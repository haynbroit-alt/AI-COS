"""Tests du moteur V9 : écart, poids, énergie, levier, anti-stagnation, verrou."""

import math

import pytest

from ai_cos.engine import AICOSEngine, LoopLockedError
from ai_cos.memory import MemoryEngine
from ai_cos.state import Action, Objective, SystemState, REST


@pytest.fixture
def objective():
    return Objective(targets={"clients": 10, "revenus": 5000})


@pytest.fixture
def engine(objective):
    return AICOSEngine(objective, MemoryEngine(objective))


def noop_execute(state, action, lever):
    return {dim: g * lever for dim, g in action.gradients.items()}


def test_weighted_gap(engine):
    state = SystemState(values={"clients": 4, "revenus": 5000})
    # Seule la dimension clients contribue : sqrt(1.0 * (4-10)^2) = 6
    assert engine.weighted_gap(state) == pytest.approx(6.0)


def test_weights_reinforce_lagging_dimension_only(objective):
    memory = MemoryEngine(objective)
    state = SystemState(values={"clients": 2, "revenus": 6000})  # revenus AU-DESSUS
    before = dict(memory.weights)
    memory.update_weights(state)
    assert memory.weights["clients"] > before["clients"]      # sous-objectif → renforcé
    assert memory.weights["revenus"] < before["revenus"]      # au-dessus → seulement l'oubli β


def test_energy_mandatory_spend_even_for_rest(engine):
    state = SystemState(values={"clients": 10, "revenus": 5000}, energy=50.0)
    engine.run_cycle(state, REST, chosen_by_user=True, execute=noop_execute)
    # Repos = coût 1, écart déjà nul donc aucune récupération : pas d'énergie fantôme
    assert state.energy == pytest.approx(49.0)


def test_energy_recovers_only_if_gap_shrinks(engine):
    state = SystemState(values={"clients": 4, "revenus": 5000}, energy=50.0)
    action = Action(name="prospection", gradients={"clients": 2.0}, cost=2)
    report = engine.run_cycle(state, action, chosen_by_user=True, execute=noop_execute)
    assert report.gap_reduced
    expected = 50.0 - 1.0 * 2 + 0.5 * (report.gap_before - report.gap_after)
    assert state.energy == pytest.approx(expected)


def test_energy_capped_no_phantom_energy(engine):
    """La récupération ne peut pas dépasser le plafond, même sur un gros gain d'écart."""
    state = SystemState(values={"clients": 2, "revenus": 500}, energy=99.0)
    action = Action(name="miracle", gradients={"revenus": 4500}, cost=1)
    engine.run_cycle(state, action, chosen_by_user=True, execute=noop_execute)
    assert state.energy == engine.energy_cap


def test_lever_requires_stability_energy_and_no_catastrophe(engine):
    # Proche de l'objectif, écarts relatifs < 50 %, énergie haute
    state = SystemState(values={"clients": 9, "revenus": 4800}, energy=90.0)
    assert engine.lever(state) == 1.0  # pas encore 3 cycles d'historique
    for gap in (5.0, 5.1, 5.05):  # 3 cycles stables (variance < ε)
        engine.gap_history.append(gap)
    assert engine.lever(state) == engine.mu

    # Énergie sous le seuil → levier coupé
    state.energy = 10.0
    assert engine.lever(state) == 1.0

    # Écart catastrophique sur une dimension → levier coupé même avec énergie
    state.energy = 90.0
    state.values["clients"] = 2  # 80 % sous l'objectif
    assert engine.lever(state) == 1.0


def test_anti_stagnation_forces_max_gradient_action(engine):
    state = SystemState(values={"clients": 3, "revenus": 3000}, energy=80.0)
    # 3 cycles d'historique où « clients » n'a pas bougé
    for _ in range(3):
        engine.state_history.append({"clients": 3.0, "revenus": 2500.0})
        engine.gap_history.append(engine.weighted_gap(state))

    assert engine.stagnant_dimension(state) == "clients"

    weak = Action(name="petit pas clients", gradients={"clients": 0.1, "revenus": 900}, cost=1)
    strong = Action(name="gros pas clients", gradients={"clients": 2.0}, cost=6, risk=2)
    suggestion = engine.suggest(state, [weak, strong])
    # Malgré son coût, l'action au plus fort gradient clients est imposée en tête
    assert suggestion.action is strong
    assert suggestion.forced_by_stagnation == "clients"


def test_suggestion_not_forced_switch(engine):
    """Le moteur propose ; il retourne toujours des alternatives + rationale."""
    state = SystemState(values={"clients": 3, "revenus": 3000}, energy=80.0)
    a = Action(name="a", gradients={"clients": 1.0}, cost=2)
    b = Action(name="b", gradients={"revenus": 500}, cost=2)
    suggestion = engine.suggest(state, [a, b])
    assert suggestion.rationale
    assert len(suggestion.alternatives) == 1  # l'utilisateur peut choisir autre chose


def test_loop_locked_no_v10(engine):
    with pytest.raises(LoopLockedError):
        engine.lock.request_modification("passer en V10", days_measured=5, measured_failure=True)
    with pytest.raises(LoopLockedError):
        engine.lock.request_modification("idée géniale", days_measured=45, measured_failure=False)
    assert engine.lock.modification_attempts == 2
    assert engine.lock.modifications_applied == 0
    # Exception légitime : échec mesuré sur >= 30 jours
    engine.lock.request_modification("échec prouvé", days_measured=30, measured_failure=True)
    assert engine.lock.modifications_applied == 1


def test_world_model_overrides_declared_gradients(objective):
    """Réalité > Hypothèse : les effets observés remplacent la déclaration."""
    memory = MemoryEngine(objective, smoothing=1.0)
    action = Action(name="prospection", gradients={"clients": 5.0})
    assert memory.predict(action)["clients"] == 5.0
    memory.observe_effect("prospection", {"clients": 0.5})  # la réalité déçoit
    assert memory.predict(action)["clients"] == pytest.approx(0.5)


def test_weighted_gap_uses_dynamic_weights(objective):
    memory = MemoryEngine(objective)
    engine = AICOSEngine(objective, memory)
    state = SystemState(values={"clients": 5, "revenus": 5000})
    base = engine.weighted_gap(state)
    memory.weights["clients"] = 4.0
    assert engine.weighted_gap(state) == pytest.approx(base * math.sqrt(4.0))
