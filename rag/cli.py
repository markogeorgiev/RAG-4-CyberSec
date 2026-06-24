"""Command-line entry point for the RAG pipeline.

Usage (from the project root):
    python -m rag.cli fetch        # download the NIST/CISA/MITRE/OWASP corpus
    python -m rag.cli ingest       # extract + chunk text -> chunks.jsonl
    python -m rag.cli index        # build BM25 + embedding index
    python -m rag.cli run          # generate answers for all 10 tasks
    python -m rag.cli run --tasks T1 T8   # only specific tasks
    python -m rag.cli all          # fetch -> ingest -> index -> run
    python -m rag.cli search "how do I spot phishing"   # debug retrieval only
"""

from __future__ import annotations

import argparse

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag", description="Condition C RAG pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("fetch", help="Download the authoritative corpus")
    sub.add_parser("ingest", help="Extract and chunk the corpus")
    sub.add_parser("index", help="Build the hybrid retrieval index")

    p_run = sub.add_parser("run", help="Generate answers with the local Llama model")
    p_run.add_argument("--tasks", nargs="*", help="Task IDs, e.g. T1 T8 (default: all)")

    sub.add_parser("all", help="fetch -> ingest -> index -> run")

    p_search = sub.add_parser("search", help="Debug: show retrieved passages only")
    p_search.add_argument("query", nargs="+", help="Query text")
    p_search.add_argument("-k", type=int, default=None, help="Top-k (default from config)")

    args = parser.parse_args()
    cfg = load_config()

    if args.command == "fetch":
        from .fetch_corpus import fetch_corpus

        fetch_corpus(cfg)

    elif args.command == "ingest":
        from .ingest import ingest

        ingest(cfg)

    elif args.command == "index":
        from .index import build_index

        build_index(cfg)

    elif args.command == "run":
        from .generate import run_tasks

        run_tasks(cfg, only=args.tasks)

    elif args.command == "all":
        from .fetch_corpus import fetch_corpus
        from .generate import run_tasks
        from .index import build_index
        from .ingest import ingest

        fetch_corpus(cfg)
        print("\n" + "=" * 70 + "\n")
        ingest(cfg)
        print("\n" + "=" * 70 + "\n")
        build_index(cfg)
        print("\n" + "=" * 70 + "\n")
        run_tasks(cfg)

    elif args.command == "search":
        from .retriever import HybridRetriever

        retriever = HybridRetriever(cfg)
        query = " ".join(args.query)
        print(f"Query: {query}\n")
        for hit in retriever.search(query, top_k=args.k):
            snippet = hit["text"].replace("\n", " ")[:140]
            print(f"[{hit['rank']:>2}] {hit['score']:.3f}  {hit['provider']} — {hit['title']}")
            print(f"      {snippet}...\n")


if __name__ == "__main__":
    main()
