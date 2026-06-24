"""Configuration loading and path resolution for the RAG pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# rag/config.py  ->  rag/  ->  project root
PKG_DIR = Path(__file__).resolve().parent
ROOT_DIR = PKG_DIR.parent
CONFIG_FILE = PKG_DIR / "config.yaml"


class Config:
    """Thin wrapper around config.yaml with project-root-relative paths."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    # -- raw access ----------------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    # -- resolved paths ------------------------------------------------------
    def path(self, key: str) -> Path:
        """Resolve a path under `paths:` to an absolute Path under the root."""
        rel = self._data["paths"][key]
        return (ROOT_DIR / rel).resolve()

    @property
    def llm(self) -> dict[str, Any]:
        return self._data["llm"]

    @property
    def embeddings(self) -> dict[str, Any]:
        return self._data["embeddings"]

    @property
    def chunk(self) -> dict[str, Any]:
        return self._data["chunk"]

    @property
    def retrieval(self) -> dict[str, Any]:
        return self._data["retrieval"]


def load_config(path: Path | str | None = None) -> Config:
    path = Path(path) if path else CONFIG_FILE
    with open(path, "r", encoding="utf-8") as fh:
        return Config(yaml.safe_load(fh))


def load_yaml(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
