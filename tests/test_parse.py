"""Offline parser tests — no network required.

Exercises the two .bbl dialects citebot.parse.bibtex handles, plus the
normalization helpers. These let us validate parsing logic deterministically;
end-to-end runs on real arXiv ids are a separate manual gate.
"""

from citebot.parse import normalize as N
from citebot.parse.bibtex import (
    parse,
    parse_bibitems,
    parse_biblatex_bbl,
)

# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
def test_strip_latex_accents_and_commands():
    assert N.strip_latex(r"\emph{Deep} learning") == "Deep learning"
    assert N.strip_latex(r"Sch\"{o}lkopf") == "Scholkopf"
    assert N.strip_latex(r"Attention~is all you need") == "Attention is all you need"


def test_identifier_extraction():
    assert N.extract_arxiv_id("Preprint arXiv:2003.08271v2.") == "2003.08271v2"
    assert N.extract_doi("https://doi.org/10.1145/3292500.3330701 here") == "10.1145/3292500.3330701"
    assert N.extract_year("In Proc. NeurIPS, 2021.") == 2021


def test_parse_authors_variants():
    assert N.parse_authors("Yann LeCun and Yoshua Bengio") == ["Yann LeCun", "Yoshua Bengio"]
    a = N.parse_authors("Vaswani, Ashish, Shazeer, Noam and Parmar, Niki")
    assert "Ashish Vaswani" in a and "Noam Shazeer" in a
    assert N.surname("Yann LeCun") == "lecun"
    assert N.surname("LeCun, Yann") == "lecun"


# --------------------------------------------------------------------------- #
# natbib / plain .bbl
# --------------------------------------------------------------------------- #
NATBIB = r"""
\begin{thebibliography}{1}
\bibitem[Vaswani et al.(2017)]{vaswani2017}
Ashish Vaswani, Noam Shazeer, and Niki Parmar.
\newblock Attention is all you need.
\newblock In \emph{Advances in Neural Information Processing Systems}, 2017.
\end{thebibliography}
"""


def test_parse_bibitems():
    refs = parse_bibitems(NATBIB)
    assert len(refs) == 1
    r = refs[0]
    assert r.ref_id == "vaswani2017"
    assert r.title == "Attention is all you need"
    assert "Ashish Vaswani" in r.authors
    assert r.year == 2017


# --------------------------------------------------------------------------- #
# biblatex .bbl
# --------------------------------------------------------------------------- #
BIBLATEX = r"""
\entry{kingma2014}{article}{}
  \name{author}{2}{}{%
    {{hash=a}{family={Kingma}{K.}{given={Diederik}}{D.}}}%
    {{hash=b}{family={Ba}{B.}{given={Jimmy}}{J.}}}%
  }
  \field{title}{Adam: A Method for Stochastic Optimization}
  \field{journaltitle}{ICLR}
  \field{year}{2015}
  \field{eprint}{1412.6980}
\endentry
"""


def test_parse_biblatex():
    refs = parse_biblatex_bbl(BIBLATEX)
    assert len(refs) == 1
    r = refs[0]
    assert r.title.startswith("Adam")
    assert r.year == 2015
    assert r.identifiers.arxiv_id == "1412.6980"
    assert any("Kingma" in a for a in r.authors)


def test_dispatch_bbl():
    refs = parse(NATBIB)
    assert len(refs) == 1 and refs[0].ref_id == "vaswani2017"
