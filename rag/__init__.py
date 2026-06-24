"""Lightweight RAG pipeline for Condition C of the AI-trust survey.

Question -> Retriever (hybrid BM25 + embeddings) -> Relevant Documents -> Llama -> Final Answer

Grounded strictly in NIST, CISA, MITRE ATT&CK, and OWASP sources.
"""

__all__ = ["config"]
