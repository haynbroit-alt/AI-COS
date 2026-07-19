"""Démonstration prototype — 10 cycles complets, 0 modification de boucle.

Scénario : atteindre 10 clients payants, 5000 de revenus, qualité 8/10,
en gérant l'énergie. Chaque cycle suit les 6 étapes du prototype :

1. AI-COS Engine observe les données      → détecte l'écart réel
2. Prépare la mission                      → claire, exécutable
3. Exécution (Automation / Claude Code)   → livrable livré
4. Automation Engine contrôle              → métrique post-action
5. Memory Engine apprend                   → skill stocké, réutilisable
6. Cosmic/Operations View affichent        → l'utilisateur voit le résultat

Mode suggestion : ici l'« utilisateur » accepte chaque suggestion (simulation),
mais le choix reste structurellement le sien — voir cli.py pour le mode interactif.

Usage : python -m ai_cos.demo
"""

from __future__ import annotations

from ai_cos.connectors import AutomationEngine, ClaudeCodeConnector, SimulatedConnector
from ai_cos.engine import AICOSEngine
from ai_cos.memory import MemoryEngine
from ai_cos.state import Action, Objective, SystemState, REST
from ai_cos.views import CosmicView, OperationsView


def build_scenario() -> tuple[AICOSEngine, SystemState, list[Action], AutomationEngine]:
    objective = Objective(targets={"clients": 10, "revenus": 5000, "qualite": 8})
    state = SystemState(values={"clients": 2, "revenus": 800, "qualite": 5}, energy=100.0)
    memory = MemoryEngine(objective)
    engine = AICOSEngine(objective, memory)

    actions = [
        Action(
            name="prospection ciblée",
            gradients={"clients": 1.2, "revenus": 150},
            cost=4,
            risk=0.5,
            description="Contacter 5 prospects qualifiés",
        ),
        Action(
            name="offre premium",
            gradients={"revenus": 600, "qualite": 0.2},
            cost=5,
            risk=1.0,
            description="Lancer une offre à plus forte marge",
        ),
        Action(
            name="amélioration produit",
            gradients={"qualite": 0.6, "clients": 0.3},
            cost=3,
            risk=0.2,
            description="Corriger le principal irritant client",
        ),
        REST,
    ]

    automation = AutomationEngine(default_connector=SimulatedConnector(noise=0.1, seed=42))
    return engine, state, actions, automation


def run_prototype(cycles: int = 10, verbose: bool = True) -> AICOSEngine:
    engine, state, actions, automation = build_scenario()
    claude = ClaudeCodeConnector()

    for _ in range(cycles):
        # 1-2. Observer + préparer : le moteur suggère, l'utilisateur choisit
        suggestion = engine.suggest(state, actions)
        mission = claude.prepare_mission(
            objectif=f"Réduire l'écart global (E = {engine.weighted_gap(state):.2f})",
            probleme=engine.identify_cause(state),
            cause=engine.identify_cause(state),
            action=f"{suggestion.action.name} — {suggestion.action.description}",
            contraintes=["une seule action", "60 secondes de décision", "boucle V9 intouchable"],
            critere="l'écart pondéré E diminue au prochain relevé",
            test="comparer E avant/après via l'Automation Engine",
        )
        claude.dispatch(mission)

        # 3-5. Exécuter, contrôler, apprendre (l'utilisateur accepte la suggestion)
        report = engine.run_cycle(
            state, suggestion.action, chosen_by_user=True, execute=automation.execute
        )

        # 6. Afficher
        if verbose:
            print(f"\n──────── CYCLE {report.cycle} ────────")
            print(suggestion.describe())
            print(CosmicView.render(engine, state))
            print(OperationsView.render(engine, state))

    if verbose:
        print("\n═══ BILAN PROTOTYPE ═══")
        first, last = engine.reports[0], engine.reports[-1]
        print(f"Cycles complets        : {engine.cycle_count}")
        print(f"Écart global           : {first.gap_before:.2f} → {last.gap_after:.2f}")
        print(f"Skills appris          : {len(engine.memory.skills)}")
        print(f"Missions dispatchées   : {len(claude.dispatched)}")
        print(f"Modifications de boucle: {engine.lock.modifications_applied} (règle bloquante respectée)")
    return engine


if __name__ == "__main__":
    run_prototype()
