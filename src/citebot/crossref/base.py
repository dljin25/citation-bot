"""Shared resolver interface and matching helpers for crossref backends.

Not yet implemented. Intended to hold: a Resolver protocol (parallel to
citebot.extract.base.Extractor) that openalex.py / dblp.py /
semantic_scholar.py each implement, a shared candidate/match data model,
and scoring helpers (title similarity, author overlap, year tolerance) used
to turn a source's raw results into a confidence score.
"""
