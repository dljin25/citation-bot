"""Resolve extracted references against external scholarly databases.

Not yet implemented. Intended public entry point: resolve(ref) -> Resolution,
trying cheap exact-identifier lookups first (DOI, arXiv id) and falling back
to fuzzy title/author search fanned out across citebot.crossref.openalex,
citebot.crossref.dblp, and citebot.crossref.semantic_scholar, reconciling
their candidates via the scoring helpers in citebot.crossref.base.
"""
