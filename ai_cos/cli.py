"""CLI quotidien — 60 secondes par jour, 1 suggestion, choix utilisateur.

Usage : python -m ai_cos.cli
  [a] accepter la suggestion   [1-9] choisir une alternative
  [s] passer (repos)           [q] quitter

L'état et la mémoire sont persistés dans .ai_cos/ pour continuer demain.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_cos.connectors import AutomationEngine, SimulatedConnector
from ai_cos.demo import build_scenario
from ai_cos.state import REST, SystemState
from ai_cos.views import CosmicView, OperationsView

DATA_DIR = Path(".ai_cos")
STATE_FILE = DATA_DIR / "state.json"
MEMORY_FILE = DATA_DIR / "memory.json"


def main() -> None:
    engine, state, actions, automation = build_scenario()

    DATA_DIR.mkdir(exist_ok=True)
    if STATE_FILE.exists():
        saved = json.loads(STATE_FILE.read_text())
        state = SystemState(values=saved["values"], energy=saved["energy"])
        # Progression du moteur : sans elle, le compteur de cycles repartirait
        # à zéro chaque jour et le levier/anti-stagnation (3 cycles d'historique)
        # ne pourraient jamais s'activer en usage quotidien.
        engine.cycle_count = saved.get("cycle_count", 0)
        engine.gap_history.extend(saved.get("gap_history", []))
        engine.state_history.extend(saved.get("state_history", []))
    if MEMORY_FILE.exists():
        engine.memory.load(MEMORY_FILE)

    print(CosmicView.render(engine, state))
    print(OperationsView.render(engine, state))

    suggestion = engine.suggest(state, actions)
    print()
    print(suggestion.describe())
    print("\n[a] accepter  [1-9] alternative  [s] repos  [q] quitter")
    choice = input("> ").strip().lower()

    if choice == "q":
        return
    if choice == "s":
        action, chosen = REST, True
    elif choice.isdigit() and 1 <= int(choice) <= len(suggestion.alternatives):
        action, chosen = suggestion.alternatives[int(choice) - 1], True
    else:
        action, chosen = suggestion.action, True

    report = engine.run_cycle(state, action, chosen_by_user=chosen, execute=automation.execute)
    print(f"\nCycle {report.cycle} : écart {report.gap_before:.2f} → {report.gap_after:.2f}")
    print(CosmicView.render(engine, state))

    STATE_FILE.write_text(
        json.dumps(
            {
                "values": state.values,
                "energy": state.energy,
                "cycle_count": engine.cycle_count,
                "gap_history": list(engine.gap_history),
                "state_history": list(engine.state_history),
            }
        )
    )
    engine.memory.save(MEMORY_FILE)
    print(f"\nÉtat sauvegardé dans {DATA_DIR}/ — à demain (60 secondes).")


if __name__ == "__main__":
    main()
