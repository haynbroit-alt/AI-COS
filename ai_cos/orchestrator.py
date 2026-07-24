"""Cœur d'orchestration multi-IA — le sang d'AI-COS.

Un seul point d'entrée — ``route(role, system, user)`` — que n'importe quel
module appelle. Le hub choisit le modèle selon le RÔLE (config), bascule en
fallback si un fournisseur est indisponible (clé absente ou erreur), et
journalise coût + latence. Aucun module ne connaît un fournisseur : il demande
« le stratège » ou « le gardien », le sang porte l'appel au bon organe.

Principes (alignés Constitution) :
- Provider-agnostique : les IDs de modèles vivent dans orchestrator_config.json,
  JAMAIS en dur. Le routeur survit à n'importe quelle nouvelle génération de
  modèles — on édite la config, pas le code.
- Zéro secret en dur : chaque clé vient de l'environnement. Sans clé, le
  fournisseur est simplement sauté (dégradation propre, pas d'exception).
- Transport injectable : toute la logique de routage est pure et testable sans
  réseau ; le câblage HTTP réel vit derrière une seule fonction.
- Réalité > Hypothèse : un modèle qui échoue est écarté au profit du suivant ;
  ce qui a marché est journalisé, pas supposé.

Fournisseurs adaptés : anthropic, openai (+ compatibles), google (Gemini),
deepseek, mistral. En ajouter un = une entrée dans _ADAPTERS, rien d'autre.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

HERE = Path(__file__).parent
CONFIG_PATH = HERE / "orchestrator_config.json"
LEDGER_PATH = HERE / "orchestrator_ledger.jsonl"

# Transport injectable : (url, headers, body_bytes) -> dict. Aucun réseau en test.
Transport = Callable[[str, dict, bytes], dict]


class OrchestratorError(RuntimeError):
    pass


# ══════════════════════════════════════════════════════════════════════
# FOURNISSEURS — chaque adaptateur sait parler à UNE API. Ajouter un
# fournisseur = ajouter une entrée ici. La forme des requêtes/réponses est
# encapsulée ; le reste du système n'en dépend jamais.
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Provider:
    name: str
    env_key: str                       # variable d'env portant la clé
    build: Callable[..., tuple]        # (model, system, user, max_tokens, key) -> (url, headers, body)
    parse: Callable[[dict], tuple]     # resp -> (text, in_tokens, out_tokens)


def _anthropic_build(model, system, user, max_tokens, key):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}]}
    if system:
        body["system"] = system
    return url, headers, json.dumps(body).encode()


def _anthropic_parse(resp):
    text = "".join(b.get("text", "") for b in resp.get("content", [])
                   if b.get("type") == "text")
    u = resp.get("usage", {})
    return text, u.get("input_tokens", 0), u.get("output_tokens", 0)


def _openai_build(model, system, user, max_tokens, key, *, url):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": user}]
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    body = {"model": model, "max_tokens": max_tokens, "messages": msgs}
    return url, headers, json.dumps(body).encode()


def _openai_parse(resp):
    text = resp["choices"][0]["message"]["content"] if resp.get("choices") else ""
    u = resp.get("usage", {})
    return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def _google_build(model, system, user, max_tokens, key):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    headers = {"content-type": "application/json"}
    body = {"contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return url, headers, json.dumps(body).encode()


def _google_parse(resp):
    cands = resp.get("candidates", [])
    text = ""
    if cands:
        text = "".join(p.get("text", "")
                       for p in cands[0].get("content", {}).get("parts", []))
    u = resp.get("usageMetadata", {})
    return text, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


_ADAPTERS: dict[str, Provider] = {
    "anthropic": Provider("anthropic", "ANTHROPIC_API_KEY", _anthropic_build, _anthropic_parse),
    "openai": Provider(
        "openai", "OPENAI_API_KEY",
        lambda m, s, u, mt, k: _openai_build(m, s, u, mt, k,
                                             url="https://api.openai.com/v1/chat/completions"),
        _openai_parse),
    "deepseek": Provider(
        "deepseek", "DEEPSEEK_API_KEY",
        lambda m, s, u, mt, k: _openai_build(m, s, u, mt, k,
                                             url="https://api.deepseek.com/chat/completions"),
        _openai_parse),
    "mistral": Provider(
        "mistral", "MISTRAL_API_KEY",
        lambda m, s, u, mt, k: _openai_build(m, s, u, mt, k,
                                             url="https://api.mistral.ai/v1/chat/completions"),
        _openai_parse),
    "google": Provider("google", "GOOGLE_API_KEY", _google_build, _google_parse),
}

# Résolution modèle -> fournisseur par préfixe. Éditable, mais couvre les
# familles courantes. Un modèle inconnu lève une erreur explicite plutôt que
# d'appeler le mauvais fournisseur en silence.
_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("claude", "anthropic"),
    ("gpt", "openai"), ("o1", "openai"), ("o3", "openai"), ("o4", "openai"),
    ("gemini", "google"),
    ("deepseek", "deepseek"),
    ("mistral", "mistral"), ("magistral", "mistral"), ("codestral", "mistral"),
)


def provider_for(model: str) -> str:
    """Fournisseur d'un modèle, par préfixe. Lève si inconnu (pas de silence)."""
    m = model.lower()
    for prefix, prov in _PREFIX_RULES:
        if m.startswith(prefix):
            return prov
    raise OrchestratorError(
        f"Modèle inconnu : « {model} ». Ajoutez une règle dans _PREFIX_RULES "
        f"ou corrigez orchestrator_config.json."
    )


