"""Claude Code Connector — AI-COS architecte, Claude Code constructeur.

AI-COS ne code pas : il prépare des missions claires et exécutables,
puis vérifie le résultat, mesure l'impact et apprend.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mission:
    """Format de mission officiel AI-COS → Claude Code."""

    objectif: str
    probleme: str
    cause_identifiee: str
    action_demandee: str
    contraintes: list[str] = field(default_factory=list)
    critere_de_reussite: str = ""
    test_a_effectuer: str = ""

    REQUIRED_FIELDS = (
        "OBJECTIF",
        "PROBLÈME",
        "CAUSE IDENTIFIÉE",
        "ACTION DEMANDÉE",
        "CONTRAINTES",
        "CRITÈRE DE RÉUSSITE",
        "TEST À EFFECTUER",
    )

    def render(self) -> str:
        contraintes = "\n".join(f"- {c}" for c in self.contraintes) or "- aucune"
        return (
            f"OBJECTIF :\n{self.objectif}\n\n"
            f"PROBLÈME :\n{self.probleme}\n\n"
            f"CAUSE IDENTIFIÉE :\n{self.cause_identifiee}\n\n"
            f"ACTION DEMANDÉE :\n{self.action_demandee}\n\n"
            f"CONTRAINTES :\n{contraintes}\n\n"
            f"CRITÈRE DE RÉUSSITE :\n{self.critere_de_reussite}\n\n"
            f"TEST À EFFECTUER :\n{self.test_a_effectuer}"
        )

    def is_executable(self) -> bool:
        """Une mission est exécutable si objectif, action et critère sont définis."""
        return bool(self.objectif and self.action_demandee and self.critere_de_reussite)


@dataclass
class MissionResult:
    mission: Mission
    delivered: bool
    notes: str = ""


class ClaudeCodeConnector:
    """Prépare, dispatche et vérifie les missions de développement."""

    def __init__(self) -> None:
        self.dispatched: list[Mission] = []
        self.results: list[MissionResult] = []

    def prepare_mission(
        self,
        objectif: str,
        probleme: str,
        cause: str,
        action: str,
        contraintes: list[str] | None = None,
        critere: str = "",
        test: str = "",
    ) -> Mission:
        mission = Mission(
            objectif=objectif,
            probleme=probleme,
            cause_identifiee=cause,
            action_demandee=action,
            contraintes=contraintes or [],
            critere_de_reussite=critere,
            test_a_effectuer=test,
        )
        if not mission.is_executable():
            raise ValueError(
                "Mission non exécutable : objectif, action demandée et "
                "critère de réussite sont obligatoires."
            )
        return mission

    def dispatch(self, mission: Mission) -> str:
        """Envoie la mission au constructeur ; retourne le texte transmis."""
        self.dispatched.append(mission)
        return mission.render()

    def record_result(self, mission: Mission, delivered: bool, notes: str = "") -> MissionResult:
        """Après exécution : vérifier le résultat avant de mesurer et apprendre."""
        result = MissionResult(mission=mission, delivered=delivered, notes=notes)
        self.results.append(result)
        return result
