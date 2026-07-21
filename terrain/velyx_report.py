"""Rapport Signaux Velyx — le livrable produit, généré depuis velyx_signals.json.

C'est LA démo promise dans l'outreach (« 15 min suffisent à vous montrer ») :
des comptes français avec un signal d'achat daté, sourcé et un angle
d'approche. Rendu en markdown, envoyable tel quel à un prospect qui répond.

Usage :
    python3 terrain/velyx_report.py            # écrit terrain/velyx-rapport-demo.md
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
SIGNALS_PATH = HERE / "velyx_signals.json"
REPORT_PATH = HERE / "velyx-rapport-demo.md"

TYPE_LABELS = {
    "recrutement_sales": "Recrutement commercial actif — la génération de leads est budgétée",
    "levee_de_fonds": "Levée de fonds récente — budget frais, pression de croissance",
}


def render(data: dict) -> str:
    """Rendu markdown pur du rapport à partir des signaux structurés."""
    lines = [
        "# Velyx — Rapport Signaux (échantillon réel)",
        "",
        f"Généré le {data['genere_le']} à partir de sources publiques uniquement.",
        "Chaque ligne = un compte français avec un signal d'achat daté, sourcé,",
        "et un angle d'approche prêt à l'emploi.",
        "",
    ]
    signaux = data.get("signaux", [])
    for type_key, label in TYPE_LABELS.items():
        group = [s for s in signaux if s["type"] == type_key]
        if not group:
            continue
        group.sort(key=lambda s: s["date"], reverse=True)
        lines += [f"## {label}", ""]
        lines += ["| Société | Signal | Date | Source |", "|---|---|---|---|"]
        for s in group:
            lines.append(f"| **{s['societe']}** | {s['signal']} | {s['date']} | {s['source']} |")
        lines.append("")
        for s in group:
            lines.append(f"- **{s['societe']}** — {s['angle']}")
        lines.append("")
    lines += [
        "---",
        "",
        "*Échantillon générique. En prestation, les signaux sont filtrés sur VOTRE",
        "ICP (secteur, taille, géographie) et livrés chaque semaine avec les",
        "contacts décideurs. — Velyx, hello@velyx.org*",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    data = json.loads(SIGNALS_PATH.read_text())
    REPORT_PATH.write_text(render(data))
    print(f"Rapport écrit : {REPORT_PATH} ({len(data.get('signaux', []))} signaux)")


if __name__ == "__main__":
    main()
