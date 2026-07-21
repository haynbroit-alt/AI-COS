"""Rapport Signaux Velyx (terrain/velyx_report.py) — rendu pur, zéro réseau."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TERRAIN = Path(__file__).resolve().parent.parent / "terrain"

spec = importlib.util.spec_from_file_location("velyx_report", TERRAIN / "velyx_report.py")
report = importlib.util.module_from_spec(spec)
sys.modules["velyx_report"] = report
spec.loader.exec_module(report)


def _data(**kw):
    base = {
        "genere_le": "2026-07-21",
        "signaux": [
            {"societe": "Mendo", "type": "levee_de_fonds", "signal": "Levée de 12 M€",
             "date": "2026-06-11", "source": "src", "angle": "budget frais"},
            {"societe": "Pennylane", "type": "recrutement_sales", "signal": "Team Lead SDR",
             "date": "2026-07", "source": "src", "angle": "outbound s'industrialise"},
        ],
    }
    base.update(kw)
    return base


def test_rendu_contient_groupes_et_societes():
    md = report.render(_data())
    assert "Recrutement commercial actif" in md
    assert "Levée de fonds récente" in md
    assert "**Pennylane**" in md and "**Mendo**" in md
    assert "budget frais" in md  # les angles d'approche sont rendus


def test_groupe_vide_omis():
    md = report.render(_data(signaux=[{"societe": "X", "type": "levee_de_fonds",
                                       "signal": "s", "date": "2026-07-01",
                                       "source": "src", "angle": "a"}]))
    assert "Levée de fonds récente" in md
    assert "Recrutement commercial actif" not in md


def test_tri_par_date_decroissante():
    data = _data(signaux=[
        {"societe": "Vieux", "type": "levee_de_fonds", "signal": "s", "date": "2026-06-01",
         "source": "src", "angle": "a"},
        {"societe": "Frais", "type": "levee_de_fonds", "signal": "s", "date": "2026-07-06",
         "source": "src", "angle": "a"},
    ])
    md = report.render(data)
    assert md.index("**Frais**") < md.index("**Vieux**")


def test_donnees_reelles_valides():
    data = json.loads((TERRAIN / "velyx_signals.json").read_text())
    assert len(data["signaux"]) >= 10
    md = report.render(data)
    assert md.count("|") > 30  # tableaux rendus
    assert "hello@velyx.org" in md
