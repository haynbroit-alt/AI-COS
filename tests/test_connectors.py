"""Tests connecteurs : format de mission Claude Code + Automation Engine."""

import pytest

from ai_cos.connectors import AutomationEngine, ClaudeCodeConnector, SimulatedConnector
from ai_cos.connectors.claude_code import Mission
from ai_cos.state import Action, SystemState


def test_mission_contains_all_required_sections():
    connector = ClaudeCodeConnector()
    mission = connector.prepare_mission(
        objectif="Réduire l'écart clients",
        probleme="2 clients au lieu de 10",
        cause="aucun canal d'acquisition actif",
        action="mettre en place la prospection ciblée",
        contraintes=["une seule action", "pas de refonte"],
        critere="au moins 1 nouveau client sous 7 jours",
        test="comparer le compte clients avant/après",
    )
    text = connector.dispatch(mission)
    for section in Mission.REQUIRED_FIELDS:
        assert f"{section} :" in text
    assert connector.dispatched == [mission]


def test_non_executable_mission_rejected():
    connector = ClaudeCodeConnector()
    with pytest.raises(ValueError):
        connector.prepare_mission(
            objectif="", probleme="p", cause="c", action="a", critere="ok"
        )


def test_mission_result_recorded():
    connector = ClaudeCodeConnector()
    mission = connector.prepare_mission(
        objectif="o", probleme="p", cause="c", action="a", critere="ok"
    )
    result = connector.record_result(mission, delivered=True, notes="livré")
    assert result.delivered
    assert connector.results == [result]


def test_automation_engine_routes_and_measures():
    engine = AutomationEngine(default_connector=SimulatedConnector())
    state = SystemState(values={"clients": 2.0})
    action = Action(name="prospection", gradients={"clients": 1.5}, cost=2)
    deltas = engine.execute(state, action, lever=2.0)
    assert deltas == {"clients": 3.0}  # gradient × levier, sans bruit
    assert len(engine.log) == 1
    assert engine.log[0].deltas == {"clients": 3.0}


def test_automation_engine_requires_connector():
    engine = AutomationEngine()
    with pytest.raises(KeyError):
        engine.execute(SystemState(values={}), Action(name="inconnue"), lever=1.0)


def test_simulated_connector_deterministic_with_seed():
    a = SimulatedConnector(noise=0.2, seed=7)
    b = SimulatedConnector(noise=0.2, seed=7)
    state = SystemState(values={"clients": 0.0})
    action = Action(name="x", gradients={"clients": 1.0})
    assert a(state, action, 1.0) == b(state, action, 1.0)
