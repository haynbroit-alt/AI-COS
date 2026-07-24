"""Tests du cœur d'orchestration multi-IA — logique de routage pure, zéro réseau.

Couvre : résolution modèle→fournisseur, chaîne par rôle, sous-ensemble
appelable selon les clés présentes, bascule en fallback, dégradation propre
sans clé, estimation de coût, conseil (deliberate), et diagnostic health().
Le transport HTTP est injecté : aucun appel réseau."""
from __future__ import annotations

from ai_cos import orchestrator as orch


CONFIG = {
    "roles": {
        "stratege": {"primary": "claude-opus-5",
                     "fallbacks": ["deepseek-reasoner", "claude-sonnet-5"],
                     "max_tokens": 100},
        "architecte": {"primary": "gpt-5", "fallbacks": ["claude-opus-5"]},
        "gardien": {"primary": "claude-opus-5", "fallbacks": ["gpt-5"]},
    },
    "prices": {"anthropic": [5.0, 25.0], "openai": [5.0, 15.0], "deepseek": [0.6, 1.7]},
}


# ── résolution fournisseur ───────────────────────────────────────────────

def test_provider_for_familles():
    assert orch.provider_for("claude-opus-5") == "anthropic"
    assert orch.provider_for("gpt-5") == "openai"
    assert orch.provider_for("o3-mini") == "openai"
    assert orch.provider_for("gemini-2.5-pro") == "google"
    assert orch.provider_for("deepseek-reasoner") == "deepseek"
    assert orch.provider_for("mistral-large-latest") == "mistral"


def test_provider_for_inconnu_leve():
    try:
        orch.provider_for("llama-4")
        assert False, "aurait dû lever"
    except orch.OrchestratorError:
        pass


# ── chaîne & sous-ensemble appelable ─────────────────────────────────────

def test_resolve_chain_dedupe_ordre():
    cfg = {"roles": {"r": {"primary": "gpt-5", "fallbacks": ["gpt-5", "claude-sonnet-5"]}}}
    assert orch.resolve_chain("r", cfg) == ["gpt-5", "claude-sonnet-5"]


def test_available_providers_depuis_env():
    env = {"ANTHROPIC_API_KEY": "x", "DEEPSEEK_API_KEY": "y"}
    assert orch.available_providers(env) == {"anthropic", "deepseek"}


def test_callable_route_filtre_sur_cles():
    # Seul anthropic a une clé → gpt-5 (openai) est sauté, opus reste.
    env = {"ANTHROPIC_API_KEY": "x"}
    route = orch.callable_route("stratege", CONFIG, env)
    assert route == [("claude-opus-5", "anthropic"), ("claude-sonnet-5", "anthropic")]


def test_callable_route_vide_sans_cle():
    assert orch.callable_route("stratege", CONFIG, {}) == []


# ── routage réel (transport simulé) ──────────────────────────────────────

def _fake_anthropic(url, headers, body):
    return {"content": [{"type": "text", "text": "OK-opus"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}}


def test_route_prend_le_primary_disponible():
    env = {"ANTHROPIC_API_KEY": "x"}
    res = orch.route("stratege", "salut", config=CONFIG, env=env,
                     transport=_fake_anthropic, ledger_path=None)
    assert res.model == "claude-opus-5" and res.provider == "anthropic"
    assert res.text == "OK-opus"
    assert res.cost_usd == orch.estimate_cost("anthropic", 10, 5, CONFIG["prices"])
    assert res.attempts == []


def test_route_bascule_en_fallback_si_primary_echoue():
    # Primary (openai gpt-5) échoue → fallback anthropic (claude-opus-5) réussit.
    env = {"OPENAI_API_KEY": "x", "ANTHROPIC_API_KEY": "y"}

    def transport(url, headers, body):
        if "openai.com" in url:
            raise orch.OrchestratorError("HTTP 500")
        return _fake_anthropic(url, headers, body)

    res = orch.route("architecte", "code", config=CONFIG, env=env,
                     transport=transport, ledger_path=None)
    assert res.model == "claude-opus-5"
    assert res.attempts == ["gpt-5"]  # gpt-5 tenté puis écarté


def test_route_sans_cle_leve_proprement():
    try:
        orch.route("stratege", "x", config=CONFIG, env={}, ledger_path=None)
        assert False, "aurait dû lever"
    except orch.OrchestratorError as e:
        assert "Aucun fournisseur disponible" in str(e)


def test_route_tous_echouent_leve():
    env = {"ANTHROPIC_API_KEY": "x"}

    def transport(url, headers, body):
        raise orch.OrchestratorError("HTTP 500")

    try:
        orch.route("stratege", "x", config=CONFIG, env=env,
                   transport=transport, ledger_path=None)
        assert False, "aurait dû lever"
    except orch.OrchestratorError as e:
        assert "ont échoué" in str(e)


# ── conseil ──────────────────────────────────────────────────────────────

def test_deliberate_agrege_les_avis_disponibles():
    env = {"ANTHROPIC_API_KEY": "x"}  # openai absent → 1 seul avis (opus)
    avis = orch.deliberate("gardien", "risque ?", k=3, config=CONFIG, env=env,
                           transport=_fake_anthropic, ledger_path=None)
    assert len(avis) == 1 and avis[0].model == "claude-opus-5"


# ── coût & santé ─────────────────────────────────────────────────────────

def test_estimate_cost():
    # 1000 in, 1000 out chez deepseek (0.6, 1.7) = (600+1700)/1e6
    assert orch.estimate_cost("deepseek", 1000, 1000, CONFIG["prices"]) == round(2300 / 1_000_000, 6)


def test_health_montre_degradation():
    env = {"ANTHROPIC_API_KEY": "x"}
    h = orch.health(config=CONFIG, env=env)
    assert h["providers_available"] == ["anthropic"]
    assert h["roles"]["stratege"]["servable"] is True
    assert h["roles"]["stratege"]["active_provider"] == "anthropic"
    # architecte : primary gpt-5 (openai, pas de clé) → bascule sur claude-opus-5
    assert h["roles"]["architecte"]["active_model"] == "claude-opus-5"
