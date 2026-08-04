# citebot

Stage 1 extraction: pull the reference list out of an arXiv paper's compiled
`.bbl` or a PDF, normalized into a common `Reference` model. 

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Usage

```bash
citebot extract 1706.03762
```

Each `Reference` (defined in [`src/models.py`](src/models.py)) carries the raw
citation string, parsed title/authors/year/venue, extracted identifiers
(DOI/arXiv id/URL), and the extraction source + confidence.

## Development

```bash
pip install -e ".[dev]"
pytest          # offline parser + normalization tests
```
