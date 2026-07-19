"""Tests de la configuration des dimensions — cas normal / erreur / limite."""

import json

import pytest

from ai_cos.product.config import ConfigError, load_config, parse_config
from ai_cos.product.demo import build_scenario


def test_default_config_matches_historic_scenario():
    objective, state, actions = load_config(None)
    assert objective.targets == {"clients": 10, "revenus": 5000, "qualite": 8}
    assert state.values["clients"] == 2
    assert {a.name for a in actions} >= {"prospection ciblée", "offre premium", "repos"}


def test_fully_custom_dimensions_run_a_cycle():
    """Sommeil/sport à la place de clients/revenus : la boucle tourne pareil."""
    raw = {
        "objective": {"sommeil": 8, "sport": 5},
        "initial": {"sommeil": 6, "sport": 1},
        "energy": 50,
        "actions": [
            {"name": "coucher 22h", "gradients": {"sommeil": 0.5}, "cost": 2},
            {"name": "footing", "gradients": {"sport": 1.0}, "cost": 3},
        ],
    }
    objective, state, actions = parse_config(raw)
    from ai_cos.core.engine import AICOSEngine
    from ai_cos.brain.memory import MemoryEngine

    engine = AICOSEngine(objective, MemoryEngine(objective))
    suggestion = engine.suggest(state, actions)
    report = engine.run_cycle(
        state, suggestion.action, chosen_by_user=True,
        execute=lambda s, a, l: {d: g * l for d, g in a.gradients.items()},
    )
    assert report.gap_reduced
    assert set(engine.memory.weights) == {"sommeil", "sport"}


def test_config_from_file(tmp_path):
    path = tmp_path / "conf.json"
    path.write_text(json.dumps({
        "objective": {"ventes": 100},
        "actions": [{"name": "demo", "gradients": {"ventes": 5}}],
    }))
    engine, state, actions, automation = build_scenario(str(path))
    assert engine.objective.targets == {"ventes": 100.0}
    assert state.values == {"ventes": 0.0}  # dimension initiale absente → 0


def test_invalid_configs_rejected(tmp_path):
    with pytest.raises(ConfigError, match="objective"):
        parse_config({"actions": [{"name": "x"}]})
    with pytest.raises(ConfigError, match="Aucune action"):
        parse_config({"objective": {"a": 1}})
    with pytest.raises(ConfigError, match="dimensions"):
        parse_config({
            "objective": {"a": 1},
            "actions": [{"name": "x", "gradients": {"zzz": 1}}],
        })
    with pytest.raises(ConfigError, match="inconnues"):
        parse_config({
            "objective": {"a": 1},
            "initial": {"autre": 2},
            "actions": [{"name": "x"}],
        })
    with pytest.raises(ConfigError, match="introuvable"):
        load_config(tmp_path / "absent.json")
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{pas du json")
    with pytest.raises(ConfigError, match="illisible"):
        load_config(corrupt)
