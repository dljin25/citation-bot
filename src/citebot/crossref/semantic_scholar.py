"""Resolve references against the Semantic Scholar Academic Graph API.

Strategy: a DOI or arXiv id on the reference gets a direct paper lookup;
otherwise fall back to a title search and let citebot.crossref.base score
the results.
"""

from __future__ import annotations

from typing import Optional

import httpx

from citebot.crossref.base import Candidate, CrossrefSource
from citebot.models import Identifiers, Reference

API = "https://api.semanticscholar.org/graph/v1/paper"
FIELDS = "title,authors,year,externalIds,venue,url"


def resolve(ref: Reference, *, limit: int = 5, timeout: float = 15.0) -> list[Candidate]:
    with httpx.Client(timeout=timeout) as client:
        external_id = _external_id(ref)
        if external_id:
            paper = _get_by_id(client, external_id)
            if paper:
                return [_to_candidate(paper)]

        if not ref.title:
            return []
        papers = _search_by_title(client, ref.title, limit=limit)
        return [_to_candidate(p) for p in papers]


def _external_id(ref: Reference) -> Optional[str]:
    if ref.identifiers.doi:
        return f"DOI:{ref.identifiers.doi}"
    if ref.identifiers.arxiv_id:
        return f"ARXIV:{ref.identifiers.arxiv_id}"
    return None


def _get_by_id(client: httpx.Client, external_id: str) -> Optional[dict]:
    resp = client.get(f"{API}/{external_id}", params={"fields": FIELDS})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _search_by_title(client: httpx.Client, title: str, *, limit: int) -> list[dict]:
    resp = client.get(f"{API}/search", params={"query": title, "fields": FIELDS, "limit": limit})
    resp.raise_for_status()
    return resp.json().get("data", [])


def _to_candidate(paper: dict) -> Candidate:
    external = paper.get("externalIds") or {}
    return Candidate(
        source=CrossrefSource.SEMANTIC_SCHOLAR,
        title=paper.get("title"),
        authors=[a["name"] for a in paper.get("authors", [])],
        year=paper.get("year"),
        identifiers=Identifiers(doi=external.get("DOI"), arxiv_id=external.get("ArXiv"), url=paper.get("url")),
        venue=paper.get("venue"),
        url=paper.get("url"),
    )
