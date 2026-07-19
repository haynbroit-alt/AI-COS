"""Tests du CLI quotidien : persistance et mode réel à mesure différée.

Cas normal : cycles cumulatifs, mesure du lendemain sur source réelle.
Cas erreur : source introuvable → sortie propre ; « q » → aucun cycle.
Cas limite : ancien state.json sans clés de progression → démarre à 0.
"""

import json

import pytest

from ai_cos.product import cli


def run_day(monkeypatch, answer="a", argv=()):
    monkeypatch.setattr("builtins.input", lambda *args: answer)
    cli.main(list(argv))


@pytest.fixture(autouse=True)
def isolated_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_COS_DATA_DIR", raising=False)
    cli.configure_paths(".ai_cos")  # les tests --data-dir ne fuient pas sur les suivants
    yield


# --- Mode simulation --------------------------------------------------------


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


# --- Mode réel : mesure différée --------------------------------------------


def write_journal(tmp_path, **values):
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps(values))
    return str(journal)


def test_real_mode_day_one_syncs_and_defers(tmp_path, monkeypatch, capsys):
    journal = write_journal(tmp_path, clients=3, revenus=1200, qualite=6)
    run_day(monkeypatch, argv=["--source", journal])
    out = capsys.readouterr().out
    assert "Mode RÉEL" in out
    assert "synchronisé sur la réalité" in out
    assert "la mesure se fera au prochain relevé" in out
    saved = json.loads(cli.STATE_FILE.read_text())
    assert saved["values"]["clients"] == 3
    assert saved["cycle_count"] == 0          # aucun cycle : rien n'est encore mesuré
    assert saved["pending_action"] is not None


def test_real_mode_next_day_measures_yesterdays_action(tmp_path, monkeypatch, capsys):
    journal = write_journal(tmp_path, clients=3, revenus=1200, qualite=6)
    run_day(monkeypatch, argv=["--source", journal])
    # La réalité a bougé pendant la nuit : +1 client, +300 de revenus
    write_journal(tmp_path, clients=4, revenus=1500, qualite=6)
    run_day(monkeypatch, argv=["--source", journal])
    out = capsys.readouterr().out
    assert "Mesure réelle de" in out
    saved = json.loads(cli.STATE_FILE.read_text())
    assert saved["cycle_count"] == 1          # le cycle d'hier est soldé
    assert saved["values"]["clients"] == 4    # l'état suit la réalité
    memory = json.loads(cli.MEMORY_FILE.read_text())
    assert memory["observed_effects"]          # le world model a appris du réel


def test_real_mode_measurement_survives_crash_before_choice(tmp_path, monkeypatch, capsys):
    """Cas limite : le processus meurt après la mesure, avant le choix du jour.
    La mesure d'hier doit déjà être sur disque."""
    journal = write_journal(tmp_path, clients=3, revenus=1200, qualite=6)
    run_day(monkeypatch, argv=["--source", journal])
    write_journal(tmp_path, clients=4, revenus=1500, qualite=6)

    def die(*args):
        raise KeyboardInterrupt  # l'utilisateur coupe au moment du prompt

    monkeypatch.setattr("builtins.input", die)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--source", journal])
    saved = json.loads(cli.STATE_FILE.read_text())
    assert saved["cycle_count"] == 1          # la mesure n'est pas perdue
    assert saved["pending_action"] is None    # et ne sera pas re-mesurée demain


def test_real_mode_missing_source_exits_cleanly(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_day(monkeypatch, argv=["--source", str(tmp_path / "absent.json")])
    assert "Erreur source" in capsys.readouterr().out


# --- Répertoire d'état configurable -----------------------------------------


def test_custom_data_dir(tmp_path, monkeypatch):
    """Cas normal : --data-dir place état et mémoire dans un répertoire suivi."""
    run_day(monkeypatch, argv=["--data-dir", "terrain"])
    assert (tmp_path / "terrain" / "state.json").exists()
    assert (tmp_path / "terrain" / "memory.json").exists()
    assert not (tmp_path / ".ai_cos").exists()


def test_data_dir_from_env(tmp_path, monkeypatch):
    """Cas limite : AI_COS_DATA_DIR sans drapeau explicite."""
    monkeypatch.setenv("AI_COS_DATA_DIR", "campagne")
    run_day(monkeypatch)
    assert (tmp_path / "campagne" / "state.json").exists()
