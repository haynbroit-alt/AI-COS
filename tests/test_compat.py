"""`python -m ai_cos.cli` reste le point d'entrée officiel (Routine terrain)."""


def test_cli_entry_point_delegates_to_product():
    from ai_cos import cli

    assert callable(cli.main)
    assert cli.STATE_FILE.name == "state.json"  # délégation dynamique
