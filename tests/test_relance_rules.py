"""Règles d'engagement (terrain/relance_rules.py) — pures, zéro réseau.

Couvre : relance due exactement à J+2 (pas avant, rattrapée après), exclusions
définitives (bounce, réponse, stop, relance déjà faite), cap quotidien global
sur les envois initiaux, et la construction des cibles (sujet, texte, clé
d'idempotence)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TERRAIN = Path(__file__).resolve().parent.parent / "terrain"

spec = importlib.util.spec_from_file_location("relance_rules", TERRAIN / "relance_rules.py")
rules = importlib.util.module_from_spec(spec)
sys.modules["relance_rules"] = rules
spec.loader.exec_module(rules)


def _contact(**kw):
    base = {
        "company": "Captain Prospect",
        "email": "hello@captainprospect.fr",
        "sent": True,
        "sent_date": "2026-07-20",
        "delivered": True,
        "bounced": False,
        "replied": False,
        "subject": "Détecter l'intention d'achat avant l'approche",
        "hook": "détecter les signaux d'achat en amont de vos SDR",
        "relances": [],
    }
    base.update(kw)
    return base


# --- relance J+2 ---------------------------------------------------------

def test_relance_due_a_j_plus_2_pas_avant():
    c = _contact(sent_date="2026-07-20")
    assert rules.due_relances([c], "2026-07-21") == []          # J+1 : trop tôt
    assert rules.due_relances([c], "2026-07-22") == [c]         # J+2 : due
    assert rules.due_relances([c], "2026-07-25") == [c]         # rattrapage : toujours due


def test_relance_exclusions_definitives():
    assert rules.due_relances([_contact(bounced=True)], "2026-07-22") == []
    assert rules.due_relances([_contact(replied=True)], "2026-07-22") == []
    assert rules.due_relances([_contact(status="stop")], "2026-07-22") == []
    assert rules.due_relances([_contact(sent=False, sent_date=None)], "2026-07-22") == []


def test_relance_unique_jamais_de_seconde():
    deja_relance = _contact(relances=["2026-07-22"])
    assert rules.due_relances([deja_relance], "2026-07-30") == []


# --- envoi initial + cap quotidien ---------------------------------------

def test_initiaux_respectent_le_cap_global():
    pool = [_contact(company=f"Agence {i}", email=f"c{i}@x.fr", sent=False, sent_date=None)
            for i in range(10)]
    assert len(rules.due_initials(pool, "2026-07-23")) == rules.DAILY_SEND_CAP


def test_cap_compte_les_envois_du_jour():
    # 2 relances parties aujourd'hui + 1 initial envoyé aujourd'hui → budget 2.
    contacts = [
        _contact(company="A", email="a@x.fr", relances=["2026-07-22"]),
        _contact(company="B", email="b@x.fr", relances=["2026-07-22"]),
        _contact(company="C", email="c@x.fr", sent_date="2026-07-22"),
    ] + [_contact(company=f"Q{i}", email=f"q{i}@x.fr", sent=False, sent_date=None)
         for i in range(5)]
    assert rules.sends_today(contacts, "2026-07-22") == 3
    assert len(rules.due_initials(contacts, "2026-07-22")) == 2


def test_initiaux_excluent_stop():
    pool = [_contact(sent=False, sent_date=None, status="stop")]
    assert rules.due_initials(pool, "2026-07-23") == []


def test_initiaux_excluent_paused():
    # Cible gelée (adresse non vérifiée) → jamais envoyée tant que paused.
    pool = [_contact(sent=False, sent_date=None, status="paused")]
    assert rules.due_initials(pool, "2026-07-23") == []


# --- application des statuts Resend --------------------------------------

def test_bounce_exclut_definitivement():
    c = _contact()
    assert rules.apply_last_event(c, "bounced") is True
    assert c["bounced"] is True and c["delivered"] is False
    assert rules.due_relances([c], "2026-07-30") == []
    assert rules.apply_last_event(c, "bounced") is False  # idempotent


def test_plainte_devient_stop():
    c = _contact()
    assert rules.apply_last_event(c, "complained") is True
    assert c["status"] == "stop"
    assert rules.due_relances([c], "2026-07-30") == []


def test_delivered_confirme_sans_exclure():
    c = _contact(delivered=False)
    assert rules.apply_last_event(c, "delivered") is True
    assert c["delivered"] is True
    assert rules.due_relances([c], "2026-07-22") == [c]


def test_evenement_inconnu_ignore():
    c = _contact()
    assert rules.apply_last_event(c, "opened") is False
    assert rules.apply_last_event(c, "") is False


# --- construction des cibles ---------------------------------------------

def test_cible_relance_complete():
    tgt = rules.build_relance_target(_contact(), "2026-07-22")
    assert tgt["subject"] == "Re: Détecter l'intention d'achat avant l'approche"
    assert tgt["email"] == "hello@captainprospect.fr"
    assert "mon message de lundi" in tgt["text"]          # 2026-07-20 = lundi
    assert "détecter les signaux d'achat" in tgt["text"]
    assert "répondez « stop »" in tgt["text"]
    assert tgt["idempotency_key"] == "velyx-relance-captainprospect-20260722"
    assert tgt["reply_to"] == "velyx.org@outlook.com"
    assert "List-Unsubscribe" in tgt["headers"]


def test_cible_initiale_appat_preuve_gratuite():
    c = _contact(company="Nova Leads", email="contact@novaleads.fr",
                 sent=False, sent_date=None,
                 subject="Des comptes déjà en recherche active",
                 hook="livrer à vos SDR des comptes déjà en recherche")
    tgt = rules.build_initial_target(c, "2026-07-23")
    assert tgt["subject"] == "Des comptes déjà en recherche active"
    assert "10 opportunités" in tgt["text"]          # l'appât : preuve gratuite
    assert "radar commercial" in tgt["text"]          # le positionnement
    assert "livrer à vos SDR" in tgt["text"]
    assert "répondez « stop »" in tgt["text"]
    assert tgt["idempotency_key"] == "velyx-initial-novaleads-20260723"


def test_templates_par_moment_de_douleur():
    sdr = _contact(company="Scaleup", email="c@s.fr", sent=False, sent_date=None,
                   template="recrute_sdr", subject="s",
                   hook="alimenter l'équipe pendant le recrutement")
    txt = rules.build_initial_target(sdr, "2026-07-23")["text"]
    assert "recrute actuellement côté commercial" in txt
    assert "10 opportunités" in txt

    levee = _contact(company="Fintech", email="c@f.fr", sent=False, sent_date=None,
                     template="post_levee", subject="s",
                     hook="transformer votre levée en pipeline")
    txt = rules.build_initial_target(levee, "2026-07-23")["text"]
    assert "boucler une levée" in txt
    assert "croissance commerciale" in txt
