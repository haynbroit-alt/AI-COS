"""Tests de terrain/autoresponder.py — logique pure, aucun appel réseau.

Couvre : classification (« stop » prime sur « oui »), anti-boucle (no-reply,
adresse propre), planification idempotente (message-id déjà traité, rapport
déjà envoyé à l'expéditeur), extraction d'email, construction de la cible
(threading In-Reply-To), et mise à jour d'état (réessai si envoi échoué)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "autoresponder", Path(__file__).resolve().parent.parent / "terrain" / "autoresponder.py"
)
autoresponder = importlib.util.module_from_spec(_SPEC)
sys.modules["autoresponder"] = autoresponder
_SPEC.loader.exec_module(autoresponder)


def _msg(**kw):
    base = {"message_id": "<m1@x>", "from": "Prospect <p@cabinet.fr>", "subject": "", "text": ""}
    base.update(kw)
    return base


# ── classify_inbound ────────────────────────────────────────────────────

def test_positive_detecte_oui():
    assert autoresponder.classify_inbound(_msg(subject="Oui — 10 opportunités")) == "positive"


def test_positive_detecte_intention_dans_le_corps():
    assert autoresponder.classify_inbound(_msg(text="Envoyez-moi les opportunités")) == "positive"


def test_stop_prime_sur_positive():
    # Un message contenant à la fois « oui » et « stop » doit être un opt-out.
    m = _msg(subject="Oui mais", text="en fait stop, ne plus recevoir")
    assert autoresponder.classify_inbound(m) == "stop"


def test_message_neutre_est_other():
    assert autoresponder.classify_inbound(_msg(text="Qui êtes-vous ?")) == "other"


# ── is_autoreply_sender ─────────────────────────────────────────────────

def test_autoreply_noreply_et_daemon():
    assert autoresponder.is_autoreply_sender("no-reply@corp.com")
    assert autoresponder.is_autoreply_sender("mailer-daemon@x.com")


def test_autoreply_propre_adresse():
    assert autoresponder.is_autoreply_sender("hello@velyx.org")


def test_expediteur_humain_valide():
    assert not autoresponder.is_autoreply_sender("directeur@cabinet.fr")


def test_sender_email_extrait_des_chevrons():
    assert autoresponder._sender_email({"from": "Jean Dupont <jean@cabinet.fr>"}) == "jean@cabinet.fr"


# ── plan_actions ────────────────────────────────────────────────────────

def test_plan_positive_donne_report():
    acts = autoresponder.plan_actions([_msg(subject="oui")], {})
    assert [a["action"] for a in acts] == ["report"]


def test_plan_ignore_message_deja_traite():
    state = {"handled": ["<m1@x>"]}
    assert autoresponder.plan_actions([_msg(message_id="<m1@x>", subject="oui")], state) == []


def test_plan_ne_renvoie_pas_deux_fois_le_rapport():
    state = {"report_sent": ["p@cabinet.fr"]}
    acts = autoresponder.plan_actions([_msg(message_id="<m2@x>", subject="oui")], state)
    assert acts[0]["action"] == "skip"


def test_plan_dedup_intra_run_meme_expediteur():
    # Deux « oui » du MÊME expéditeur dans un seul run → 1 rapport, 1 skip
    # (régression : sans dédup intra-run, les deux partaient).
    msgs = [
        _msg(message_id="<m1@x>", subject="Oui — 10 opportunités"),
        _msg(message_id="<m2@x>", subject="Oui encore"),
    ]
    acts = autoresponder.plan_actions(msgs, {})
    assert [a["action"] for a in acts] == ["report", "skip"]


def test_plan_stop_puis_human():
    msgs = [
        _msg(message_id="<a@x>", from_=None, subject="stop"),
        _msg(message_id="<b@x>", subject="une question"),
    ]
    # corriger la clé 'from'
    msgs[0]["from"] = "p@cabinet.fr"
    acts = autoresponder.plan_actions(msgs, {})
    assert [a["action"] for a in acts] == ["stop", "human"]


# ── build_report_target ─────────────────────────────────────────────────

def test_build_target_thread_et_idempotence():
    act = {"message_id": "<CAG123@mail.gmail.com>", "sender": "p@cabinet.fr", "subject": "Oui"}
    tgt = autoresponder.build_report_target(act)
    assert tgt["email"] == "p@cabinet.fr"
    assert tgt["subject"] == "Re: Oui"
    assert tgt["headers"]["In-Reply-To"] == "<CAG123@mail.gmail.com>"
    assert tgt["idempotency_key"].startswith("velyx-report-")
    assert tgt["from"] == autoresponder.FROM


def test_build_target_prefixe_re_si_absent():
    act = {"message_id": "x", "sender": "p@cabinet.fr", "subject": "Demande info"}
    assert autoresponder.build_report_target(act)["subject"] == "Re: Demande info"


# ── personnalisation via le cœur (repli garanti) ─────────────────────────

def test_compose_report_defaut_contient_corps_et_optout():
    txt = autoresponder.compose_report(None)
    assert txt.startswith("Bonjour")
    assert "SYNANTO" in txt and "199 €/mois" in txt
    assert txt.rstrip().endswith("répondez « stop ».")


def test_compose_report_intro_personnalisee_remplace_intro_garde_corps():
    txt = autoresponder.compose_report("Ravi de votre retour rapide !")
    assert txt.startswith("Ravi de votre retour rapide !")
    assert "Merci pour votre" not in txt          # intro figée remplacée
    assert "QUANTUM SURGICAL" in txt              # corps factuel préservé
    assert "répondez « stop »." in txt            # opt-out préservé


def test_sane_intro_rejette_trop_long_ou_vide():
    assert autoresponder.sane_intro("Bonjour, ravi !") == "Bonjour, ravi !"
    assert autoresponder.sane_intro("") is None
    assert autoresponder.sane_intro(None) is None
    assert autoresponder.sane_intro("x" * 401) is None
    assert autoresponder.sane_intro("a\n" * 8) is None


def test_personalized_intro_utilise_le_coeur():
    class _Res:
        text = "  Merci de votre réactivité — voici ce que Velyx a repéré chez vous.  "
    got = autoresponder.personalized_intro(
        "dg@cabinet.fr", "oui envoyez",
        route_fn=lambda role, user, system: _Res())
    assert got == "Merci de votre réactivité — voici ce que Velyx a repéré chez vous."


def test_personalized_intro_repli_si_coeur_echoue():
    def boom(role, user, system):
        raise RuntimeError("pas de clé LLM")
    assert autoresponder.personalized_intro("dg@cabinet.fr", "oui", route_fn=boom) is None


def test_personalized_intro_repli_si_sortie_hors_gabarit():
    class _Res:
        text = "x" * 500  # trop long → rejeté
    assert autoresponder.personalized_intro(
        "dg@cabinet.fr", "oui", route_fn=lambda r, u, s: _Res()) is None


def test_build_target_intro_personnalisee_thread_ok():
    act = {"message_id": "<CAG@mail>", "sender": "p@cabinet.fr", "subject": "Oui"}
    tgt = autoresponder.build_report_target(act, "Intro sur-mesure.")
    assert tgt["text"].startswith("Intro sur-mesure.")
    assert "SYNANTO" in tgt["text"]
    assert tgt["headers"]["In-Reply-To"] == "<CAG@mail>"


# ── apply_result ────────────────────────────────────────────────────────

def test_apply_report_ok_marque_handled_et_reported():
    state = {}
    act = {"message_id": "<m@x>", "sender": "p@cabinet.fr", "action": "report"}
    autoresponder.apply_result(state, act, True)
    assert "<m@x>" in state["handled"]
    assert "p@cabinet.fr" in state["report_sent"]


def test_apply_report_echoue_ne_marque_pas_handled():
    # Envoi raté → message NON marqué handled pour réessayer au prochain run.
    state = {}
    act = {"message_id": "<m@x>", "sender": "p@cabinet.fr", "action": "report"}
    autoresponder.apply_result(state, act, False)
    assert "<m@x>" not in state.get("handled", [])
    assert "p@cabinet.fr" not in state.get("report_sent", [])


def test_apply_stop_ajoute_opt_out():
    state = {}
    act = {"message_id": "<m@x>", "sender": "p@cabinet.fr", "action": "stop"}
    autoresponder.apply_result(state, act, False)
    assert "p@cabinet.fr" in state["opt_out"]
    assert "<m@x>" in state["handled"]
