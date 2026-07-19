"""Tests de la base de connaissances — cas normal / erreur / limite (règle 3).

La vraie innovation : chaque décision réelle devient une connaissance
réutilisable (contexte, fréquence, confiance, conditions d'échec).
"""

import pytest

from ai_cos.engine import AICOSEngine
from ai_cos.memory import ActionKnowledge, MemoryEngine, Skill
from ai_cos.state import Action, Objective, SystemState


@pytest.fixture
def objective():
    return Objective(targets={"clients": 10, "revenus": 5000})


def make_skill(action="prospection", context="clients en retard", before=100.0, after=80.0, cycle=1):
    return Skill(action=action, context=context, gap_before=before, gap_after=after, cycle=cycle)


# --- Cas normal -------------------------------------------------------------


def test_knowledge_accumulates_trials_contexts_and_confidence(objective):
    memory = MemoryEngine(objective)
    memory.learn(make_skill(cycle=1))                       # réussite
    memory.learn(make_skill(cycle=2, before=80, after=85))  # échec
    memory.learn(make_skill(cycle=3, before=85, after=60))  # réussite

    k = memory.knowledge_for("prospection")
    assert k.trials == 3
    assert k.successes == 2
    assert k.confidence == pytest.approx((2 + 1) / (3 + 2))  # Laplace : 60 %
    assert k.contexts["clients en retard"] == 3
    assert k.failure_contexts["clients en retard"] == 1
    assert "3 essai(s), 2 réussite(s)" in k.basis()
    assert "échoue surtout quand" in k.basis()


def test_suggestion_carries_confidence_and_problem(objective):
    memory = MemoryEngine(objective)
    engine = AICOSEngine(objective, memory)
    state = SystemState(values={"clients": 2, "revenus": 3000}, energy=80.0)
    action = Action(name="prospection", gradients={"clients": 1.0}, cost=2)
    for cycle in (1, 2):
        memory.learn(make_skill(cycle=cycle))

    suggestion = engine.suggest(state, [action])
    assert suggestion.confidence == pytest.approx((2 + 1) / (2 + 2))
    assert "essai(s)" in suggestion.basis
    assert "clients" in suggestion.problem
    text = suggestion.describe()
    assert "Problème" in text and "Action" in text and "Pourquoi" in text
    assert "Confiance : 75%" in text.replace(" ", " ").replace(" %", "%")


# --- Cas limite : jamais testée ---------------------------------------------


def test_untested_action_gets_neutral_confidence(objective):
    memory = MemoryEngine(objective)
    k = memory.knowledge_for("inconnue")
    assert not k.tested
    assert k.confidence == pytest.approx(0.5)  # prudence, ni crédit ni discrédit
    assert "jamais testée" in k.basis()


# --- Persistance + migration ------------------------------------------------


def test_knowledge_roundtrip(objective, tmp_path):
    memory = MemoryEngine(objective)
    memory.learn(make_skill())
    path = tmp_path / "memory.json"
    memory.save(path)

    restored = MemoryEngine(objective)
    restored.load(path)
    assert restored.knowledge_for("prospection").trials == 1


def test_legacy_memory_rebuilds_knowledge_from_skills(objective, tmp_path):
    """Cas erreur/limite : mémoire d'avant la base de connaissances (campagne
    en cours) — la connaissance est reconstruite en rejouant les skills."""
    memory = MemoryEngine(objective)
    memory.learn(make_skill(cycle=1))
    memory.learn(make_skill(cycle=2, before=80, after=90))
    path = tmp_path / "memory.json"
    memory.save(path)
    # Simule l'ancien format : on retire la clé "knowledge"
    import json

    data = json.loads(path.read_text())
    del data["knowledge"]
    path.write_text(json.dumps(data))

    restored = MemoryEngine(objective)
    restored.load(path)
    k = restored.knowledge_for("prospection")
    assert k.trials == 2 and k.successes == 1


def test_engine_cycle_feeds_knowledge(objective):
    memory = MemoryEngine(objective)
    engine = AICOSEngine(objective, memory)
    state = SystemState(values={"clients": 4, "revenus": 5000}, energy=50.0)
    action = Action(name="prospection", gradients={"clients": 2.0}, cost=2)
    engine.run_cycle(
        state, action, chosen_by_user=True,
        execute=lambda s, a, l: {d: g * l for d, g in a.gradients.items()},
    )
    assert memory.knowledge_for("prospection").trials == 1
