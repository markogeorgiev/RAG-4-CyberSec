"""Minimal client for a local Llama model served by Ollama.

Uses the Ollama HTTP API (/api/chat) over plain `requests` — no hosted or
commercial LLM provider is involved. Streaming is used so long generations
don't hit a single-shot timeout.
"""

from __future__ import annotations

import json

import requests

from .config import Config, load_config


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, cfg: Config | None = None):
        cfg = cfg or load_config()
        llm = cfg.llm
        self.base_url = llm["base_url"].rstrip("/")
        self.model = llm["model"]
        self.timeout = int(llm.get("request_timeout", 600))
        self.options = {
            "temperature": float(llm.get("temperature", 0.2)),
            "num_ctx": int(llm.get("num_ctx", 8192)),
            "num_predict": int(llm.get("num_predict", 2048)),
        }

    # -- preflight -----------------------------------------------------------
    def health_check(self) -> None:
        """Raise a clear error if Ollama isn't reachable or the model is missing."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(
                f"Cannot reach Ollama at {self.base_url}. Is it running? "
                f"Start it with `ollama serve` (and `ollama pull {self.model}`).\n"
                f"Underlying error: {type(exc).__name__}: {exc}"
            ) from exc
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        # Ollama tags look like "llama3.1:8b"; allow a match on the bare base too.
        if self.model not in names and f"{self.model}:latest" not in names:
            raise OllamaError(
                f"Model {self.model!r} is not available in Ollama.\n"
                f"Pull it first:  ollama pull {self.model}\n"
                f"Installed models: {', '.join(sorted(names)) or '(none)'}"
            )

    # -- generation ----------------------------------------------------------
    def chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "stream": True,
            "options": self.options,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise OllamaError(
                f"Generation request to Ollama failed: {type(exc).__name__}: {exc}"
            ) from exc

        parts: list[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in event:
                raise OllamaError(f"Ollama error: {event['error']}")
            parts.append(event.get("message", {}).get("content", ""))
            if event.get("done"):
                break
        return "".join(parts).strip()
