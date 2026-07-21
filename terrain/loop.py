"""Boucle terrain autonome — fiabilité + autonomie (objectif 10/10).

Capacités :
- REPRISE après panne : état par jour idempotent (terrain/loop_state.json). Une
  étape « done » n'est jamais rejouée (pas de double cycle, pas de double envoi) ;
  une étape échouée est retentée à la prochaine exécution.
- RETRY avec backoff exponentiel par étape (réseau/GitHub indisponible → réessai).
- JOURNAL complet : chaque exécution et chaque étape sont écrites en append dans
  terrain/runs.jsonl (rejouable, auditable).
- ALERTE seulement si intervention humaine nécessaire : classify_alert ne lève un
  drapeau que pour un vrai besoin (secret absent, réponse prospect à traiter,
  échec persistant) — sinon silence.

La logique d'orchestration est pure et injectable (étapes = callables). Le câblage
réel (Stripe/Resend/git) vit dans _main, hors du chemin testé.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

HERE = Path(__file__).parent
STATE_PATH = HERE / "loop_state.json"
LEDGER_PATH = HERE / "runs.jsonl"

# Une étape : callable sans argument → (ok, detail). Pas de réseau en test.
Step = Callable[[], "tuple[bool, str]"]
SleepFn = Callable[[float], None]
Clock = Callable[[], str]

FAIL_ALERT_THRESHOLD = 3  # échecs consécutifs avant alerte humaine


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"date": None, "steps": {}, "fail_counts": {}}
    return json.loads(path.read_text())


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def reset_if_new_day(state: dict, today: str) -> dict:
    """Nouveau jour → repartir de zéro sur les étapes (les fail_counts persistent
    pour détecter un échec persistant multi-jours)."""
    if state.get("date") != today:
        state = {"date": today, "steps": {}, "fail_counts": state.get("fail_counts", {})}
    return state


def run_step(name: str, fn: Step, retries: int, sleep_fn: SleepFn) -> tuple[bool, str]:
    """Exécute fn avec retry + backoff exponentiel (2,4,8… s). Renvoie (ok, detail)."""
    last = ""
    for attempt in range(retries):
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 — une étape ne doit jamais tuer la boucle
            ok, detail = False, f"exception: {exc}"
        last = detail
        if ok:
            return True, detail
        if attempt < retries - 1:
            sleep_fn(2 ** (attempt + 1))
    return False, last


def classify_alert(
    step_results: dict[str, tuple[bool, str]],
    fail_counts: dict[str, int],
    contacts: list[dict],
    missing_secrets: list[str],
) -> dict:
    """Décide si un humain doit intervenir. Silence par défaut."""
    reasons: list[str] = []
    for secret in missing_secrets:
        reasons.append(f"secret_absent:{secret} — poser la clé (terrain/SETUP-SECRETS.md)")
    for c in contacts:
        if c.get("replied") and not c.get("meeting") and not c.get("signed"):
            reasons.append(f"réponse_prospect_à_traiter:{c.get('email')}")
    for step, count in fail_counts.items():
        if count >= FAIL_ALERT_THRESHOLD:
            reasons.append(f"échec_persistant:{step} ({count}x)")
    return {"needs_human": bool(reasons), "reasons": reasons}


@dataclass
class LoopConfig:
    steps: dict[str, Step]
    plan: list[str]
    contacts: list[dict] = field(default_factory=list)
    missing_secrets: list[str] = field(default_factory=list)
    retries: int = 4
    sleep_fn: SleepFn = time.sleep
    clock: Clock = _now_iso
    today_fn: Callable[[], str] = _today
    state_path: Path = STATE_PATH
    ledger_path: Path = LEDGER_PATH


def _append_ledger(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(cfg: LoopConfig) -> dict:
    """Exécute le plan du jour avec reprise idempotente. Renvoie le rapport."""
    today = cfg.today_fn()
    state = reset_if_new_day(load_state(cfg.state_path), today)
    results: dict[str, tuple[bool, str]] = {}

    for name in cfg.plan:
        if state["steps"].get(name) == "done":
            results[name] = (True, "déjà fait (reprise)")
            continue
        step = cfg.steps.get(name)
        if step is None:
            continue
        ok, detail = run_step(name, step, cfg.retries, cfg.sleep_fn)
        results[name] = (ok, detail)
        state["steps"][name] = "done" if ok else "failed"
        fc = state["fail_counts"]
        fc[name] = 0 if ok else fc.get(name, 0) + 1
        _append_ledger(
            cfg.ledger_path,
            {
                "ts": cfg.clock(),
                "date": today,
                "step": name,
                "ok": ok,
                "detail": detail,
                "fail_count": fc[name],
            },
        )

    save_state(state, cfg.state_path)
    alert = classify_alert(results, state["fail_counts"], cfg.contacts, cfg.missing_secrets)
    report = {
        "date": today,
        "steps": {k: {"ok": v[0], "detail": v[1]} for k, v in results.items()},
        "needs_human": alert["needs_human"],
        "reasons": alert["reasons"],
    }
    _append_ledger(cfg.ledger_path, {"ts": cfg.clock(), "date": today, "run_summary": report})
    return report


# --------------------------------------------------------------------------
# Câblage réel (hors chemin testé) : Stripe/Resend/git via subprocess & stdlib.
# --------------------------------------------------------------------------

def _load_sibling(name: str):
    """Charge un module voisin de terrain/ (répertoire non-paquet)."""
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CAMPAIGN_PATH = HERE / "campaign.json"


def _send_due(kind: str) -> tuple[bool, str]:
    """Envoie les cibles dues du jour (kind = 'relance' | 'initial'), calculées
    par relance_rules depuis campaign.json, puis persiste l'avancement. 0 cible
    due = succès silencieux (la clé Resend n'est exigée que s'il faut envoyer)."""
    rules = _load_sibling("relance_rules")
    campaign = json.loads(CAMPAIGN_PATH.read_text())
    contacts = campaign.get("contacts", [])
    today = _today()
    due = rules.due_relances(contacts, today) if kind == "relance" \
        else rules.due_initials(contacts, today)
    if not due:
        return True, f"0 {kind} due"
    if not os.environ.get("RESEND_API_KEY"):
        return False, "RESEND_API_KEY absent"
    outreach = _load_sibling("outreach")
    sender = outreach.ResendSender()
    report, errors = [], 0
    for contact in due:
        target = rules.build_relance_target(contact, today) if kind == "relance" \
            else rules.build_initial_target(contact, today)
        try:
            res = sender.send(target)
            if kind == "relance":
                contact.setdefault("relances", []).append(today)
            else:
                contact.update(sent=True, sent_date=today, delivered=True)
            report.append({"email": target["email"], "status": "sent", "id": res.get("id")})
        except outreach.OutreachError as exc:
            errors += 1
            report.append({"email": target["email"], "status": "error", "error": str(exc)})
    CAMPAIGN_PATH.write_text(json.dumps(campaign, ensure_ascii=False, indent=2) + "\n")
    return errors == 0, json.dumps(report, ensure_ascii=False)


def _real_plan_and_steps():
    import subprocess

    def read_cycle() -> tuple[bool, str]:
        if not os.environ.get("STRIPE_API_KEY"):
            return False, "STRIPE_API_KEY absent"
        proc = subprocess.run(
            ["python3", "-m", "ai_cos.cli", "--source", "stripe", "--data-dir", "terrain"],
            input="a\n", capture_output=True, text=True, cwd=HERE.parent,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr)[-500:]

    def push() -> tuple[bool, str]:
        import subprocess
        branch = os.environ.get("TERRAIN_BRANCH") or subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=HERE.parent,
        ).stdout.strip() or "main"
        subprocess.run(["git", "add", "terrain/"], cwd=HERE.parent)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"terrain: run auto {_today()}"], cwd=HERE.parent
        )
        proc = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            capture_output=True, text=True, cwd=HERE.parent,
        )
        return proc.returncode == 0, (proc.stdout or proc.stderr)[-300:]

    steps = {
        "read_cycle": read_cycle,
        "relance": lambda: _send_due("relance"),
        "outreach_initial": lambda: _send_due("initial"),
        "push": push,
    }
    plan = ["read_cycle", "relance", "outreach_initial"]
    # En CI (GitHub Actions), le workflow gère le commit/push : LOOP_SKIP_PUSH=1.
    if not os.environ.get("LOOP_SKIP_PUSH"):
        plan.append("push")
    return plan, steps


def _main(argv: list[str]) -> int:
    import argparse
    from metrics import report as metrics_report  # type: ignore

    parser = argparse.ArgumentParser(description="Boucle terrain autonome.")
    parser.add_argument("--relance", action="store_true",
                        help="(déprécié — la relance J+2 est désormais automatique)")
    parser.parse_args(argv)

    plan, steps = _real_plan_and_steps()
    contacts = json.loads(CAMPAIGN_PATH.read_text()).get("contacts", []) \
        if CAMPAIGN_PATH.exists() else []
    rules = _load_sibling("relance_rules")
    send_work_due = bool(
        rules.due_relances(contacts, _today()) or rules.due_initials(contacts, _today())
    )
    missing = [s for s in (["STRIPE_API_KEY"] + (["RESEND_API_KEY"] if send_work_due else []))
               if not os.environ.get(s)]

    cfg = LoopConfig(steps=steps, plan=plan, contacts=contacts, missing_secrets=missing)
    rep = run(cfg)
    rep["kpis"] = metrics_report()["funnel"]

    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if rep["needs_human"]:
        print("ALERTE — intervention humaine requise :", file=__import__("sys").stderr)
        for r in rep["reasons"]:
            print(f"  - {r}", file=__import__("sys").stderr)
    # Code 3 = besoin humain : en CI, le job GitHub Actions échoue → notification
    # e-mail à l'utilisateur (canal d'alerte, sans session de chat). 0 sinon.
    return 3 if rep["needs_human"] else 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
