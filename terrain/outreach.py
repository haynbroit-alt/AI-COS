"""Envoi d'outreach/relance via l'API Resend — stdlib pure, zéro MCP.

Rend les Routines robustes : au réveil, plus besoin qu'un connecteur MCP se
reconnecte. La clé vient de RESEND_API_KEY (jamais en dur, jamais commitée),
exactement comme StripeSource pour Stripe.

Usage :
    RESEND_API_KEY=... python3 terrain/outreach.py --relance          # envoie
    RESEND_API_KEY=... python3 terrain/outreach.py --relance --dry-run # simule
    RESEND_API_KEY=... python3 terrain/outreach.py --check            # statuts

Le fichier de cibles (terrain/relance_targets.json) porte un champ "status" par
cible : seules les cibles "pending" sont envoyées. Un bounce ou une réponse se
traduit par un autre statut (bounced/replied/stop) → exclusion automatique.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_TARGETS = Path(__file__).with_name("relance_targets.json")

# Transport injectable pour les tests (aucun appel réseau en test).
Transport = Callable[[str, dict, bytes], dict]


class OutreachError(RuntimeError):
    pass


def _http_post_json(url: str, headers: dict, body: bytes) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:  # 4xx/5xx : corps utile pour le diag
        detail = exc.read().decode(errors="replace")
        raise OutreachError(f"Resend HTTP {exc.code} : {detail}") from exc
    except Exception as exc:  # noqa: BLE001 — urllib lève des types variés
        raise OutreachError(f"Appel Resend échoué : {exc}") from exc


def _http_get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise OutreachError(f"Resend HTTP {exc.code} : {detail}") from exc
    except Exception as exc:  # noqa: BLE001 — urllib lève des types variés
        raise OutreachError(f"Appel Resend échoué : {exc}") from exc


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {_key()}",
        "User-Agent": "velyx-terrain/1.0 (+https://velyx.org)",
    }


def get_last_event(email_id: str) -> str:
    """Dernier événement Resend d'un envoi (delivered/bounced/complained/…)."""
    data = _http_get_json(f"{RESEND_URL}/{email_id}", _auth_headers())
    return data.get("last_event") or ""


def list_received(limit: int = 50) -> list[dict]:
    """Emails entrants (réception activée sur le domaine). Meilleure-effort :
    renvoie [] si l'endpoint n'est pas disponible sur le compte."""
    try:
        data = _http_get_json(f"{RESEND_URL}/receiving?limit={limit}", _auth_headers())
    except OutreachError as exc:
        if any(f"HTTP {code}" in str(exc) for code in (404, 405, 422)):
            return []  # réception non disponible sur le compte
        raise
    return data.get("data") or []


def _key() -> str:
    key = os.environ.get("RESEND_API_KEY", "")
    if not key:
        raise OutreachError(
            "RESEND_API_KEY absent — exportez la clé avant l'envoi (voir "
            "terrain/SETUP-SECRETS.md)."
        )
    return key


@dataclass
class ResendSender:
    """Envoi transactionnel via Resend, avec transport injectable."""

    transport: Transport = _http_post_json

    def send(self, target: dict) -> dict:
        payload = {
            "from": target["from"],
            "to": [target["email"]],
            "subject": target["subject"],
            "text": target["text"],
        }
        if target.get("reply_to"):
            payload["reply_to"] = target["reply_to"]
        if target.get("headers"):
            payload["headers"] = target["headers"]
        body = json.dumps(payload).encode()
        headers = {
            "Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json",
            "Idempotency-Key": target["idempotency_key"],
            # Cloudflare (devant api.resend.com) rejette la signature par
            # défaut de urllib depuis les runners CI (HTTP 403, code 1010).
            "User-Agent": "velyx-terrain/1.0 (+https://velyx.org)",
        }
        return self.transport(RESEND_URL, headers, body)


def load_targets(path: Path) -> dict:
    if not path.exists():
        raise OutreachError(f"Fichier de cibles introuvable : {path}")
    return json.loads(path.read_text())


def relance(
    targets_path: Path = DEFAULT_TARGETS,
    dry_run: bool = False,
    sender: ResendSender | None = None,
) -> list[dict]:
    """Envoie la relance aux seules cibles 'pending'. Retourne un rapport par
    cible tenté : {email, status, id?/error?}."""
    config = load_targets(targets_path)
    defaults = config.get("defaults", {})
    sender = sender or ResendSender()
    report: list[dict] = []
    for tgt in config.get("targets", []):
        if tgt.get("status") != "pending":
            report.append({"email": tgt["email"], "status": f"skipped:{tgt.get('status')}"})
            continue
        merged = {**defaults, **tgt}
        if dry_run:
            report.append({"email": merged["email"], "status": "dry-run"})
            continue
        try:
            res = sender.send(merged)
            report.append({"email": merged["email"], "status": "sent", "id": res.get("id")})
        except OutreachError as exc:
            report.append({"email": merged["email"], "status": "error", "error": str(exc)})
    return report


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Outreach Resend — stdlib, zéro MCP.")
    parser.add_argument("--relance", action="store_true", help="Envoyer la relance aux 'pending'.")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans envoyer.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    args = parser.parse_args(argv)

    if not args.relance:
        parser.print_help()
        return 2
    try:
        report = relance(args.targets, dry_run=args.dry_run)
    except OutreachError as exc:
        print(f"FILET : {exc}", file=sys.stderr)
        return 1
    for line in report:
        print(json.dumps(line, ensure_ascii=False))
    sent = sum(1 for r in report if r["status"] == "sent")
    errors = sum(1 for r in report if r["status"] == "error")
    print(f"— {sent} envoyé(s), {errors} erreur(s)", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
