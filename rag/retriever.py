"""Hybrid retriever: fuse normalised BM25 and embedding-cosine scores."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np

from .config import Config, load_config
from .index import load_chunks, tokenize


def _minmax(scores: np.ndarray) -> np.ndarray:
    lo, hi = float(scores.min()), float(scores.max())
    if hi - lo < 1e-12:
        return np.zeros_like(scores)
    return (scores - lo) / (hi - lo)


class HybridRetriever:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        index_dir = self.cfg.path("index_dir")
        meta_path = index_dir / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"{meta_path} not found. Run `python -m rag.cli index` first."
            )
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.chunks = load_chunks(self.cfg)

        with open(index_dir / "bm25.pkl", "rb") as fh:
            self.bm25 = pickle.load(fh)

        self.embeddings = None
        self._embed_model = None
        if self.meta.get("has_embeddings"):
            self.embeddings = np.load(index_dir / "embeddings.npy")

        rt = self.cfg.retrieval
        self.w_bm25 = float(rt["bm25_weight"])
        self.w_emb = float(rt["embedding_weight"])
        self.default_k = int(rt["top_k"])

    # -- lazy-load the embedding model only when a query needs it ------------
    def _embed_query(self, query: str) -> np.ndarray | None:
        if self.embeddings is None:
            return None
        if self._embed_model is None:
            from sentence_transformers import SentenceTransformer

            from .index import _resolve_device

            device = _resolve_device(self.cfg.embeddings.get("device", "auto"))
            self._embed_model = SentenceTransformer(
                self.meta["embedding_model"], device=device
            )
        vec = self._embed_model.encode(
            [query], normalize_embeddings=True, convert_to_numpy=True
        ).astype("float32")
        return vec[0]

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        top_k = top_k or self.default_k

        bm25_scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype="float32")

        if self.embeddings is not None:
            qvec = self._embed_query(query)
            emb_scores = self.embeddings @ qvec  # cosine (rows are unit norm)
            combined = self.w_bm25 * _minmax(bm25_scores) + self.w_emb * _minmax(
                emb_scores
            )
        else:
            emb_scores = np.zeros_like(bm25_scores)
            combined = _minmax(bm25_scores)

        order = np.argsort(combined)[::-1][:top_k]
        results = []
        for rank, idx in enumerate(order, start=1):
            rec = dict(self.chunks[idx])
            rec["rank"] = rank
            rec["score"] = round(float(combined[idx]), 4)
            rec["bm25"] = round(float(bm25_scores[idx]), 4)
            rec["embedding"] = round(float(emb_scores[idx]), 4)
            results.append(rec)
        return results


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "How can I recognize a phishing email?"
    r = HybridRetriever()
    print(f"Query: {q}\n")
    for hit in r.search(q):
        print(f"  [{hit['rank']:>2}] {hit['score']:.3f}  {hit['provider']} — {hit['title']}")
