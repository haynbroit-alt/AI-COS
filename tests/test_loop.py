"""Tests de terrain/loop.py et terrain/metrics.py — logique pure, zéro réseau.

Couvre : reprise idempotente (une étape 'done' n'est pas rejouée), retry avec
backoff, journal en append, classification d'alerte (silence vs besoin humain),
et les KPIs de funnel (dont division par zéro)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TERRAIN = Path(__file__).resolve().parent.parent / "terrain"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TERRAIN / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


loop = _load("loop")
metrics = _load("metrics")


def _cfg(tmp_path, steps, plan, **kw):
    today = kw.pop("today", "2026-07-21")
    return loop.LoopConfig(
        steps=steps,
        plan=plan,
        sleep_fn=lambda _s: None,  # pas d'attente réelle
        clock=lambda: "2026-07-21T08:00:00Z",
        today_fn=lambda: today,
        state_path=tmp_path / "state.json",
        ledger_path=tmp_path / "runs.jsonl",
        **kw,
    )


# --- retry ---------------------------------------------------------------

def test_retry_reussit_apres_echecs(tmp_path):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return (calls["n"] >= 3, f"tentative {calls['n']}")

    cfg = _cfg(tmp_path, {"s": flaky}, ["s"], retries=4)
    rep = loop.run(cfg)
    assert rep["steps"]["s"]["ok"] is True
    assert calls["n"] == 3  # a réessayé jusqu'au succès


def test_echec_apres_epuisement_retries(tmp_path):
    cfg = _cfg(tmp_path, {"s": lambda: (False, "down")}, ["s"], retries=2)
    rep = loop.run(cfg)
    assert rep["steps"]["s"]["ok"] is False


# --- reprise idempotente -------------------------------------------------

def test_reprise_ne_rejoue_pas_les_done(tmp_path):
    hits = {"read": 0, "push": 0}

    def read():
        hits["read"] += 1
        return True, "ok"

    def push_fail():
        hits["push"] += 1
        return False, "github down"

    # 1re exécution : read ok, push échoue.
    cfg1 = _cfg(tmp_path, {"read_cycle": read, "push": push_fail}, ["read_cycle", "push"], retries=1)
    loop.run(cfg1)
    assert hits == {"read": 1, "push": 1}

    # 2e exécution même jour : read NON rejoué (reprise), push retenté.
    def push_ok():
        hits["push"] += 1
        return True, "poussé"

    cfg2 = _cfg(tmp_path, {"read_cycle": read, "push": push_ok}, ["read_cycle", "push"], retries=1)
    rep = loop.run(cfg2)
    assert hits["read"] == 1  # pas de double cycle
    assert hits["push"] == 2
    assert rep["steps"]["read_cycle"]["detail"].startswith("déjà fait")
    assert rep["steps"]["push"]["ok"] is True


def test_nouveau_jour_reinitialise(tmp_path):
    read = lambda: (True, "ok")  # noqa: E731
    cfg1 = _cfg(tmp_path, {"read_cycle": read}, ["read_cycle"], today="2026-07-21", retries=1)
    loop.run(cfg1)
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["date"] == "2026-07-21"
    cfg2 = _cfg(tmp_path, {"read_cycle": read}, ["read_cycle"], today="2026-07-22", retries=1)
    loop.run(cfg2)
    state2 = json.loads((tmp_path / "state.json").read_text())
    assert state2["date"] == "2026-07-22"


# --- journal -------------------------------------------------------------

def test_journal_append(tmp_path):
    cfg = _cfg(tmp_path, {"s": lambda: (True, "ok")}, ["s"], retries=1)
    loop.run(cfg)
    lines = (tmp_path / "runs.jsonl").read_text().strip().splitlines()
    assert len(lines) >= 2  # 1 ligne d'étape + 1 résumé
    assert any("run_summary" in ln for ln in lines)


# --- alerte : silence par défaut, humain seulement si nécessaire ---------

def test_pas_d_alerte_quand_tout_va_bien(tmp_path):
    cfg = _cfg(tmp_path, {"s": lambda: (True, "ok")}, ["s"], retries=1, contacts=[], missing_secrets=[])
    rep = loop.run(cfg)
    assert rep["needs_human"] is False
    assert rep["reasons"] == []


def test_alerte_reponse_prospect(tmp_path):
    contacts = [{"email": "a@x.fr", "replied": True, "meeting": False, "signed": False}]
    cfg = _cfg(tmp_path, {"s": lambda: (True, "ok")}, ["s"], retries=1, contacts=contacts)
    rep = loop.run(cfg)
    assert rep["needs_human"] is True
    assert any("réponse_prospect_à_traiter" in r for r in rep["reasons"])


def test_alerte_secret_absent(tmp_path):
    cfg = _cfg(tmp_path, {"s": lambda: (True, "ok")}, ["s"], retries=1, missing_secrets=["STRIPE_API_KEY"])
    rep = loop.run(cfg)
    assert rep["needs_human"] is True
    assert any("secret_absent" in r for r in rep["reasons"])


def test_alerte_echec_persistant(tmp_path):
    # 3 exécutions ratées le même jour → seuil atteint.
    for _ in range(3):
        cfg = _cfg(tmp_path, {"push": lambda: (False, "down")}, ["push"], retries=1)
        rep = loop.run(cfg)
    assert rep["needs_human"] is True
    assert any("échec_persistant:push" in r for r in rep["reasons"])


# --- KPIs ----------------------------------------------------------------

def test_funnel_taux(tmp_path):
    contacts = [
        {"sent": True, "delivered": True, "replied": True, "meeting": True, "signed": True, "revenue_eur": 290},
        {"sent": True, "delivered": True, "replied": False},
        {"sent": True, "delivered": False, "bounced": True},
    ]
    f = metrics.compute_funnel(contacts)
    assert f.sent == 3 and f.delivered == 2 and f.bounced == 1
    assert f.delivery_rate == 2 / 3
    assert f.reply_rate == 1 / 2
    assert f.revenue_eur == 290
    d = f.as_dict()
    assert d["sign_rate"] == "100%"


def test_funnel_division_par_zero(tmp_path):
    f = metrics.compute_funnel([])
    assert f.delivery_rate is None
    assert f.as_dict()["delivery_rate"] == "n/a"


def test_funnel_chaine_valeur_complete(tmp_path):
    # La métrique qui compte : réponse positive → rapport demandé → appel → paiement.
    contacts = [
        {"sent": True, "delivered": True, "replied": True, "positive_reply": True,
         "report_requested": True, "meeting": True, "signed": True, "revenue_eur": 290},
        {"sent": True, "delivered": True, "replied": True, "positive_reply": False},
        {"sent": True, "delivered": True},
    ]
    f = metrics.compute_funnel(contacts)
    assert f.replies == 2 and f.positive_replies == 1 and f.report_requests == 1
    d = f.as_dict()
    assert d["positive_rate"] == "50%"   # 1 positive / 2 réponses
    assert d["report_rate"] == "100%"    # 1 rapport / 1 positive
    assert d["meeting_rate"] == "100%"   # 1 appel / 1 rapport
    assert d["sign_rate"] == "100%"      # 1 paiement / 1 appel
