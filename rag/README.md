# Condition C — Retrieval-Augmented Generation (RAG)

This folder implements **Condition C** of the study *"Do Users Trust AI Too Much?
Evaluating Trust in AI-Generated Cybersecurity Advice."* It is a lightweight RAG
system that answers the study's 10 cybersecurity questions using **only**
authoritative sources, and writes one grounded, cited answer per question for use
in the survey.

It implements exactly the pipeline from the study plan:

```
Question → Retriever → Relevant Documents → LLM → Final Answer
```

- **Retriever:** *hybrid* — lexical **BM25** + local semantic **embeddings**
  (`all-MiniLM-L6-v2`), scores normalized and fused.
- **LLM:** a **local Llama** model (default `llama3.1:8b`) served by
  [Ollama](https://ollama.com). No hosted/commercial LLM API is used — the whole
  generation step is local, suitable for a single GPU (e.g. RTX 2070 Super, 8 GB).
- **Corpus:** strictly the four families named in the plan — **NIST**, **CISA**,
  **MITRE ATT&CK**, **OWASP** — downloaded from their official locations.

Every answer cites the retrieved supporting documents inline (`[S1]`, `[S2]`, …)
and lists them in a **References** section, matching the plan's requirement that
"generated responses will include references to retrieved supporting documents."

> Scope: this folder builds **only Condition C**. Conditions A (Traditional
> Search) and B (Pure LLM), the survey, expert evaluation, and analysis are out of
> scope here.

---

## 1. Prerequisites

### a) Python environment

Python 3.10+ and the retrieval dependencies:

```bash
# from the project root (the folder containing rag/)
pip install -r requirements.txt
```

`sentence-transformers` pulls in PyTorch. On the RTX 2070 Super, install a
CUDA-enabled PyTorch build first (see <https://pytorch.org/get-started/locally/>)
so embeddings run on the GPU; otherwise CPU works fine for this small corpus.

> If `sentence-transformers`/torch is unavailable, the pipeline still runs in
> **BM25-only** mode (a warning is printed). Install it to get the hybrid
> retriever the study specifies.

### b) Ollama + a Llama model (the generator)

1. Install Ollama: <https://ollama.com/download>
2. Start the server (it usually runs automatically; otherwise `ollama serve`).
3. Pull the model once:

   ```bash
   ollama pull llama3.1:8b
   ```

`llama3.1:8b` is 4-bit quantized by default (~4.7 GB) and fits comfortably in
8 GB VRAM. To use a different model, change `llm.model` in
[`config.yaml`](config.yaml) and `ollama pull` it.

---

## 2. Run the pipeline

From the **project root**, run the whole thing end-to-end:

```bash
python -m rag.cli all
```

Or run the stages individually (each writes its output to disk, so you can stop
and resume):

```bash
python -m rag.cli fetch     # 1. download NIST/CISA/MITRE/OWASP -> rag/corpus/raw/
python -m rag.cli ingest    # 2. extract + chunk text         -> rag/corpus/chunks.jsonl
python -m rag.cli index     # 3. build BM25 + embeddings index -> rag/index/
python -m rag.cli run       # 4. generate answers              -> rag/answers/
```

Generate a subset of tasks:

```bash
python -m rag.cli run --tasks T1 T8 T10
```

Inspect retrieval without calling the LLM (useful for tuning):

```bash
python -m rag.cli search "what should I do after clicking a suspicious link"
```

---

## 3. Output

For each task `T1`…`T10`, [`rag/answers/`](answers/) gets two files:

- **`T#.md`** — the human-readable answer with inline `[S#]` citations, a
  **References** list of the retrieved sources, and a collapsible table of
  hybrid-retrieval scores. This is what you show participants as "Answer A/B/C".
- **`T#.json`** — a full record for analysis: the answer text, the exact
  retrieved passages with scores, and the prompts used. Useful for the
  ground-truth/expert evaluation and for reproducibility.

---

## 4. How it works

| Stage | File | What it does |
|-------|------|--------------|
| Fetch | [`fetch_corpus.py`](fetch_corpus.py) | Downloads every entry in [`sources.yaml`](sources.yaml). Failed/moved URLs are skipped, not fatal. |
| Ingest | [`ingest.py`](ingest.py) | PDF (pypdf), HTML (BeautifulSoup), OWASP markdown, and MITRE STIX → cleaned, overlapping text chunks (`chunks.jsonl`). Each ATT&CK technique becomes its own document. |
| Index | [`index.py`](index.py) | Builds a BM25 index and a normalized embedding matrix. |
| Retrieve | [`retriever.py`](retriever.py) | Fuses min-max-normalized BM25 + cosine scores (weights in `config.yaml`) and returns the top-k passages. |
| Generate | [`generate.py`](generate.py) | Builds a grounded, citation-instructed prompt and calls the local Llama model via [`llm.py`](llm.py). |

All knobs (model, chunk size, `top_k`, BM25/embedding weights, generation length)
live in [`config.yaml`](config.yaml).

---

## 5. The corpus

The corpus is defined entirely in [`sources.yaml`](sources.yaml) — **only** NIST,
CISA, MITRE ATT&CK, and OWASP. It currently includes, mapped to the tasks they
chiefly support:

| Provider | Documents | Mainly supports |
|----------|-----------|-----------------|
| **NIST** | SP 800-63B (auth), 800-46r2 (telework/home network), 800-41r1 (firewalls), 800-83r1 (malware), 800-61r2 (incident handling), 800-184 (recovery) | T2–T9 |
| **CISA** | Secure Our World pages (phishing, passwords, MFA, updates), Phishing Guidance, #StopRansomware Guide | T1, T2, T4, T5, T7, T8, T9, T10 |
| **MITRE ATT&CK** | Enterprise STIX bundle — every technique as a document (e.g. T1566 Phishing) | T1, T2, T6, T10 |
| **OWASP** | Cheat Sheets: Authentication, Password Storage, MFA, Credential Stuffing, TLS, Vulnerable Dependency Management | T3, T4, T5, T8 |

To add or swap a source, edit `sources.yaml` and re-run `fetch → ingest → index`.
Keep additions within the four allowed families to stay faithful to the study
design.

---

## 6. Reproducibility notes

- `rag/corpus/raw/`, `rag/corpus/chunks.jsonl`, and `rag/index/` are
  git-ignored (large / rebuildable). `rag/answers/` is kept.
- Generation uses a low temperature (`0.2`) for faithful, low-invention output,
  but local LLM decoding is not bit-for-bit deterministic; regenerate if you
  need to refresh answers. The retrieved passages saved in each `T#.json` make
  the grounding fully auditable regardless.
- MITRE ATT&CK and OWASP are pulled from their `master` branches, so the corpus
  reflects the latest published content at fetch time. Note the fetch date for
  your methods section.
