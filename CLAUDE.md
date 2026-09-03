# citebot

Research-integrity tool for auditing citations, starting with NeurIPS submissions. Pipeline: extract references (PDF/.bbl) → parse into a normalized `Reference` model → resolve against crossref backends (Semantic Scholar, OpenAlex, DBLP) → classify each citation's verdict.

## Setup

Always `conda activate cite` before running Python, pip, pytest, or `citebot` commands — base/system Python lacks or has stale versions of the deps.

If `conda activate` fails silently in this harness, use `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate cite` instead, and confirm with `python -c "import sys; print(sys.executable)"` (should show a path containing `envs/cite`).

## Working style

- **Ask before implementing.** Even for "suggest ways to fix X" or small/obvious fixes — present options and wait for explicit go-ahead before editing files.
- **Simplicity first.** Minimum code that solves the problem, no speculative abstractions, no unrequested error handling. Match existing style; don't refactor or clean up unrelated code.
- **Surgical diffs.** Every changed line should trace to the request. Flag unrelated dead code instead of deleting it.
- **State assumptions.** If a request has multiple interpretations, present them instead of picking silently.

## Project-specific rules

- **Bias toward low false positives.** Any code that assigns a verdict to a citation (`classify`, eventually `score`) is making an accusation when it says `NOT_FOUND` or `MISMATCH` against a plausibly-legitimate author. Default to `AMBIGUOUS` under incomplete evidence (e.g. a crossref source errored out). `VERIFIED` can have a more generous bar since it isn't an accusation.
- **Cross-reference concurrency is standard; per-backend fan-out concurrency is still deferred.** `citebot check` resolves references concurrently (a `ThreadPoolExecutor` in `cli.py`), but each reference is still resolved against one backend at a time — no concurrency, retries, or rate-limit handling *across* DBLP/OpenAlex/Semantic Scholar within a single `resolve()` call. That fan-out design is deferred as a later system-design problem; keep backend code itself simple and sequential (fresh `httpx.Client` per call) until asked to revisit it.
- **DBLP and Semantic Scholar are temporarily disabled.** Only OpenAlex is queried (see `_BACKENDS` in `crossref/__init__.py`) until per-backend fan-out concurrency and each backend's rate limits are designed. OpenAlex requires a free API key, prompted for interactively once per `check` run and held in memory only — see `CONTEXT.md`'s **Run** entry.
