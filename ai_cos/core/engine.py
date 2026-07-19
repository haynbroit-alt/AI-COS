"""AI-COS Engine — boucle V9 Dual à 7 phases.

ÉCART → CAUSE → PRIORITÉ → PREMIER PAS → ACTION → MESURE → APPRENTISSAGE

Modèle mathématique (version finale corrigée) :
- Écart pondéré      E_t = sqrt(Σ w_i·(s_i − o_i)²)
- Énergie            R_{t+1} = R_t − γ·c(a) + δ·max(0, E_t − E_{t+1})
- Levier             L_t = 1 + (μ−1)·1{Var(E) < ε ∧ R > seuil ∧ aucun écart catastrophique}
- Anti-stagnation    dimension figée 3 cycles → action au gradient max pour elle

Mode suggestion : le moteur propose, l'utilisateur choisit. Jamais de bascule forcée.

Règle bloquante : la boucle est verrouillée en V9. Toute modification est
refusée tant que le prototype n'a pas prouvé un échec mesuré sur 30 jours.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from ai_cos.brain.memory import MemoryEngine, Skill
from ai_cos.core.state import Action, Objective, SystemState


class LoopLockedError(RuntimeError):
    """Levée quand on tente de modifier la boucle V9 sans preuve suffisante."""


@dataclass
class LoopLock:
    """Règle bloquante — pas de V10/V11 avant preuve prototype.

    Seule exception : un échec mesuré sur au moins 30 jours de prototype.
    """

    version: str = "V9"
    modification_attempts: int = 0
    modifications_applied: int = 0

    def request_modification(
        self, reason: str, days_measured: int = 0, measured_failure: bool = False
    ) -> None:
        self.modification_attempts += 1
        if days_measured < 30 or not measured_failure:
            raise LoopLockedError(
                f"Boucle {self.version} verrouillée — refus automatique : « {reason} ». "
                f"Exception uniquement sur échec mesuré ≥ 30 jours "
                f"(reçu : {days_measured} jours, échec mesuré = {measured_failure})."
            )
        self.modifications_applied += 1


@dataclass
class Suggestion:
    """Le moteur propose ; l'utilisateur garde le contrôle.

    Le moteur reste mathématique ; la suggestion parle le langage
    utilisateur : quel est le problème, que faire, pourquoi, avec quelle
    confiance — fondée sur les essais réels de la base de connaissances.
    """

    action: Action
    rationale: str
    problem: str = ""
    confidence: float = 0.5
    basis: str = ""
    alternatives: list[Action] = field(default_factory=list)
    lever_active: bool = False
    forced_by_stagnation: str | None = None

    def describe(self) -> str:
        lines = [
            f"Problème  : {self.problem}" if self.problem else None,
            f"Action    : « {self.action.name} »"
            + (f" — {self.action.description}" if self.action.description else ""),
            f"Pourquoi  : {self.rationale}",
            f"Confiance : {self.confidence:.0%} ({self.basis})" if self.basis else None,
        ]
        if self.forced_by_stagnation:
            lines.append(
                f"Diversification anti-stagnation : dimension "
                f"« {self.forced_by_stagnation} » figée depuis 3 cycles."
            )
        if self.lever_active:
            lines.append("Levier actif : 3 cycles stables + énergie > seuil.")
        if self.alternatives:
            names = ", ".join(a.name for a in self.alternatives)
            lines.append(f"Alternatives : {names}")
        return "\n".join(line for line in lines if line)


@dataclass
class CycleReport:
    """Trace complète d'un cycle — chaque phase laisse une preuve."""

    cycle: int
    gap_before: float
    gap_after: float
    cause: str
    action: Action
    chosen_by_user: bool
    lever: float
    energy_before: float
    energy_after: float
    deltas: dict[str, float]
    skill: Skill

    @property
    def gap_reduced(self) -> bool:
        return self.gap_after < self.gap_before


