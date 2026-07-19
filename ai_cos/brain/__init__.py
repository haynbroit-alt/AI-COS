"""Brain — mémoire, world model discret, base de connaissances.

C'est ici que la valeur s'accumule : chaque décision réelle devient une
connaissance réutilisable. À renforcer en priorité.
"""

from ai_cos.brain.memory import ActionKnowledge, MemoryEngine, Skill

__all__ = ["ActionKnowledge", "MemoryEngine", "Skill"]
