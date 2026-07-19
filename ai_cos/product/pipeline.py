"""Pipeline de contrôle autour de Claude Code.

On ne cherche pas du code parfait du premier coup : on met un système de
contrôle autour du constructeur.

    Mission claire → Plan → Construction → Tests → Revue humaine
    → Déploiement progressif (simulation → production) → Mesure réelle

Chaque transition est gardée. Le pipeline applique les 7 règles de la
constitution (AI-COS_CONSTITUTION.md) et refuse de fonctionner sans elle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ai_cos.product.connectors.claude_code import Mission

CONSTITUTION_FILE = "AI-COS_CONSTITUTION.md"

# Règle 3 : chaque fonction importante couvre ces trois cas.
REQUIRED_TEST_KINDS = frozenset({"normal", "erreur", "limite"})


class PipelineError(RuntimeError):
    """Transition refusée par le système de contrôle."""


class Stage(Enum):
    SOUMISE = "soumise"
    PLANIFIEE = "planifiée"
    PLAN_APPROUVE = "plan approuvé"
    CONSTRUITE = "construite"
    TESTEE = "testée"
    REVUE = "revue humaine OK"
    SIMULEE = "validée en simulation"
    EN_PRODUCTION = "en production"
    MESUREE = "mesurée"
    REJETEE = "rejetée"


@dataclass
class Plan:
    """Règle 2 : toujours un plan avant le code."""

    fichiers: list[str]
    risques: list[str]
    strategie: str
    tests_prevus: dict[str, str]  # kind ("normal"/"erreur"/"limite") → description

    def validate(self) -> None:
        if not self.fichiers:
            raise PipelineError("Plan invalide : aucun fichier concerné listé.")
        if not self.risques:
            raise PipelineError("Plan invalide : aucun risque identifié.")
        if not self.strategie:
            raise PipelineError("Plan invalide : stratégie manquante.")
        missing = REQUIRED_TEST_KINDS - set(self.tests_prevus)
        if missing:
            raise PipelineError(
                f"Plan invalide : tests manquants pour les cas {sorted(missing)} "
                "(règle 3 : cas normal + cas erreur + cas limite)."
            )


@dataclass
class TestReport:
    """Résultat des tests automatiques post-construction."""

    __test__ = False  # nom en Test* : ne pas collecter comme test pytest

    passed: int
    failed: int
    details: str = ""

    @property
    def green(self) -> bool:
        return self.failed == 0 and self.passed > 0


@dataclass
class Verdict:
    """Règle 7 : la vraie question — l'écart a-t-il baissé ?"""

    gap_before: float
    gap_after: float

    @property
    def useful(self) -> bool:
        return self.gap_after < self.gap_before

    def describe(self) -> str:
        if self.useful:
            return f"Utile : écart {self.gap_before:.2f} → {self.gap_after:.2f}."
        return (
            f"Code propre mais inutile : écart {self.gap_before:.2f} → "
            f"{self.gap_after:.2f} (pas de réduction). Mission à reprendre."
        )


@dataclass
class ControlledMission:
    """Une mission et sa trajectoire dans le pipeline."""

    mission: Mission
    stage: Stage = Stage.SOUMISE
    plan: Plan | None = None
    plan_approved_by: str | None = None
    test_report: TestReport | None = None
    reviewed_by: str | None = None
    verdict: Verdict | None = None
    history: list[str] = field(default_factory=list)

    def _advance(self, stage: Stage, note: str) -> None:
        self.stage = stage
        self.history.append(f"{stage.value} — {note}")