class AICOSEngine:
    """Chef d'orchestre : observe, analyse, propose, mesure, apprend."""

    def __init__(
        self,
        objective: Objective,
        memory: MemoryEngine,
        gamma: float = 1.0,
        delta: float = 0.5,
        mu: float = 2.0,
        stability_epsilon: float = 0.5,
        energy_threshold: float = 40.0,
        max_relative_gap: float = 0.5,
        stagnation_tau: float = 0.01,
        energy_cap: float = 100.0,
    ) -> None:
        self.objective = objective
        self.memory = memory
        self.gamma = gamma
        self.delta = delta
        self.mu = mu
        self.stability_epsilon = stability_epsilon
        self.energy_threshold = energy_threshold
        self.max_relative_gap = max_relative_gap
        self.stagnation_tau = stagnation_tau
        self.energy_cap = energy_cap
        self.lock = LoopLock()
        self.cycle_count = 0
        self.gap_history: deque[float] = deque(maxlen=10)
        self.state_history: deque[dict[str, float]] = deque(maxlen=10)
        self.reports: list[CycleReport] = []

    # --- Phase 1 : ÉCART --------------------------------------------------

    def weighted_gap(self, state: SystemState) -> float:
        """E_t = sqrt(Σ w_i·(s_i − o_i)²)."""
        total = 0.0
        for dim in self.objective.dimensions:
            w = self.memory.weights[dim]
            diff = state.values[dim] - self.objective.targets[dim]
            total += w * diff * diff
        return math.sqrt(total)

    # --- Phase 2 : CAUSE --------------------------------------------------

    def identify_cause(self, state: SystemState) -> str:
        """Cause racine = la dimension sous-objectif au plus fort écart relatif."""
        worst_dim, worst_gap = None, -1.0
        for dim in self.objective.dimensions:
            if state.is_below(dim, self.objective):
                gap = state.relative_gap(dim, self.objective)
                if gap > worst_gap:
                    worst_dim, worst_gap = dim, gap
        if worst_dim is None:
            return "aucune dimension sous-objectif"
        return f"dimension « {worst_dim} » à {worst_gap:.0%} sous l'objectif"

    # --- Levier -----------------------------------------------------------

    def lever(self, state: SystemState) -> float:
        """L_t = 1 + (μ−1) si stabilité 3 cycles ∧ énergie > seuil ∧ aucun écart catastrophique."""
        if len(self.gap_history) < 3:
            return 1.0
        last3 = list(self.gap_history)[-3:]
        mean = sum(last3) / 3
        variance = sum((g - mean) ** 2 for g in last3) / 3
        stable = variance < self.stability_epsilon
        energized = state.energy > self.energy_threshold
        no_catastrophe = all(
            state.relative_gap(d, self.objective) < self.max_relative_gap
            for d in self.objective.dimensions
        )
        if stable and energized and no_catastrophe:
            return self.mu
        return 1.0

    # --- Anti-stagnation --------------------------------------------------

    def stagnant_dimension(self, state: SystemState) -> str | None:
        """Dimension sous-objectif dont la variation < τ·o_i sur 3 cycles."""
        if len(self.state_history) < 3:
            return None
        past = self.state_history[-3]
        for dim in self.objective.dimensions:
            if not state.is_below(dim, self.objective):
                continue
            moved = abs(state.values[dim] - past[dim])
            if moved < self.stagnation_tau * self.objective.targets[dim]:
                return dim
        return None

    # --- Phase 3 : PRIORITÉ (mode suggestion) -----------------------------

    def expected_impact(self, state: SystemState, action: Action, lever: float) -> float:
        """Réduction d'écart projetée si l'action est exécutée (world model)."""
        effects = self.memory.predict(action)
        projected = state.copy()
        for dim, grad in effects.items():
            if dim in projected.values:
                projected.values[dim] += grad * lever
        return self.weighted_gap(state) - self.weighted_gap(projected)

    def score(self, state: SystemState, action: Action, lever: float) -> float:
        """impact attendu / (coût + risque) — une seule action, le plus grand levier."""
        impact = self.expected_impact(state, action, lever)
        return impact / (action.cost + action.risk)

    def suggest(self, state: SystemState, actions: list[Action]) -> Suggestion:
        """Le moteur propose UNE action ; l'utilisateur décide. Pas de bascule forcée."""
        if not actions:
            raise ValueError("Aucune action candidate")
        lever = self.lever(state)
        stagnant = self.stagnant_dimension(state)

        if stagnant is not None:
            # Diversification forcée par gradient : a = argmax ∂s_i/∂a
            best = max(actions, key=lambda a: self.memory.predict(a).get(stagnant, 0.0))
            rationale = (
                f"plus fort gradient sur « {stagnant} » "
                f"(+{self.memory.predict(best).get(stagnant, 0.0):.2f} attendu)"
            )
            others = [a for a in actions if a is not best]
        else:
            ranked = sorted(actions, key=lambda a: self.score(state, a, lever), reverse=True)
            best, others = ranked[0], ranked[1:]
            rationale = (
                f"meilleur ratio impact/coût "
                f"(impact projeté {self.expected_impact(state, best, lever):.2f}, "
                f"coût {best.cost:.0f})"
            )
        knowledge = self.memory.knowledge_for(best.name)
        return Suggestion(
            action=best,
            rationale=rationale,
            problem=self.identify_cause(state),
            confidence=knowledge.confidence,
            basis=knowledge.basis(),
            alternatives=others[:3],
            lever_active=lever > 1.0,
            forced_by_stagnation=stagnant,
        )

    # --- Phases 4-7 : PREMIER PAS → ACTION → MESURE → APPRENTISSAGE ------

    def run_cycle(
        self,
        state: SystemState,
        action: Action,
        chosen_by_user: bool,
        execute: "callable[[SystemState, Action, float], dict[str, float]]",
    ) -> CycleReport:
        """Exécute un cycle complet sur l'action retenue (par l'utilisateur).

        `execute(state, action, lever)` réalise l'action dans le monde réel
        (Automation Engine ou Claude Code Connector) et retourne les deltas
        réellement mesurés par dimension.
        """
        self.cycle_count += 1
        gap_before = self.weighted_gap(state)
        cause = self.identify_cause(state)
        lever = self.lever(state)
        energy_before = state.energy

        # ACTION : exécution réelle, MESURE : deltas observés
        deltas = execute(state, action, lever)
        for dim, d in deltas.items():
            if dim in state.values:
                state.values[dim] += d

        gap_after = self.weighted_gap(state)

        # Énergie : dépense obligatoire, récupération seulement si l'écart baisse,
        # bornée par un plafond — pas d'énergie fantôme, dans aucun sens.
        state.energy = min(
            self.energy_cap,
            state.energy
            - self.gamma * action.cost
            + self.delta * max(0.0, gap_before - gap_after),
        )

        # APPRENTISSAGE : poids, world model, skill
        self.memory.update_weights(state)
        self.memory.observe_effect(action.name, deltas)
        skill = Skill(
            action=action.name,
            context=cause,
            gap_before=gap_before,
            gap_after=gap_after,
            cycle=self.cycle_count,
        )
        self.memory.learn(skill)

        self.gap_history.append(gap_after)
        self.state_history.append(dict(state.values))

        report = CycleReport(
            cycle=self.cycle_count,
            gap_before=gap_before,
            gap_after=gap_after,
            cause=cause,
            action=action,
            chosen_by_user=chosen_by_user,
            lever=lever,
            energy_before=energy_before,
            energy_after=state.energy,
            deltas=deltas,
            skill=skill,
        )
        self.reports.append(report)
        return report
