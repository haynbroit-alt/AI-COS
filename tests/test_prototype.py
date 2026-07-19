"""Preuve prototype : 10 cycles complets, écart qui converge, 0 modification de boucle.

C'est le critère de succès de la spec V9 :
« Métrique succès : 10 cycles complets, 0 modification boucle. »
"""

import json

from ai_cos.product.demo import build_scenario, run_prototype
from ai_cos.brain.memory import MemoryEngine
from ai_cos.core.state import Objective, SystemState
from ai_cos.product.views import CosmicView, OperationsView


def test_ten_full_cycles_zero_loop_modifications():
    engine = run_prototype(cycles=10, verbose=False)
    assert engine.cycle_count == 10
    assert engine.lock.modifications_applied == 0
    assert len(engine.memory.skills) == 10  # un skill stocké par cycle


def test_global_gap_converges():
    engine = run_prototype(cycles=10, verbose=False)
    first_gap = engine.reports[0].gap_before
    last_gap = engine.reports[-1].gap_after
    assert last_gap < first_gap * 0.5  # l'écart a au moins été divisé par deux


def test_no_dimension_sacrificed():
    """Équilibre : les revenus ne décollent pas au détriment des clients."""
    engine, state, actions, automation = build_scenario()
    start = dict(state.values)
    for _ in range(10):
        suggestion = engine.suggest(state, actions)
        engine.run_cycle(state, suggestion.action, chosen_by_user=True, execute=automation.execute)
    for dim in engine.objective.dimensions:
        assert state.values[dim] >= start[dim]  # aucune dimension ne régresse


def test_energy_stays_positive_over_ten_cycles():
    engine, state, actions, automation = build_scenario()
    for _ in range(10):
        suggestion = engine.suggest(state, actions)
        engine.run_cycle(state, suggestion.action, chosen_by_user=True, execute=automation.execute)
        assert state.energy > 0  # énergie durable > effort temporaire


def test_views_render_without_error():
    engine, state, actions, automation = build_scenario()
    suggestion = engine.suggest(state, actions)
    engine.run_cycle(state, suggestion.action, chosen_by_user=True, execute=automation.execute)
    cosmic = CosmicView.render(engine, state)
    ops = OperationsView.render(engine, state)
    assert "COSMIC VIEW" in cosmic and "V9" in cosmic
    assert "OPERATIONS VIEW" in ops and "clients" in ops


def test_memory_persistence_roundtrip(tmp_path):
    objective = Objective(targets={"clients": 10})
    memory = MemoryEngine(objective)
    state = SystemState(values={"clients": 2})
    memory.update_weights(state)
    memory.observe_effect("prospection", {"clients": 0.8})
    path = tmp_path / "memory.json"
    memory.save(path)

    restored = MemoryEngine(objective)
    restored.load(path)
    assert restored.weights == memory.weights
    assert restored.observed_effects == memory.observed_effects
    assert json.loads(path.read_text())  # JSON valide


def test_every_report_traces_user_choice():
    """Suggestion, pas imposition : chaque cycle trace qui a décidé."""
    engine = run_prototype(cycles=10, verbose=False)
    assert all(r.chosen_by_user for r in engine.reports)
