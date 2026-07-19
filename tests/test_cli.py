"""Tests du CLI quotidien : persistance de la progression entre les jours.

Cas normal : deux jours consécutifs → le compteur de cycles est cumulatif.
Cas erreur : réponse « q » → aucun cycle exécuté, rien d'écrasé.
Cas limite : ancien state.json sans les clés de progression → démarre à 0.
"""

import json

import pytest

from ai_cos import cli


def run_day(monkeypatch, answer="a"):
    monkeypatch.setattr("builtins.input", lambda *args: answer)
    cli.main()


@pytest.fixture(autouse=True)
def isolated_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_cycle_count_cumulative_across_days(monkeypatch, capsys):
    run_day(monkeypatch)
    run_day(monkeypatch)
    run_day(monkeypatch)
    out = capsys.readouterr().out
    assert "Cycle 3 :" in out
    saved = json.loads(cli.STATE_FILE.read_text())
    assert saved["cycle_count"] == 3
    assert len(saved["gap_history"]) == 3
    assert len(saved["state_history"]) == 3


def test_quit_runs_no_cycle(monkeypatch, capsys):
    run_day(monkeypatch)
    run_day(monkeypatch, answer="q")
    assert json.loads(cli.STATE_FILE.read_text())["cycle_count"] == 1


def test_legacy_state_without_progress_keys(monkeypatch, capsys):
    cli.DATA_DIR.mkdir(exist_ok=True)
    cli.STATE_FILE.write_text(
        json.dumps({"values": {"clients": 4, "revenus": 2000, "qualite": 6}, "energy": 80.0})
    )
    run_day(monkeypatch)
    saved = json.loads(cli.STATE_FILE.read_text())
    assert saved["cycle_count"] == 1  # reparti proprement de 0, pas de crash
    assert saved["values"]["clients"] >= 4
