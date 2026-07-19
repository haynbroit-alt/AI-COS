"""Alias de compatibilité — module déplacé vers ai_cos.product.cli.

`python -m ai_cos.cli` reste le point d'entrée officiel (Routine terrain).
Les attributs mutables (STATE_FILE, configure_paths…) sont délégués
dynamiquement au module réel.
"""
import sys

from ai_cos.product import cli as _impl


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    try:
        _impl.main()
    except BrokenPipeError:
        sys.exit(0)
