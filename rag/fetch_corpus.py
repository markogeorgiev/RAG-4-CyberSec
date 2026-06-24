"""Download the authoritative corpus (NIST, CISA, MITRE ATT&CK, OWASP).

Reads `sources.yaml`, downloads each source into `corpus/raw/`, and writes a
`manifest.json` describing what was fetched. Sources that fail to download are
logged and skipped so a single moved URL never breaks the whole build.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import Config, load_config, load_yaml

# A descriptive UA; some government sites reject the default urllib/requests UA.
USER_AGENT = (
    "Mozilla/5.0 (compatible; ai-trust-survey-rag/1.0; "
    "academic research; +https://www.cisa.gov)"
)

EXT_BY_TYPE = {
    "pdf": ".pdf",
    "html": ".html",
    "owasp_md": ".md",
    "stix": ".json",
}


def _download(url: str, dest: Path, timeout: int = 120) -> int:
    """Stream a URL to disk. Returns the number of bytes written."""
    headers = {"User-Agent": USER_AGENT}
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        total = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    fh.write(chunk)
                    total += len(chunk)
    return total


def fetch_corpus(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    raw_dir = cfg.path("raw_dir")
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources = load_yaml(cfg.path("sources_file"))["sources"]
    manifest: list[dict] = []

    print(f"Downloading {len(sources)} sources into {raw_dir}\n")
    for src in sources:
        ext = EXT_BY_TYPE.get(src["type"], ".bin")
        filename = f"{src['id']}{ext}"
        dest = raw_dir / filename
        try:
            size = _download(src["url"], dest)
            ok = size > 0
            status = f"ok  ({size/1024:,.0f} KB)" if ok else "empty"
            print(f"  [{'OK ' if ok else 'WARN'}] {src['id']:<28} {status}")
            if ok:
                manifest.append(
                    {
                        "id": src["id"],
                        "provider": src["provider"],
                        "title": src["title"],
                        "type": src["type"],
                        "url": src["url"],
                        "tasks": src.get("tasks", []),
                        "file": filename,
                        "bytes": size,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - we want to keep going
            print(f"  [FAIL] {src['id']:<28} {type(exc).__name__}: {exc}")

    manifest_path = raw_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"\nFetched {len(manifest)}/{len(sources)} sources.")
    print(f"Manifest written to {manifest_path}")
    if len(manifest) < len(sources):
        print(
            "Note: some sources were skipped. The pipeline still works with the "
            "rest; you can update URLs in rag/sources.yaml and re-run fetch."
        )
    return manifest_path


if __name__ == "__main__":
    fetch_corpus()
