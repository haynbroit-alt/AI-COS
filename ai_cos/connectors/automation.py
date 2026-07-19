"""Automation Engine — exécution + contrôle post-action.

Registre de connecteurs (GitHub, CRM, mail, API…). Chaque exécution
retourne les deltas RÉELLEMENT mesurés par dimension : Mesure > Intuition.

Le prototype embarque un connecteur simulé déterministe pour prouver
la boucle de bout en bout avant de brancher le monde réel.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Protocol

from ai_cos.state import Action, SystemState

# Un connecteur exécute une action et retourne les deltas mesurés.
Connector = Callable[[SystemState, Action, float], dict[str, float]]


@dataclass
class ExecutionRecord:
    action: str
    connector: str
    lever: float
    deltas: dict[str, float]


class AutomationEngine:
    """Route chaque action vers son connecteur et garde la trace des mesures."""

    def __init__(self, default_connector: Connector | None = None) -> None:
        self.connectors: dict[str, Connector] = {}
        self.default_connector = default_connector
        self.log: list[ExecutionRecord] = []

    def register(self, action_name: str, connector: Connector) -> None:
        self.connectors[action_name] = connector

    def execute(self, state: SystemState, action: Action, lever: float) -> dict[str, float]:
        connector = self.connectors.get(action.name, self.default_connector)
        if connector is None:
            raise KeyError(
                f"Aucun connecteur pour « {action.name} » et pas de connecteur par défaut."
            )
        deltas = connector(state, action, lever)
        self.log.append(
            ExecutionRecord(
                action=action.name,
                connector=getattr(connector, "name", connector.__class__.__name__),
                lever=lever,
                deltas=dict(deltas),
            )
        )
        return deltas


@dataclass
class SimulatedConnector:
    """Connecteur simulé : applique les gradients déclarés × levier, avec un
    bruit optionnel reproductible (seed) pour tester la robustesse."""

    noise: float = 0.0
    seed: int | None = None
    name: str = "simulation"
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def __call__(self, state: SystemState, action: Action, lever: float) -> dict[str, float]:
        deltas: dict[str, float] = {}
        for dim, grad in action.gradients.items():
            jitter = self._rng.uniform(-self.noise, self.noise) if self.noise else 0.0
            deltas[dim] = grad * lever * (1.0 + jitter)
        return deltas
