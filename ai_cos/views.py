"""Vues — Cosmic View (cap, tendance) et Operations View (détail opérationnel).

Sortie texte pure : le prototype prouve la boucle, pas le pixel.
"""

from __future__ import annotations

from ai_cos.engine import AICOSEngine
from ai_cos.state import Objective, SystemState

BAR_WIDTH = 24


def _bar(ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = round(ratio * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


class CosmicView:
    """Vue cosmique : où on va, où on en est, avec quelle énergie."""

    @staticmethod
    def render(engine: AICOSEngine, state: SystemState) -> str:
        gap = engine.weighted_gap(state)
        trend = "—"
        if len(engine.gap_history) >= 2:
            prev = list(engine.gap_history)[-2]
            trend = "↓ converge" if gap < prev else ("↑ diverge" if gap > prev else "→ stable")
        lever = engine.lever(state)
        lines = [
            "═══ COSMIC VIEW ═══",
            f"Écart global E : {gap:8.2f}   tendance : {trend}",
            f"Énergie R      : {state.energy:8.1f}   levier : {'ACTIF ×%.1f' % lever if lever > 1 else 'inactif'}",
            f"Cycles         : {engine.cycle_count:5d}      version boucle : {engine.lock.version} (verrouillée)",
        ]
        return "\n".join(lines)


class OperationsView:
    """Vue opérationnelle : dimensions, poids, dernier cycle, skills."""

    @staticmethod
    def render(engine: AICOSEngine, state: SystemState) -> str:
        objective: Objective = engine.objective
        lines = ["═══ OPERATIONS VIEW ═══", f"{'dimension':<12} {'actuel':>8} {'cible':>8} {'poids':>6}  progression"]
        for dim in objective.dimensions:
            current = state.values[dim]
            target = objective.targets[dim]
            weight = engine.memory.weights[dim]
            lines.append(
                f"{dim:<12} {current:8.1f} {target:8.1f} {weight:6.2f}  {_bar(current / target)}"
            )
        if engine.reports:
            last = engine.reports[-1]
            lines.append(
                f"Dernier cycle #{last.cycle} : « {last.action.name} » "
                f"(choix utilisateur : {'oui' if last.chosen_by_user else 'non'}) — "
                f"écart {last.gap_before:.2f} → {last.gap_after:.2f}"
            )
        if engine.memory.skills:
            lines.append(f"Skills appris : {len(engine.memory.skills)}")
            lines.append("  " + engine.memory.skills[-1].as_rule())
        return "\n".join(lines)
