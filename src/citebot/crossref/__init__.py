"""Resolve extracted references against external scholarly databases.

Public entry point: resolve(ref, api_key) -> Resolution. Fans a reference out
to the active crossref backends, scores every candidate returned via
citebot.crossref.base.score, and returns the best-scoring one alongside which
sources actually responded.
"""

from __future__ import annotations

import httpx

from citebot.crossref import base, openalex
# DBLP and Semantic Scholar are temporarily disabled while per-backend fan-out
# concurrency and their rate limits are redesigned — see CLAUDE.md.
# from citebot.crossref import dblp, semantic_scholar
from citebot.crossref.base import Candidate, CrossrefSource, Resolution
from citebot.models import Reference

_BACKENDS = {
    CrossrefSource.OPENALEX: openalex,
    # CrossrefSource.SEMANTIC_SCHOLAR: semantic_scholar,
    # CrossrefSource.DBLP: dblp,
}


def resolve(ref: Reference, api_key: str) -> Resolution:
    """Search all active crossref sources for ref and return the best match, if any."""
    candidates: list[Candidate] = []
    sources_ok: list[CrossrefSource] = []

    for source, backend in _BACKENDS.items():
        try:
            found = backend.resolve(ref, api_key=api_key)
        except (httpx.HTTPError, ValueError):
            continue  # one source being down/misbehaving shouldn't fail the whole resolution
        sources_ok.append(source)
        for candidate in found:
            candidate.match_score = base.score(ref, candidate)
            candidates.append(candidate)

    candidates.sort(key=lambda c: c.match_score, reverse=True)
    best = candidates[0] if candidates else None
    return Resolution(ref_id=ref.ref_id, candidates=candidates, best=best, sources_ok=sources_ok)
