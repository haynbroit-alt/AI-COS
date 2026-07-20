"""Tests de terrain/outreach.py — envoi Resend en stdlib, transport simulé.

Aucun appel réseau : le transport est injecté. Couvre le cas normal (envoi des
'pending'), le cas erreur (clé absente / HTTP), le cas limite (aucune cible
'pending', déduplication par statut)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# terrain/ n'est pas un package importable : chargement par chemin.
_SPEC = importlib.util.spec_from_file_location(
    "outreach", Path(__file__).resolve().parent.parent / "terrain" / "outreach.py"
)
outreach = importlib.util.module_from_spec(_SPEC)
# Enregistrer avant exec : le dataclass résout ses annotations (str, via
# `from __future__ import annotations`) en cherchant le module dans sys.modules.
sys.modules["outreach"] = outreach
_SPEC.loader.exec_module(outreach)


def _write_targets(tmp_path: Path, statuses: list[str]) -> Path:
    targets = [
        {
            "company": f"C{i}",
            "email": f"c{i}@example.com",
            "status": st,
            "idempotency_key": f"k{i}",
            "subject": "Re: test",
            "text": "corps",
        }
        for i, st in enumerate(statuses)
    ]
    config = {
        "defaults": {
            "from": "Velyx <hello@velyx.org>",
            "reply_to": "velyx.org@outlook.com",
            "headers": {"List-Unsubscribe": "<mailto:hello@velyx.org>"},
        },
        "targets": targets,
    }
    path = tmp_path / "t.json"
    path.write_text(json.dumps(config))
    return path


class _FakeTransport:
    """Capture les envois et renvoie un id, sans réseau."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append({"url": url, "headers": headers, "body": json.loads(body)})
        return {"id": f"id-{len(self.calls)}"}


# --- cas normal -----------------------------------------------------------

def test_relance_envoie_seulement_les_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    path = _write_targets(tmp_path, ["pending", "bounced", "pending"])
    fake = _FakeTransport()
    report = outreach.relance(path, sender=outreach.ResendSender(transport=fake))

    sent = [r for r in report if r["status"] == "sent"]
    skipped = [r for r in report if r["status"].startswith("skipped")]
    assert len(sent) == 2
    assert len(skipped) == 1
    # Les defaults sont fusionnés dans le payload envoyé.
    first = fake.calls[0]["body"]
    assert first["from"] == "Velyx <hello@velyx.org>"
    assert first["reply_to"] == "velyx.org@outlook.com"
    assert first["to"] == ["c0@example.com"]
    # Idempotency-Key transmis en en-tête.
    assert fake.calls[0]["headers"]["Idempotency-Key"] == "k0"


def test_dry_run_n_envoie_rien(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    path = _write_targets(tmp_path, ["pending", "pending"])
    fake = _FakeTransport()
    report = outreach.relance(path, dry_run=True, sender=outreach.ResendSender(transport=fake))
    assert all(r["status"] == "dry-run" for r in report)
    assert fake.calls == []  # aucun envoi réel


# --- cas erreur -----------------------------------------------------------

def test_cle_absente_leve_filet(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    path = _write_targets(tmp_path, ["pending"])
    report = outreach.relance(path, sender=outreach.ResendSender())
    # L'erreur est capturée par cible, pas propagée : rapport 'error'.
    assert report[0]["status"] == "error"
    assert "RESEND_API_KEY" in report[0]["error"]


def test_http_error_remonte_en_erreur(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    path = _write_targets(tmp_path, ["pending"])

    def boom(url, headers, body):
        raise outreach.OutreachError("Resend HTTP 422 : invalid from")

    report = outreach.relance(path, sender=outreach.ResendSender(transport=boom))
    assert report[0]["status"] == "error"
    assert "422" in report[0]["error"]


def test_fichier_cibles_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    with pytest.raises(outreach.OutreachError):
        outreach.relance(tmp_path / "absent.json")


# --- cas limite -----------------------------------------------------------

def test_aucune_cible_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    path = _write_targets(tmp_path, ["bounced", "replied", "stop"])
    fake = _FakeTransport()
    report = outreach.relance(path, sender=outreach.ResendSender(transport=fake))
    assert fake.calls == []
    assert all(r["status"].startswith("skipped") for r in report)
