import os

import pytest

import cite

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("CITE_LIVE") != "1", reason="set CITE_LIVE=1 to hit the real APIs")]


def test_pastrana_papers_are_each_others_siblings():
    cad = cite.crossref("10.1016/j.cad.2022.103435")
    assert (cad.venue, cad.year) == ("Computer-Aided Design", 2023)
    jax = cite.arxiv("2307.12407")
    assert jax.title.startswith("JAX FDM")
    assert "https://arxiv.org/abs/2307.12407" in [w["link"] for w in cite.siblings(cad, show_all=True)["shown"]]
    assert "https://doi.org/10.1016/j.cad.2022.103435" in [w["link"] for w in cite.siblings(jax, show_all=True)["shown"]]