# ══════════════════════════════════════════════════════════════════════
# COÛT — table indicative $/1M tokens (in, out). À AJUSTER : les prix
# bougent. Sert au journal, jamais à bloquer un appel.
# ══════════════════════════════════════════════════════════════════════

DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "anthropic": (5.0, 25.0),
    "openai": (5.0, 15.0),
    "google": (2.5, 10.0),
    "deepseek": (0.6, 1.7),
    "mistral": (2.0, 6.0),
}


def estimate_cost(provider: str, in_tok: int, out_tok: int,
                  prices: dict | None = None) -> float:
    p = (prices or DEFAULT_PRICES).get(provider, (0.0, 0.0))
    return round((in_tok * p[0] + out_tok * p[1]) / 1_000_000, 6)


# ══════════════════════════════════════════════════════════════════════
# CONFIG & ROUTAGE (pur, testable)
# ══════════════════════════════════════════════════════════════════════

def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise OrchestratorError(f"Config d'orchestration absente : {path}")
    return json.loads(path.read_text())


def available_providers(env: dict | None = None) -> set[str]:
    """Fournisseurs dont la clé est présente dans l'environnement."""
    env = env if env is not None else os.environ
    return {name for name, p in _ADAPTERS.items() if env.get(p.env_key)}


def resolve_chain(role: str, config: dict) -> list[str]:
    """Chaîne ordonnée de modèles pour un rôle : [primary, *fallbacks]."""
    roles = config.get("roles", {})
    if role not in roles:
        raise OrchestratorError(
            f"Rôle inconnu : « {role} ». Rôles définis : {sorted(roles)}")
    spec = roles[role]
    chain = [spec["primary"], *spec.get("fallbacks", [])]
    # dédoublonnage en préservant l'ordre
    seen, out = set(), []
    for m in chain:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def callable_route(role: str, config: dict, env: dict | None = None) -> list[tuple[str, str]]:
    """Sous-ensemble de la chaîne réellement appelable (clé présente),
    sous forme [(model, provider), …], dans l'ordre de préférence. Pur."""
    avail = available_providers(env)
    out = []
    for model in resolve_chain(role, config):
        prov = provider_for(model)
        if prov in avail:
            out.append((model, prov))
    return out


# ══════════════════════════════════════════════════════════════════════
# CÂBLAGE RÉEL (hors chemin testé)
# ══════════════════════════════════════════════════════════════════════

def _http_post_json(url: str, headers: dict, body: bytes) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        raise OrchestratorError(f"HTTP {exc.code} : {exc.read().decode(errors='replace')[:300]}") from exc
    except Exception as exc:  # noqa: BLE001 — urllib lève des types variés
        raise OrchestratorError(f"Appel échoué : {exc}") from exc


@dataclass
class Result:
    role: str
    model: str
    provider: str
    text: str
    in_tokens: int = 0
    out_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    attempts: list[str] = field(default_factory=list)  # modèles tentés avant succès


def _call_one(model: str, provider: str, system: str, user: str,
              max_tokens: int, env: dict, transport: Transport) -> tuple:
    p = _ADAPTERS[provider]
    key = env[p.env_key]
    url, headers, body = p.build(model, system, user, max_tokens, key)
    resp = transport(url, headers, body)
    return p.parse(resp)


