"""Build the hybrid retrieval index: BM25 (lexical) + embeddings (semantic).

Outputs in `index/`:
    bm25.pkl        pickled BM25Okapi over the tokenised corpus
    embeddings.npy  L2-normalised float32 embedding matrix (rows align to chunks)
    meta.json       {count, has_embeddings, embedding_model, ...}

Embeddings are optional: if sentence-transformers/torch is unavailable, the
index is still built (BM25-only) and the retriever degrades gracefully.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

from .config import Config, load_config

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def load_chunks(cfg: Config) -> list[dict]:
    path = cfg.path("chunks_file")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python -m rag.cli ingest` first."
        )
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def build_index(cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    chunks = load_chunks(cfg)
    if not chunks:
        raise RuntimeError("No chunks to index. Did fetch/ingest produce data?")

    index_dir = cfg.path("index_dir")
    index_dir.mkdir(parents=True, exist_ok=True)
    texts = [c["text"] for c in chunks]

    # ---- BM25 (lexical) ----------------------------------------------------
    from rank_bm25 import BM25Okapi

    print(f"Building BM25 over {len(texts)} chunks...")
    tokenized = [tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized)
    with open(index_dir / "bm25.pkl", "wb") as fh:
        pickle.dump(bm25, fh)

    # ---- Embeddings (semantic) --------------------------------------------
    has_embeddings = False
    emb_model_name = cfg.embeddings["model"]
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        device = _resolve_device(cfg.embeddings.get("device", "auto"))
        print(f"Embedding {len(texts)} chunks with {emb_model_name} on {device}...")
        model = SentenceTransformer(emb_model_name, device=device)
        embeddings = model.encode(
            texts,
            batch_size=cfg.embeddings.get("batch_size", 64),
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")
        np.save(index_dir / "embeddings.npy", embeddings)
        has_embeddings = True
    except Exception as exc:  # noqa: BLE001
        print(
            f"[warn] Skipping embeddings ({type(exc).__name__}: {exc}).\n"
            "       The retriever will run BM25-only. Install "
            "sentence-transformers for hybrid retrieval."
        )

    meta = {
        "count": len(chunks),
        "has_embeddings": has_embeddings,
        "embedding_model": emb_model_name if has_embeddings else None,
    }
    with open(index_dir / "meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    mode = "hybrid (BM25 + embeddings)" if has_embeddings else "BM25 only"
    print(f"\nIndex built: {len(chunks)} chunks, mode = {mode}")
    print(f"Index dir: {index_dir}")
    return index_dir


if __name__ == "__main__":
    build_index()
