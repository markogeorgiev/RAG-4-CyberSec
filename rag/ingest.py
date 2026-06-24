"""Extract text from the raw corpus and chunk it into `chunks.jsonl`.

Each output line is one retrievable passage:
    {id, source_id, provider, title, url, chunk_index, text}

Handles four source types: pdf, html, owasp_md, stix (MITRE ATT&CK).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import Config, load_config


# --------------------------------------------------------------------------- #
# Text extraction per source type
# --------------------------------------------------------------------------- #
def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - skip unreadable pages
            continue
    return "\n".join(parts)


def _extract_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")
    # Drop non-content chrome.
    for tag in soup(["script", "style", "nav", "header", "footer", "form", "aside", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text("\n")


def _extract_markdown(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    # Light cleanup: strip HTML comments and image tags; keep prose + structure.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    return text


def _clean(text: str) -> str:
    """Normalise whitespace; collapse runs of blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def chunk_text(text: str, size: int, overlap: int, min_chars: int) -> list[str]:
    """Greedy paragraph-aware chunker with character overlap."""
    text = _clean(text)
    if not text:
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= size or not buf:
            buf = f"{buf}\n\n{para}".strip()
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap else ""
            buf = f"{tail}\n\n{para}".strip()
        # A single very long paragraph: hard-split it.
        while len(buf) > size * 1.5:
            chunks.append(buf[:size])
            buf = buf[size - overlap :]
    if buf:
        chunks.append(buf)

    return [c.strip() for c in chunks if len(c.strip()) >= min_chars]


# --------------------------------------------------------------------------- #
# MITRE ATT&CK STIX -> per-technique documents
# --------------------------------------------------------------------------- #
def _iter_attack_techniques(path: Path):
    """Yield (technique_id, name, url, description) for each active technique."""
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        description = (obj.get("description") or "").strip()
        if not description:
            continue
        ext_id, ext_url = "", ""
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                ext_id = ref.get("external_id", "")
                ext_url = ref.get("url", "")
                break
        yield ext_id, obj.get("name", ""), ext_url, description


# --------------------------------------------------------------------------- #
# Main ingest
# --------------------------------------------------------------------------- #
def ingest(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    raw_dir = cfg.path("raw_dir")
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"{manifest_path} not found. Run `python -m rag.cli fetch` first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ch = cfg.chunk
    size, overlap, min_chars = ch["size"], ch["overlap"], ch["min_chars"]

    out_path = cfg.path("chunks_file")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    print(f"Ingesting {len(manifest)} sources -> {out_path}\n")

    for src in manifest:
        path = raw_dir / src["file"]
        stype = src["type"]
        try:
            if stype == "stix":
                count = 0
                for tid, name, url, desc in _iter_attack_techniques(path):
                    title = f"MITRE ATT&CK {tid}: {name}".strip().rstrip(":")
                    for ci, piece in enumerate(chunk_text(desc, size, overlap, min_chars)):
                        records.append(
                            {
                                "id": f"{src['id']}::{tid}::{ci}",
                                "source_id": src["id"],
                                "provider": src["provider"],
                                "title": title,
                                "url": url or src["url"],
                                "chunk_index": ci,
                                "text": piece,
                            }
                        )
                        count += 1
                print(f"  [OK] {src['id']:<28} {count:>4} technique chunks")
                continue

            if stype == "pdf":
                raw_text = _extract_pdf(path)
            elif stype == "html":
                raw_text = _extract_html(path)
            elif stype == "owasp_md":
                raw_text = _extract_markdown(path)
            else:
                print(f"  [SKIP] {src['id']:<28} unknown type {stype!r}")
                continue

            pieces = chunk_text(raw_text, size, overlap, min_chars)
            for ci, piece in enumerate(pieces):
                records.append(
                    {
                        "id": f"{src['id']}::{ci}",
                        "source_id": src["id"],
                        "provider": src["provider"],
                        "title": src["title"],
                        "url": src["url"],
                        "chunk_index": ci,
                        "text": piece,
                    }
                )
            print(f"  [OK] {src['id']:<28} {len(pieces):>4} chunks")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {src['id']:<28} {type(exc).__name__}: {exc}")

    with open(out_path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    providers = sorted({r["provider"] for r in records})
    print(f"\nWrote {len(records)} chunks from providers: {', '.join(providers)}")
    print(f"Chunks file: {out_path}")
    return out_path


if __name__ == "__main__":
    ingest()
