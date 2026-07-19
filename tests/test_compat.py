"""Les alias de compatibilité restent fonctionnels (plus utilisés en interne)."""


def test_old_import_paths_still_work():
    from ai_cos.engine import AICOSEngine  # noqa: F401
    from ai_cos.state import Action, REST  # noqa: F401
    from ai_cos.memory import MemoryEngine  # noqa: F401
    from ai_cos.config import load_config  # noqa: F401
    from ai_cos.views import CosmicView  # noqa: F401
    from ai_cos.sources import JsonFileSource  # noqa: F401
    from ai_cos.pipeline import ControlPipeline  # noqa: F401
    from ai_cos.connectors import ClaudeCodeConnector  # noqa: F401
    from ai_cos.connectors.automation import SimulatedConnector  # noqa: F401
    from ai_cos import cli

    assert callable(cli.main)
    assert cli.STATE_FILE.name == "state.json"  # délégation dynamique
