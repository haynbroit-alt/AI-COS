"""AI-COS V9 — Système d'exploitation décisionnel personnel.

Boucle : ÉCART → CAUSE → PRIORITÉ → PREMIER PAS → ACTION → MESURE → APPRENTISSAGE

Règle bloquante : pas de V10/V11 avant validation du prototype
(10 cycles complets en 30 jours, 0 modification de boucle).
"""

LOOP_VERSION = "V9"

from ai_cos.core.state import Action, Objective, SystemState  # noqa: E402
from ai_cos.brain.memory import MemoryEngine  # noqa: E402
from ai_cos.core.engine import AICOSEngine, LoopLockedError  # noqa: E402

__all__ = [
    "LOOP_VERSION",
    "Action",
    "Objective",
    "SystemState",
    "MemoryEngine",
    "AICOSEngine",
    "LoopLockedError",
]
