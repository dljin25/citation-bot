"""Resolve references against the OpenAlex API (api.openalex.org).

Not yet implemented. Intended strategy: DOI or arXiv id present -> direct
`/works/doi:{doi}` (or equivalent) lookup; otherwise -> title search filtered
by publication year, scored via citebot.crossref.base.
"""
