"""citebot command-line interface.

Commands:
1. `extract` gets the references with no validation
2. `check` runs the full pipeline: extract → resolve → score → classify → report.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from citebot.models import Reference

app = typer.Typer(add_completion=False, help="Citation verification bot") # Typer CLI app object

_ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$|^[a-z\-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$") # regex matcher for arXiv IDs

@app.callback()
def _main() -> None:
    """Citation verification (subcommands: extract, ...)."""

def _detect_and_extract(source: str) -> tuple[str, list[Reference]]:
    """Return (source_kind, references)."""

    # PDF
    p = Path(source)
    if source.lower().endswith(".pdf"):
        from citebot.extract import pdf 
        return "pdf", pdf.extract(p)

    #arXiv
    if _ARXIV_ID_RE.match(source):
        from citebot.extract import arxiv
        try:
            return "arxiv", arxiv.extract(source)
        except ValueError as e:
            raise typer.BadParameter(str(e))

    raise typer.BadParameter(
        f"Could not interpret '{source}' as a .pdf or arXiv id."
    )


@app.command()
def extract(
    source: str = typer.Argument(..., help="arXiv id or path to .pdf"),
    as_json: bool = typer.Option(False, "--json", help="Emit references as JSON"),
):
    """Extract and print references for inspection."""
    kind, refs = _detect_and_extract(source)

    if as_json:
        typer.echo(json.dumps([r.model_dump() for r in refs], indent=2, ensure_ascii=False))
        return

    # print extraction summary

    typer.echo(f"\nSource: {source}  (kind={kind})")
    typer.echo(f"Extracted {len(refs)} references\n" + "=" * 70)
    typer.echo("")

    n_titled = sum(1 for r in refs if r.title)
    n_authored = sum(1 for r in refs if r.authors)
    n_ids = sum(1 for r in refs if r.identifiers.doi or r.identifiers.arxiv_id)
    for r in refs:
        ids = []
        if r.identifiers.arxiv_id:
            ids.append(f"arXiv:{r.identifiers.arxiv_id}")
        if r.identifiers.doi:
            ids.append(f"doi:{r.identifiers.doi}")
        id_str = ("  [" + ", ".join(ids) + "]") if ids else ""
        typer.echo(f"  title : {r.title!r}")
        typer.echo(f"  auth  : {r.authors}")
        typer.echo(f"  year  : {r.year} \n" )

    typer.echo("=" * 70)
    typer.echo(
        f"summary: {len(refs)} refs | {n_titled} with title | "
        f"{n_authored} with authors | {n_ids} with DOI/arXiv id"
    )


@app.command()
def check(
    source: str = typer.Argument(..., help="arXiv id or path to .pdf"),
):
    """Extract references, resolve each against crossref sources, and classify it.

    Bare bones: no `score` stage yet (that needs the citation's claim/context,
    which isn't wired up), so this is extract -> resolve -> classify -> print.
    """
    from concurrent.futures import ThreadPoolExecutor

    from citebot import classify as classify_mod
    from citebot import crossref

    typer.echo("OpenAlex requires a free API key (get one at https://openalex.org/settings/api).")
    api_key = typer.prompt("OpenAlex API key", hide_input=True)
    if not api_key:
        raise typer.BadParameter("An OpenAlex API key is required.")

    kind, refs = _detect_and_extract(source)

    typer.echo(f"\nSource: {source}  (kind={kind})")
    typer.echo(f"Checking {len(refs)} references against OpenAlex...\n")

    def _resolve_and_classify(r: Reference):
        resolution = crossref.resolve(r, api_key)
        return r, resolution, classify_mod.classify(resolution)

    counts: dict[classify_mod.Verdict, int] = {v: 0 for v in classify_mod.Verdict}
    with ThreadPoolExecutor(max_workers=10) as executor:
        for r, resolution, verdict in executor.map(_resolve_and_classify, refs):
            counts[verdict] += 1

            best = resolution.best
            best_str = (
                f"{best.title!r} ({best.source.value}, score={best.match_score:.2f})"
                if best
                else "no candidates found"
            )
            typer.echo(f"  [{verdict.value:10}] {r.title!r}")
            typer.echo(f"               -> {best_str}")

    typer.echo("\n" + "=" * 70)
    summary = " | ".join(f"{v.value}={n}" for v, n in counts.items())
    typer.echo(f"summary: {len(refs)} refs | {summary}")
