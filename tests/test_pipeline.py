"""Tests du pipeline de contrôle — chaque règle a son garde-fou.

Conformément à la règle 3, chaque garde est couvert par :
cas normal (happy path), cas erreur (transition refusée), cas limite.
"""

from pathlib import Path

import pytest

from ai_cos.connectors.claude_code import ClaudeCodeConnector
from ai_cos.pipeline import (
    CONSTITUTION_FILE,
    ControlPipeline,
    PipelineError,
    Plan,
    Stage,
    TestReport,
)

ROOT = Path(__file__).resolve().parent.parent


def make_mission(objectif="Ajouter la mémoire des décisions"):
    return ClaudeCodeConnector().prepare_mission(
        objectif=objectif,
        probleme="les décisions ne sont pas persistées",
        cause="aucun stockage",
        action="ajouter uniquement la mémoire des décisions",
        critere="10 tests passent",
        test="pytest tests/test_memory.py",
    )


def make_plan():
    return Plan(
        fichiers=["ai_cos/memory.py", "tests/test_memory.py"],
        risques=["corruption du fichier JSON"],
        strategie="ajout incrémental, aucune autre couche touchée",
        tests_prevus={
            "normal": "décision enregistrée puis relue",
            "erreur": "fichier JSON corrompu → erreur claire",
            "limite": "mémoire vide → lecture sans crash",
        },
    )


@pytest.fixture
def pipeline():
    return ControlPipeline(root=ROOT)


def run_until(pipeline, stage):
    """Fait avancer une mission jusqu'à l'étape demandée."""
    pipeline.submit(make_mission())
    if stage is Stage.SOUMISE:
        return
    pipeline.attach_plan(make_plan())
    if stage is Stage.PLANIFIEE:
        return
    pipeline.approve_plan("humain")
    if stage is Stage.PLAN_APPROUVE:
        return
    pipeline.record_build()
    if stage is Stage.CONSTRUITE:
        return
    pipeline.record_tests(TestReport(passed=10, failed=0))
    if stage is Stage.TESTEE:
        return
    pipeline.human_review("humain", approved=True)
    if stage is Stage.REVUE:
        return
    pipeline.validate_in_simulation()
    if stage is Stage.SIMULEE:
        return
    pipeline.deploy_to_production()


# --- Cas normal : trajectoire complète -------------------------------------


def test_full_pipeline_happy_path(pipeline):
    run_until(pipeline, Stage.EN_PRODUCTION)
    verdict = pipeline.measure(gap_before=100.0, gap_after=60.0)
    assert verdict.useful
    assert pipeline.in_flight is None
    assert pipeline.completed[0].stage is Stage.MESUREE
    assert len(pipeline.completed[0].history) == 9


# --- Règle 5 : source de vérité obligatoire --------------------------------


def test_constitution_required(tmp_path):
    with pytest.raises(PipelineError, match="source de vérité"):
        ControlPipeline(root=tmp_path)


def test_constitution_loaded(pipeline):
    assert "CONSTITUTION" in pipeline.constitution
    assert (ROOT / CONSTITUTION_FILE).exists()


# --- Règle 1 : une mission = un objectif -----------------------------------


def test_multi_objective_mission_rejected(pipeline):
    mission = make_mission(objectif="Construire la mémoire\nEt refaire toutes les vues")
    with pytest.raises(PipelineError, match="un objectif"):
        pipeline.submit(mission)


# --- Règle 4 : une seule mission en vol ------------------------------------


def test_second_mission_refused_while_in_flight(pipeline):
    pipeline.submit(make_mission())
    with pytest.raises(PipelineError, match="déjà en vol"):
        pipeline.submit(make_mission("Autre objectif"))


# --- Règle 2 : plan avant le code ------------------------------------------


def test_build_refused_without_approved_plan(pipeline):
    pipeline.submit(make_mission())
    with pytest.raises(PipelineError):
        pipeline.record_build()


def test_plan_missing_test_kinds_rejected(pipeline):
    pipeline.submit(make_mission())
    plan = make_plan()
    del plan.tests_prevus["limite"]
    with pytest.raises(PipelineError, match="limite"):
        pipeline.attach_plan(plan)


def test_plan_without_risks_rejected(pipeline):
    pipeline.submit(make_mission())
    plan = make_plan()
    plan.risques = []
    with pytest.raises(PipelineError, match="risque"):
        pipeline.attach_plan(plan)


# --- Règle 3 : tests obligatoires ------------------------------------------


def test_red_tests_block_review(pipeline):
    run_until(pipeline, Stage.CONSTRUITE)
    with pytest.raises(PipelineError, match="rouges"):
        pipeline.record_tests(TestReport(passed=8, failed=2))
    # cas limite : zéro test exécuté n'est pas vert non plus
    with pytest.raises(PipelineError):
        pipeline.record_tests(TestReport(passed=0, failed=0))


def test_insufficient_coverage_rejected(pipeline):
    run_until(pipeline, Stage.CONSTRUITE)
    with pytest.raises(PipelineError, match="Couverture"):
        pipeline.record_tests(TestReport(passed=2, failed=0))


# --- Revue humaine ----------------------------------------------------------


def test_human_rejection_closes_mission(pipeline):
    run_until(pipeline, Stage.TESTEE)
    pipeline.human_review("humain", approved=False, notes="hors périmètre")
    assert pipeline.in_flight is None
    assert pipeline.completed[0].stage is Stage.REJETEE
    # la voie est libre pour la mission suivante
    pipeline.submit(make_mission())


# --- Règle 6 : simulation avant production ---------------------------------


def test_production_refused_without_simulation(pipeline):
    run_until(pipeline, Stage.REVUE)
    with pytest.raises(PipelineError, match="simulation"):
        pipeline.deploy_to_production()


# --- Règle 7 : mesure réelle -----------------------------------------------


def test_useless_clean_code_flagged(pipeline):
    run_until(pipeline, Stage.EN_PRODUCTION)
    verdict = pipeline.measure(gap_before=100.0, gap_after=100.0)
    assert not verdict.useful
    assert "inutile" in verdict.describe()


def test_measure_requires_production(pipeline):
    run_until(pipeline, Stage.SIMULEE)
    with pytest.raises(PipelineError):
        pipeline.measure(gap_before=100.0, gap_after=50.0)
