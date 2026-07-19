"""CLI quotidien — 60 secondes par jour, 1 suggestion, choix utilisateur.

Usage :
  python -m ai_cos.cli                          # mode simulation (démo)
  python -m ai_cos.cli --source journal.json    # mode RÉEL : journal JSON
  python -m ai_cos.cli --source stripe          # mode RÉEL : API Stripe

  [a] accepter la suggestion   [1-9] choisir une alternative
  [s] passer (repos)           [q] quitter

Mode réel = mesure différée : l'action décidée aujourd'hui est exécutée dans
le monde (par vous ou l'Automation Engine) ; ses effets sont mesurés demain
matin au relevé de la source (deltas = observé − état d'hier). Le simulateur,
lui, applique les effets immédiatement — c'est toute la différence entre
simulation et production (règle 6).

L'état et la mémoire sont persistés dans .ai_cos/ pour continuer demain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_cos.demo import build_scenario
from ai_cos.sources import DataSource, DataSourceError, JsonFileSource, StripeSource, measure_since
from ai_cos.state import REST, SystemState
from ai_cos.views import CosmicView, OperationsView

DATA_DIR = Path(".ai_cos")
STATE_FILE = DATA_DIR / "state.json"
MEMORY_FILE = DATA_DIR / "memory.json"


def make_source(spec: str | None) -> DataSource | None:
    if spec is None:
        return None
    if spec == "stripe":
        return StripeSource()
    return JsonFileSource(path=spec)


def load_progress(engine, state: SystemState) -> str | None:
    """Restaure état + progression moteur. Retourne l'action en attente (mode réel)."""
    pending = None
    if STATE_FILE.exists():
        saved = json.loads(STATE_FILE.read_text())
        state.values.update(saved["values"])
        state.energy = saved["energy"]
        # Progression du moteur : sans elle, le compteur de cycles repartirait
        # à zéro chaque jour et le levier/anti-stagnation (3 cycles d'historique)
        # ne pourraient jamais s'activer en usage quotidien.
        engine.cycle_count = saved.get("cycle_count", 0)
        engine.gap_history.extend(saved.get("gap_history", []))
        engine.state_history.extend(saved.get("state_history", []))
        pending = saved.get("pending_action")
    if MEMORY_FILE.exists():
        engine.memory.load(MEMORY_FILE)
    return pending


def save_progress(engine, state: SystemState, pending_action: str | None) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "values": state.values,
                "energy": state.energy,
                "cycle_count": engine.cycle_count,
                "gap_history": list(engine.gap_history),
                "state_history": list(engine.state_history),
                "pending_action": pending_action,
            }
        )
    )
    engine.memory.save(MEMORY_FILE)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Boucle quotidienne AI-COS")
    parser.add_argument(
        "--source",
        default=None,
        help="Source réelle : chemin d'un journal JSON, ou « stripe » (STRIPE_API_KEY requis)",
    )
    args = parser.parse_args(argv)

    engine, state, actions, automation = build_scenario()
    actions_by_name = {a.name: a for a in actions}
    try:
        source = make_source(args.source)
    except DataSourceError as exc:
        print(f"Erreur source : {exc}")
        sys.exit(1)

    DATA_DIR.mkdir(exist_ok=True)
    pending = load_progress(engine, state)

    if source is not None:
        print(f"Mode RÉEL — source : {source.name}")
        try:
            observed = source.observe()
        except DataSourceError as exc:
            print(f"Erreur source : {exc}")
            sys.exit(1)
        if pending and pending in actions_by_name:
            # MESURE différée : le relevé de ce matin solde l'action d'hier.
            measure = measure_since(state.values, observed)
            report = engine.run_cycle(
                state, actions_by_name[pending], chosen_by_user=True, execute=measure
            )
            # Sauvegarde immédiate : une mesure faite ne doit jamais être
            # perdue, même si le processus meurt avant la fin de la session.
            save_progress(engine, state, pending_action=None)
            print(
                f"Mesure réelle de « {report.action.name} » (décidée hier) : "
                f"écart {report.gap_before:.2f} → {report.gap_after:.2f}, "
                f"deltas {measure.deltas}"
            )
        else:
            # Première synchronisation : la réalité remplace l'état supposé.
            tracked = {d: v for d, v in observed.items() if d in state.values}
            state.values.update(tracked)
            print(f"État synchronisé sur la réalité : {tracked}")
    else:
        print("Mode SIMULATION (aucune source réelle — voir --source)")

    print(CosmicView.render(engine, state))
    print(OperationsView.render(engine, state))

    suggestion = engine.suggest(state, actions)
    print()
    print(suggestion.describe())
    print("\n[a] accepter  [1-9] alternative  [s] repos  [q] quitter")
    choice = input("> ").strip().lower()

    if choice == "q":
        save_progress(engine, state, pending_action=None)
        return
    if choice == "s":
        action = REST
    elif choice.isdigit() and 1 <= int(choice) <= len(suggestion.alternatives):
        action = suggestion.alternatives[int(choice) - 1]
    else:
        action = suggestion.action

    if source is not None:
        # Mode réel : l'action part dans le monde ; mesure demain matin.
        print(f"\nAction retenue : « {action.name} » — {action.description or 'à exécuter'}")
        print("Exécutez-la aujourd'hui ; la mesure se fera au prochain relevé.")
        save_progress(engine, state, pending_action=action.name)
    else:
        report = engine.run_cycle(state, action, chosen_by_user=True, execute=automation.execute)
        print(f"\nCycle {report.cycle} : écart {report.gap_before:.2f} → {report.gap_after:.2f}")
        print(CosmicView.render(engine, state))
        save_progress(engine, state, pending_action=None)

    print(f"\nÉtat sauvegardé dans {DATA_DIR}/ — à demain (60 secondes).")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Sortie tronquée (ex. | head) : l'état mesuré est déjà sauvegardé.
        sys.exit(0)
