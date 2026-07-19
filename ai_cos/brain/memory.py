"""Memory Engine (Mémoire #2) — apprentissage partagé.

- Poids dynamiques w_i(t) : normalisation par écart relatif, renforcement
  seulement si la dimension est sous-objectif, oubli β contre la saturation.
- World model discret : « si je fais A, probablement B » — effets observés
  des actions, qui remplacent progressivement les gradients déclarés
  (Loi 1 : Réalité > Hypothèse).
- Skills : chaque cycle réussi devient une règle réutilisable.
- Persistance JSON pour survivre entre les sessions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ai_cos.core.state import Action, Objective, SystemState


@dataclass
class ActionKnowledge:
    """Connaissance accumulée sur une action — au-delà de « action → résultat » :
    contextes d'usage, fréquence, taux de réussite, conditions d'échec.

    La confiance est lissée (Laplace) : une action jamais testée vaut 50 %,
    et il faut des essais répétés pour s'en éloigner — dans les deux sens.
    Le délai d'effet n'est pas encore suivi : la mesure actuelle est à J+1
    systématique ; on ne stocke pas ce qu'on ne sait pas mesurer.
    """

    action: str
    trials: int = 0
    successes: int = 0
    total_gap_reduction: float = 0.0
    contexts: dict[str, int] = field(default_factory=dict)
    failure_contexts: dict[str, int] = field(default_factory=dict)
    last_cycle: int = 0

    @property
    def confidence(self) -> float:
        return (self.successes + 1) / (self.trials + 2)

    @property
    def tested(self) -> bool:
        return self.trials > 0

    def record(self, skill: "Skill") -> None:
        self.trials += 1
        self.contexts[skill.context] = self.contexts.get(skill.context, 0) + 1
        if skill.worked:
            self.successes += 1
            self.total_gap_reduction += skill.gap_before - skill.gap_after
        else:
            self.failure_contexts[skill.context] = (
                self.failure_contexts.get(skill.context, 0) + 1
            )
        self.last_cycle = skill.cycle

    def basis(self) -> str:
        """Justification lisible : sur quoi repose la confiance."""
        if not self.tested:
            return "jamais testée en réel — estimation d'après le gradient déclaré"
        parts = [f"{self.trials} essai(s), {self.successes} réussite(s)"]
        if self.failure_contexts:
            worst = max(self.failure_contexts, key=self.failure_contexts.get)
            parts.append(f"échoue surtout quand : {worst}")
        return ", ".join(parts)


@dataclass
class Skill:
    """Règle apprise d'un cycle : contexte → action → résultat mesuré."""

    action: str
    context: str
    gap_before: float
    gap_after: float
    cycle: int

    @property
    def worked(self) -> bool:
        return self.gap_after < self.gap_before

    def as_rule(self) -> str:
        verdict = "réutiliser" if self.worked else "éviter"
        return (
            f"[cycle {self.cycle}] {self.context} → « {self.action} » : "
            f"écart {self.gap_before:.2f} → {self.gap_after:.2f} ({verdict})"
        )


class MemoryEngine:
    """Poids dynamiques + world model + skills."""

    def __init__(
        self,
        objective: Objective,
        eta: float = 0.3,
        beta: float = 0.05,
        smoothing: float = 0.5,
    ) -> None:
        self.objective = objective
        self.eta = eta          # taux d'apprentissage des poids
        self.beta = beta        # oubli (anti-saturation)
        self.smoothing = smoothing  # lissage du world model
        self.weights: dict[str, float] = {d: 1.0 for d in objective.dimensions}
        self.observed_effects: dict[str, dict[str, float]] = {}
        self.skills: list[Skill] = []
        self.knowledge: dict[str, ActionKnowledge] = {}

    # --- Poids dynamiques -------------------------------------------------

    def update_weights(self, state: SystemState) -> dict[str, float]:
        """w_i(t+1) = w_i + η·(|s_i-o_i|/o_i)·1{s_i<o_i} − β·w_i."""
        for dim in self.objective.dimensions:
            w = self.weights[dim]
            reinforcement = 0.0
            if state.is_below(dim, self.objective):
                reinforcement = self.eta * state.relative_gap(dim, self.objective)
            self.weights[dim] = max(0.1, w + reinforcement - self.beta * w)
        return dict(self.weights)

    # --- World model discret ----------------------------------------------

    def observe_effect(self, action_name: str, deltas: dict[str, float]) -> None:
        """Enregistre l'effet réel mesuré d'une action (moyenne mobile)."""
        known = self.observed_effects.setdefault(action_name, {})
        for dim, delta in deltas.items():
            if dim in known:
                known[dim] = (1 - self.smoothing) * known[dim] + self.smoothing * delta
            else:
                known[dim] = delta

    def predict(self, action: Action) -> dict[str, float]:
        """Prédiction « si je fais A, probablement B ».

        Réalité > Hypothèse : les effets observés priment sur les gradients
        déclarés ; sans observation, on retombe sur la déclaration.
        """
        observed = self.observed_effects.get(action.name)
        if observed:
            merged = dict(action.gradients)
            merged.update(observed)
            return merged
        return dict(action.gradients)

    # --- Skills -----------------------------------------------------------

    def learn(self, skill: Skill) -> None:
        self.skills.append(skill)
        knowledge = self.knowledge.setdefault(
            skill.action, ActionKnowledge(action=skill.action)
        )
        knowledge.record(skill)

    def rules(self) -> list[str]:
        return [s.as_rule() for s in self.skills]

    def knowledge_for(self, action_name: str) -> ActionKnowledge:
        return self.knowledge.get(action_name, ActionKnowledge(action=action_name))

    # --- Persistance ------------------------------------------------------

    def save(self, path: str | Path) -> None:
        payload = {
            "weights": self.weights,
            "observed_effects": self.observed_effects,
            "skills": [vars(s) for s in self.skills],
            "knowledge": {name: vars(k) for name, k in self.knowledge.items()},
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def load(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        self.weights.update(data.get("weights", {}))
        self.observed_effects = data.get("observed_effects", {})
        self.skills = [Skill(**s) for s in data.get("skills", [])]
        stored = data.get("knowledge")
        if stored is not None:
            self.knowledge = {
                name: ActionKnowledge(**payload) for name, payload in stored.items()
            }
        else:
            # Mémoire d'avant la base de connaissances : on la reconstruit en
            # rejouant les skills — aucune donnée réelle n'est perdue.
            self.knowledge = {}
            for skill in self.skills:
                self.knowledge.setdefault(
                    skill.action, ActionKnowledge(action=skill.action)
                ).record(skill)
