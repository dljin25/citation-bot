# citebot

Research-integrity tool that audits a paper's citations against external scholarly databases.

## Language

**Run**:
One invocation of `citebot check`, from process start to exit. The OpenAlex API key is prompted for once per run and held in memory only for that run's lifetime — never written to disk, a config file, or an env var, and never reused by a later run.
_Avoid_: Session (implies persistence across invocations, e.g. a shell session or login session — this project has no such concept)
