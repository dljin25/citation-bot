"""Resolve references against the DBLP publication search API (dblp.org).

DBLP has no DOI/arXiv lookup, only free-text search, so this backend is a
title-search fallback with strong coverage of CS/ML venues, used as a
secondary cross-check alongside citebot.crossref.openalex.
"""

from __future__ import annotations

import html

import httpx

from citebot.crossref.base import Candidate, CrossrefSource
from citebot.models import Identifiers, Reference

SEARCH_URL = "https://dblp.org/search/publ/api"
_USER_AGENT = "citebot/0.1 (research-integrity tool; mailto:davidjin684@gmail.com)"


def resolve(ref: Reference, *, limit: int = 5, timeout: float = 15.0) -> list[Candidate]:
    """Search DBLP by title and return the top matches as candidates."""
    if not ref.title:
        return []

    params = {"q": ref.title, "format": "json", "h": limit}
    with httpx.Client(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if isinstance(hits, dict):  # DBLP collapses a single hit to a dict, not a list
        hits = [hits]

    return [_to_candidate(hit["info"]) for hit in hits if "info" in hit]


def _to_candidate(info: dict) -> Candidate:
    year = info.get("year", "")
    title = info.get("title")
    return Candidate(
        source=CrossrefSource.DBLP,
        title=html.unescape(title) if title else None,
        authors=_authors(info),
        year=int(year) if year.isdigit() else None,
        identifiers=_identifiers(info),
        venue=info.get("venue"),
        url=info.get("url"),
    )


def _authors(info: dict) -> list[str]:
    raw = info.get("authors", {}).get("author", [])
    if isinstance(raw, dict):  # a single author comes back as a dict, not a list
        raw = [raw]
    names = [author["text"] if isinstance(author, dict) else author for author in raw]
    return [html.unescape(name) for name in names]  # DBLP HTML-escapes names too, e.g. "&aacute;"


def _identifiers(info: dict) -> Identifiers:
    ee = info.get("ee", "")  # DBLP's "electronic edition" link; often a DOI or arXiv URL
    arxiv_id = ee.rsplit("/", 1)[-1] if "arxiv.org/abs/" in ee else None
    return Identifiers(doi=info.get("doi") or None, arxiv_id=arxiv_id, url=info.get("url"))
