"""Resolve references against the OpenAlex API (api.openalex.org).

Strategy: a DOI or arXiv id on the reference gets a direct, cheap /works
lookup; otherwise fall back to a plain title search and let
citebot.crossref.base score the results.
"""

from __future__ import annotations

from typing import Optional

import httpx

from citebot.crossref.base import Candidate, CrossrefSource
from citebot.models import Identifiers, Reference

API = "https://api.openalex.org/works"


def resolve(ref: Reference, *, api_key: str, limit: int = 5, timeout: float = 15.0) -> list[Candidate]:
    with httpx.Client(timeout=timeout, params={"api_key": api_key}) as client:
        doi = ref.identifiers.doi or _arxiv_doi(ref.identifiers.arxiv_id)
        if doi:
            work = _get_by_doi(client, doi)
            if work:
                return [_to_candidate(work)]

        if not ref.title:
            return []
        works = _search_by_title(client, ref.title, limit=limit)
        return [_to_candidate(w) for w in works]


def _arxiv_doi(arxiv_id: Optional[str]) -> Optional[str]:
    """OpenAlex mints a DOI for every arXiv preprint under this prefix."""
    return f"10.48550/arxiv.{arxiv_id}" if arxiv_id else None


def _get_by_doi(client: httpx.Client, doi: str) -> Optional[dict]:
    resp = client.get(f"{API}/doi:{doi}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _search_by_title(client: httpx.Client, title: str, *, limit: int) -> list[dict]:
    resp = client.get(API, params={"search": title, "per_page": limit})
    resp.raise_for_status()
    return resp.json().get("results", [])


def _to_candidate(work: dict) -> Candidate:
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    doi = (work.get("doi") or "").removeprefix("https://doi.org/") or None
    return Candidate(
        source=CrossrefSource.OPENALEX,
        title=work.get("title"),
        authors=[a["author"]["display_name"] for a in work.get("authorships", [])],
        year=work.get("publication_year"),
        identifiers=Identifiers(doi=doi, url=work.get("id")),
        venue=source.get("display_name"),
        url=location.get("landing_page_url"),
    )
