"""État du système : dimensions, objectif, énergie, actions.

S_t = (s_1, ..., s_n), O = vecteur cible, R = réserve d'énergie.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Objective:
    """Vecteur cible O. Chaque dimension a une valeur cible strictement positive."""

    targets: dict[str, float]

    def __post_init__(self) -> None:
        for name, value in self.targets.items():
            if value <= 0:
                raise ValueError(f"Objectif '{name}' doit être > 0 (reçu {value})")

    @property
    def dimensions(self) -> list[str]:
        return list(self.targets)


@dataclass
class SystemState:
    """État courant S_t + réserve d'énergie R_t."""

    values: dict[str, float]
    energy: float = 100.0

    def copy(self) -> "SystemState":
        return SystemState(values=dict(self.values), energy=self.energy)

    def relative_gap(self, dim: str, objective: Objective) -> float:
        """Écart relatif |s_i - o_i| / o_i."""
        target = objective.targets[dim]
        return abs(self.values[dim] - target) / target

    def is_below(self, dim: str, objective: Objective) -> bool:
        return self.values[dim] < objective.targets[dim]


@dataclass
class Action:
    """Action candidate.

    gradients : effet attendu par exécution sur chaque dimension (∂s_i/∂a).
    cost : coût énergétique c(a) — toujours >= 1, même le repos (pas d'énergie fantôme).
    risk : pénalité de risque utilisée dans le score de priorité.
    """

    name: str
    gradients: dict[str, float] = field(default_factory=dict)
    cost: float = 1.0
    risk: float = 0.0
    description: str = ""

    def __post_init__(self) -> None:
        if self.cost < 1.0:
            # Dépense obligatoire : toute action consomme au moins 1 point.
            self.cost = 1.0

    def gradient_for(self, dim: str) -> float:
        return self.gradients.get(dim, 0.0)


REST = Action(name="repos", gradients={}, cost=1.0, description="Récupération — coûte quand même 1 point")
