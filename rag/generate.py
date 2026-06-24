"""Answer generation: retrieve -> build grounded prompt -> Llama -> render.

For each task the system retrieves the top-k passages, asks the local Llama
model to write a comprehensive answer grounded strictly in those passages with
inline [S#] citations, and writes a Markdown answer plus a JSON record (the
retrieved passages, scores, and prompt) for the study's analysis.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .config import Config, load_config, load_yaml
from .llm import OllamaClient
from .retriever import HybridRetriever

SYSTEM_PROMPT = (
    "You are a senior cybersecurity expert writing clear, accurate, defensive "
    "security guidance for a general audience.\n"
    "You answer ONLY using the numbered SOURCES provided in the user message.\n"
    "\n"
    "Rules:\n"
    "1. Be comprehensive, well-structured, and practical. Use Markdown headings, "
    "short paragraphs, and numbered or bulleted steps.\n"
    "2. Ground every factual claim in the sources and cite them inline with their "
    "bracket IDs, e.g. [S1], [S3]. Cite the specific source(s) supporting each "
    "statement; you may cite more than one.\n"
    "3. Do NOT invent facts, settings, product names, URLs, or steps that are not "
    "supported by the sources. If the sources do not cover part of the question, "
    "say so briefly instead of guessing.\n"
    "4. Prefer concrete specifics found in the sources (procedures, thresholds, "
    "settings) over vague advice.\n"
    "Write only the answer, with no preamble or sign-off."
)


def _build_user_prompt(question: str, hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        header = f"[S{i}] {h['provider']} — {h['title']}"
        if h.get("url"):
            header += f" ({h['url']})"
        blocks.append(f"{header}\n{h['text']}")
    sources = "\n\n".join(blocks)
    return (
        f"Question: {question}\n\n"
        f"SOURCES:\n{sources}\n\n"
        "Write the most detailed, accurate answer you can to the question above, "
        "grounded in and citing these sources with [S#] markers."
    )


def _render_markdown(task_id: str, question: str, answer: str, hits: list[dict], model: str) -> str:
    cited = sorted(int(n) for n in set(re.findall(r"\[S(\d+)\]", answer)))
    cited_note = (
        f"Cited sources: {', '.join(f'[S{n}]' for n in cited)}" if cited else
        "Cited sources: (none detected — review the answer)"
    )

    lines = [
        f"# {task_id} — {question}",
        "",
        f"> **Condition C (RAG)** — hybrid retrieval (BM25 + MiniLM embeddings) over "
        f"NIST / CISA / MITRE ATT&CK / OWASP, synthesized by `{model}` (local).  ",
        f"> {cited_note}",
        "",
        answer.strip(),
        "",
        "## References (retrieved sources)",
        "",
    ]
    for i, h in enumerate(hits, start=1):
        ref = f"- **[S{i}]** {h['provider']} — {h['title']}"
        if h.get("url"):
            ref += f". <{h['url']}>"
        lines.append(ref)

    lines += ["", "<details><summary>Retrieval details (hybrid scores)</summary>", ""]
    lines.append("| ID | Score | BM25 | Embed | Source |")
    lines.append("|----|------:|-----:|------:|--------|")
    for i, h in enumerate(hits, start=1):
        lines.append(
            f"| S{i} | {h['score']:.3f} | {h['bm25']:.3f} | {h['embedding']:.3f} | "
            f"{h['provider']} — {h['title']} |"
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def answer_task(
    task_id: str,
    question: str,
    retriever: HybridRetriever,
    client: OllamaClient,
    cfg: Config,
) -> dict:
    hits = retriever.search(question)
    user_prompt = _build_user_prompt(question, hits)
    answer = client.chat(SYSTEM_PROMPT, user_prompt)

    answers_dir = cfg.path("answers_dir")
    answers_dir.mkdir(parents=True, exist_ok=True)

    md = _render_markdown(task_id, question, answer, hits, client.model)
    (answers_dir / f"{task_id}.md").write_text(md, encoding="utf-8")

    record = {
        "task_id": task_id,
        "question": question,
        "model": client.model,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "answer": answer,
        "retrieved": [
            {
                "rank": h["rank"],
                "score": h["score"],
                "bm25": h["bm25"],
                "embedding": h["embedding"],
                "source_id": h["source_id"],
                "provider": h["provider"],
                "title": h["title"],
                "url": h.get("url", ""),
                "text": h["text"],
            }
            for h in hits
        ],
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
    }
    (answers_dir / f"{task_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def run_tasks(cfg: Config | None = None, only: list[str] | None = None) -> None:
    cfg = cfg or load_config()
    tasks = load_yaml(cfg.path("tasks_file"))["tasks"]
    if only:
        wanted = {t.upper() for t in only}
        tasks = [t for t in tasks if t["id"].upper() in wanted]
        if not tasks:
            raise SystemExit(f"No tasks matched {sorted(wanted)}.")

    retriever = HybridRetriever(cfg)
    client = OllamaClient(cfg)
    client.health_check()

    print(f"Generating answers with {client.model} for {len(tasks)} task(s)...\n")
    for t in tasks:
        print(f"  -> {t['id']}: {t['question']}")
        rec = answer_task(t["id"], t["question"], retriever, client, cfg)
        cited = sorted(set(re.findall(r"\[S(\d+)\]", rec["answer"])))
        print(
            f"     {len(rec['answer'])} chars, "
            f"{len(rec['retrieved'])} sources retrieved, "
            f"cited: {', '.join('S'+c for c in cited) or 'none'}"
        )

    print(f"\nDone. Answers in {cfg.path('answers_dir')}")


if __name__ == "__main__":
    run_tasks()
