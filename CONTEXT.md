# citebot

Research-integrity tool that audits a paper's citations against external scholarly databases.

## Language

**Run**:
One invocation of `citebot check`, from process start to exit. The OpenAlex API key is prompted for once per run and held in memory only for that run's lifetime — never written to disk, a config file, or an env var, and never reused by a later run.
_Avoid_: Session (implies persistence across invocations, e.g. a shell session or login session — this project has no such concept)

**Venue**:
The journal, book, or conference/proceedings a reference's cited work appeared in. Doesn't distinguish a journal from a conference — both are the same concept.
_Avoid_: Publisher, location (the entity or place behind the venue, not the venue itself)

**Verdict**:
The outcome `citebot check` assigns a Reference after resolving it against crossref sources: VERIFIED, AMBIGUOUS, or CONFLICT.

**Conflict** (a Verdict):
The reference's identifying details don't check out — either nothing was found despite a complete search, or a real candidate was found whose title matches but other details (author, year) don't line up. Both read the same way to a reviewer: this citation doesn't hold up. The strongest, most accusatory Verdict; requires a complete search (no source errors) to reach.
_Avoid_: Not found (the older, narrower term — covered only the "nothing found" half of what Conflict now covers), Mismatch (ambiguous about whether the cited work exists at all), Hallucination (names a *cause* — AI fabrication — the pipeline can't actually observe; a mistyped year or a genuine human error produces the same signal)