class ControlPipeline:
    """Chef d'orchestre du constructeur. AI-COS contrôle la direction."""

    MODES = ("complet", "leger")

    def __init__(self, root: str | Path = ".", mode: str = "complet") -> None:
        if mode not in self.MODES:
            raise PipelineError(f"Mode inconnu « {mode} » — choix : {self.MODES}")
        path = Path(root) / CONSTITUTION_FILE
        if not path.exists():
            raise PipelineError(
                f"{CONSTITUTION_FILE} introuvable — le pipeline refuse de "
                "fonctionner sans source de vérité (règle 5)."
            )
        self.constitution = path.read_text()
        # « complet » : gouvernance intégrale, pour développer AI-COS.
        # « leger » : usage quotidien — plan, revue humaine et simulation
        # deviennent optionnels, mais les invariants ne se désactivent
        # jamais : une mission à la fois, un objectif, tests verts,
        # mesure réelle.
        self.mode = mode
        self.in_flight: ControlledMission | None = None
        self.completed: list[ControlledMission] = []

    # --- Règle 1 + 4 : une mission, un objectif, une à la fois -----------

    def submit(self, mission: Mission) -> ControlledMission:
        if self.in_flight is not None:
            raise PipelineError(
                "Une mission est déjà en vol (règle 4 : une modification, "
                "puis test, puis validation, puis la suivante)."
            )
        objectif = mission.objectif.strip()
        if "\n" in objectif:
            raise PipelineError(
                "Objectif multiple détecté (règle 1 : une mission = un objectif)."
            )
        if not mission.critere_de_reussite:
            raise PipelineError(
                "Pas de critère de réussite mesurable (règle 1)."
            )
        controlled = ControlledMission(mission=mission)
        controlled._advance(Stage.SOUMISE, objectif)
        self.in_flight = controlled
        return controlled

    # --- Règle 2 : plan avant le code -------------------------------------

    def attach_plan(self, plan: Plan) -> None:
        cm = self._require(Stage.SOUMISE)
        plan.validate()
        cm.plan = plan
        cm._advance(Stage.PLANIFIEE, f"{len(plan.fichiers)} fichier(s), {len(plan.risques)} risque(s)")

    def approve_plan(self, approved_by: str) -> None:
        cm = self._require(Stage.PLANIFIEE)
        cm.plan_approved_by = approved_by
        cm._advance(Stage.PLAN_APPROUVE, f"par {approved_by}")

    # --- Construction ------------------------------------------------------

    def record_build(self, note: str = "livrable produit") -> None:
        if self.mode == "leger":
            # Plan optionnel : on peut construire dès la soumission,
            # ou après un plan approuvé si l'utilisateur en a fait un.
            cm = self._require_any((Stage.SOUMISE, Stage.PLAN_APPROUVE))
        else:
            cm = self._require(Stage.PLAN_APPROUVE)
        cm._advance(Stage.CONSTRUITE, note)

    # --- Règle 3 : tests obligatoires --------------------------------------

    def record_tests(self, report: TestReport) -> None:
        cm = self._require(Stage.CONSTRUITE)
        if not report.green:
            cm.test_report = report
            raise PipelineError(
                f"Tests rouges ({report.failed} échec(s)) — retour construction, "
                "pas de revue humaine sur du rouge."
            )
        if report.passed < len(REQUIRED_TEST_KINDS):
            raise PipelineError(
                "Couverture insuffisante : au moins un test par cas "
                "(normal, erreur, limite) — règle 3."
            )
        cm.test_report = report
        cm._advance(Stage.TESTEE, f"{report.passed} tests verts")

    # --- Revue humaine ------------------------------------------------------

    def human_review(self, reviewer: str, approved: bool, notes: str = "") -> None:
        cm = self._require(Stage.TESTEE)
        if not approved:
            cm._advance(Stage.REJETEE, f"refusée par {reviewer} : {notes}")
            self.completed.append(cm)
            self.in_flight = None
            return
        cm.reviewed_by = reviewer
        cm._advance(Stage.REVUE, f"par {reviewer}")

    # --- Règle 6 : simulation avant production ------------------------------

    def validate_in_simulation(self, note: str = "comportement conforme") -> None:
        cm = self._require(Stage.REVUE)
        cm._advance(Stage.SIMULEE, note)

    def deploy_to_production(self) -> None:
        if self.mode == "leger":
            # Revue humaine et simulation optionnelles : tests verts suffisent.
            cm = self._require_any((Stage.TESTEE, Stage.REVUE, Stage.SIMULEE))
        else:
            cm = self._require(
                Stage.SIMULEE,
                hint="production interdite sans passage par la simulation (règle 6)",
            )
        cm._advance(Stage.EN_PRODUCTION, "déploiement progressif")

    # --- Règle 7 : mesure réelle --------------------------------------------

    def measure(self, gap_before: float, gap_after: float) -> Verdict:
        cm = self._require(Stage.EN_PRODUCTION)
        verdict = Verdict(gap_before=gap_before, gap_after=gap_after)
        cm.verdict = verdict
        cm._advance(Stage.MESUREE, verdict.describe())
        self.completed.append(cm)
        self.in_flight = None
        return verdict

    # --- Interne ------------------------------------------------------------

    def _require(self, stage: Stage, hint: str = "") -> ControlledMission:
        return self._require_any((stage,), hint)

    def _require_any(self, stages: tuple[Stage, ...], hint: str = "") -> ControlledMission:
        if self.in_flight is None:
            raise PipelineError("Aucune mission en vol.")
        if self.in_flight.stage not in stages:
            expected = " ou ".join(f"« {s.value} »" for s in stages)
            message = (
                f"Étape « {self.in_flight.stage.value} » : transition refusée "
                f"(attendu : {expected})."
            )
            if hint:
                message += f" {hint}."
            raise PipelineError(message)
        return self.in_flight