def route(role: str, user: str, *, system: str = "", config: dict | None = None,
          env: dict | None = None, transport: Transport = _http_post_json,
          ledger_path: Path | None = LEDGER_PATH) -> Result:
    """Route une requête vers le meilleur modèle disponible pour ``role``.

    Essaie la chaîne dans l'ordre ; bascule au suivant sur erreur. Journalise
    l'issue. Lève OrchestratorError si aucun modèle n'est disponible/ne répond.
    C'est LE point d'entrée : un module ne nomme jamais un fournisseur."""
    config = config or load_config()
    env = env if env is not None else os.environ
    spec = config.get("roles", {}).get(role, {})
    max_tokens = spec.get("max_tokens", 1024)

    route_ = callable_route(role, config, env)
    if not route_:
        raise OrchestratorError(
            f"Aucun fournisseur disponible pour « {role} ». Chaîne : "
            f"{resolve_chain(role, config)} — posez au moins une clé "
            f"(ANTHROPIC_API_KEY, OPENAI_API_KEY, …).")

    attempts, last_err = [], ""
    for model, provider in route_:
        t0 = time.time()
        try:
            text, itk, otk = _call_one(model, provider, system, user, max_tokens, env, transport)
        except OrchestratorError as exc:
            attempts.append(model)
            last_err = str(exc)
            _log(ledger_path, role, model, provider, False, int((time.time() - t0) * 1000), 0.0, str(exc))
            continue
        latency = int((time.time() - t0) * 1000)
        cost = estimate_cost(provider, itk, otk, config.get("prices"))
        _log(ledger_path, role, model, provider, True, latency, cost, "")
        return Result(role, model, provider, text, itk, otk, cost, latency, attempts)

    raise OrchestratorError(
        f"Tous les modèles ont échoué pour « {role} » ({', '.join(attempts)}). "
        f"Dernière erreur : {last_err}")


def deliberate(role: str, user: str, *, k: int = 3, system: str = "",
               config: dict | None = None, env: dict | None = None,
               transport: Transport = _http_post_json,
               ledger_path: Path | None = LEDGER_PATH) -> list[Result]:
    """Conseil : interroge jusqu'à ``k`` modèles distincts de la chaîne du rôle
    et renvoie tous les avis. Pour les rôles à enjeu (Décideur, Gardien) où l'on
    veut une pluralité plutôt qu'un point de défaillance unique. Les modèles qui
    échouent sont ignorés ; on renvoie ce qui a répondu."""
    config = config or load_config()
    env = env if env is not None else os.environ
    spec = config.get("roles", {}).get(role, {})
    max_tokens = spec.get("max_tokens", 1024)
    results: list[Result] = []
    for model, provider in callable_route(role, config, env)[:k]:
        t0 = time.time()
        try:
            text, itk, otk = _call_one(model, provider, system, user, max_tokens, env, transport)
        except OrchestratorError as exc:
            _log(ledger_path, role, model, provider, False, int((time.time() - t0) * 1000), 0.0, str(exc))
            continue
        latency = int((time.time() - t0) * 1000)
        cost = estimate_cost(provider, itk, otk, config.get("prices"))
        _log(ledger_path, role, model, provider, True, latency, cost, "")
        results.append(Result(role, model, provider, text, itk, otk, cost, latency, []))
    if not results:
        raise OrchestratorError(f"Aucun avis obtenu pour le conseil « {role} ».")
    return results


def _log(path: Path | None, role, model, provider, ok, latency_ms, cost, detail):
    if path is None:
        return
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "role": role,
           "model": model, "provider": provider, "ok": ok,
           "latency_ms": latency_ms, "cost_usd": cost}
    if detail:
        rec["detail"] = detail[:200]
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def health(config: dict | None = None, env: dict | None = None) -> dict:
    """État du sang : quels rôles sont réellement servables, et par quoi.
    Sans clé → dégradation visible, pas de plantage. Diagnostic pur."""
    config = config or load_config()
    env = env if env is not None else os.environ
    avail = available_providers(env)
    roles = {}
    for role in config.get("roles", {}):
        route_ = callable_route(role, config, env)
        roles[role] = {
            "servable": bool(route_),
            "active_model": route_[0][0] if route_ else None,
            "active_provider": route_[0][1] if route_ else None,
            "fallbacks_ready": max(len(route_) - 1, 0),
        }
    return {"providers_available": sorted(avail), "roles": roles}
