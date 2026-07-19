"""Configuration des dimensions, objectifs et actions.

Les dimensions ne sont pas codées en dur : clients/revenus/qualité n'est
que la configuration par défaut. Sommeil, sport, ventes, apprentissage —
n'importe quel jeu de dimensions se déclare dans un JSON :

{
  "objective": {"sommeil": 8, "sport": 5},
  "initial":   {"sommeil": 6, "sport": 1},
  "energy": 100,
  "actions": [
    {"name": "coucher 22h", "gradients": {"sommeil": 0.5}, "cost": 2,
     "risk": 0, "description": "…"}
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_cos.state import Action, Objective, SystemState

DEFAULT_CONFIG: dict = {
    "objective": {"clients": 10, "revenus": 5000, "qualite": 8},
    "initial": {"clients": 2, "revenus": 800, "qualite": 5},
    "energy": 100.0,
    "actions": [
        {
            "name": "prospection ciblée",
            "gradients": {"clients": 1.2, "revenus": 150},
            "cost": 4,
            "risk": 0.5,
            "description": "Contacter 5 prospects qualifiés",
        },
        {
            "name": "offre premium",
            "gradients": {"revenus": 600, "qualite": 0.2},
            "cost": 5,
            "risk": 1.0,
            "description": "Lancer une offre à plus forte marge",
        },
        {
            "name": "amélioration produit",
            "gradients": {"qualite": 0.6, "clients": 0.3},
            "cost": 3,
            "risk": 0.2,
            "description": "Corriger le principal irritant client",
        },
        {"name": "repos", "gradients": {}, "cost": 1.0, "description": "Récupération"},
    ],
}


class ConfigError(ValueError):
    """Configuration invalide — message actionnable, pas de crash obscur."""


def parse_config(raw: dict) -> tuple[Objective, SystemState, list[Action]]:
    """Valide et matérialise une configuration."""
    targets = raw.get("objective")
    if not targets:
        raise ConfigError("« objective » manquant ou vide : au moins une dimension cible.")
    try:
        objective = Objective(targets={k: float(v) for k, v in targets.items()})
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Objectif invalide : {exc}") from exc

    initial = raw.get("initial", {})
    unknown = set(initial) - set(targets)
    if unknown:
        raise ConfigError(
            f"Dimensions initiales inconnues de l'objectif : {sorted(unknown)}"
        )
    values = {dim: float(initial.get(dim, 0.0)) for dim in targets}
    state = SystemState(values=values, energy=float(raw.get("energy", 100.0)))

    actions = []
    for spec in raw.get("actions", []):
        if "name" not in spec:
            raise ConfigError(f"Action sans nom : {spec}")
        bad_dims = set(spec.get("gradients", {})) - set(targets)
        if bad_dims:
            raise ConfigError(
                f"Action « {spec['name']} » : gradients sur des dimensions "
                f"inconnues {sorted(bad_dims)}"
            )
        actions.append(
            Action(
                name=spec["name"],
                gradients={k: float(v) for k, v in spec.get("gradients", {}).items()},
                cost=float(spec.get("cost", 1.0)),
                risk=float(spec.get("risk", 0.0)),
                description=spec.get("description", ""),
            )
        )
    if not actions:
        raise ConfigError("Aucune action déclarée : la boucle n'a rien à proposer.")
    return objective, state, actions


def load_config(path: str | Path | None = None) -> tuple[Objective, SystemState, list[Action]]:
    """Charge un JSON de configuration ; sans chemin, la configuration par défaut."""
    if path is None:
        return parse_config(DEFAULT_CONFIG)
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"Configuration introuvable : {file}")
    try:
        raw = json.loads(file.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration illisible ({file}) : {exc}") from exc
    return parse_config(raw)
