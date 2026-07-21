"""Règles d'engagement génériques — envoi initial et relance J+2, fonctions pures.

Règles d'envoi Velyx (terrain/relance-J2-plus2.md, terrain/prospection-J2.md) :
- envoi initial : cap quotidien global, adresses génériques pro publiques, opt-out ;
- relance unique à J+2 sans réponse — jamais de suivi au-delà ;
- bounce, réponse ou « stop » → exclusion définitive.

Tout est dérivé de campaign.json : chaque contact porte sent/sent_date/bounced/
replied/status/subject/hook/relances. Aucun fichier de cibles à maintenir à la
main — les cibles du jour sont calculées, pas listées.
"""
from __future__ import annotations

from datetime import date, timedelta

RELANCE_DELAY_DAYS = 2
MAX_RELANCES = 1
DAILY_SEND_CAP = 5  # cap global (initiaux + relances) par jour

SEND_DEFAULTS = {
    "from": "Charfa — Velyx <hello@velyx.org>",
    "reply_to": "velyx.org@outlook.com",
    "headers": {"List-Unsubscribe": "<mailto:hello@velyx.org?subject=unsubscribe>"},
}

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

RELANCE_TEXT = (
    "Bonjour,\n\n"
    "Je reviens en un mot sur mon message de {jour} à propos de Velyx.\n\n"
    "Pas de souci si le timing n'est pas le bon — un simple « pas pour nous » "
    "et je vous laisse tranquille. Si {hook} vous parle, 15 min suffisent à "
    "vous montrer.\n\n"
    "Charfa — Velyx\n\n"
    "Pour ne plus recevoir de message : répondez « stop »."
)

_PREUVE = (
    "Pour vous le prouver plutôt que le raconter : je vous envoie gratuitement "
    "10 opportunités détectées sur votre marché (signal daté, source, angle "
    "d'approche), sans condition.\n\n"
    "Si {hook} vous parle : un simple « oui » suffit.\n\n"
    "Charfa — Velyx\n\n"
    "Pour ne plus recevoir de message : répondez « stop »."
)

# L'appât = preuve gratuite de valeur, par moment de douleur (terrain/OFFRE.md).
INITIAL_TEXTS = {
    "agence": (
        "Bonjour,\n\n"
        "Velyx est un radar commercial : nous trouvons les entreprises qui ont "
        "une raison d'acheter maintenant — pas des listes, des comptes avec une "
        "raison datée.\n\n" + _PREUVE
    ),
    "recrute_sdr": (
        "Bonjour,\n\n"
        "{company} recrute actuellement côté commercial — pendant que le "
        "recrutement suit son cours, le pipeline attend.\n\n"
        "Velyx est un radar commercial : nous trouvons les entreprises qui ont "
        "une raison d'acheter maintenant.\n\n" + _PREUVE
    ),
    "post_levee": (
        "Bonjour,\n\n"
        "{company} vient de boucler une levée — félicitations. Le défi qui "
        "suit est connu : transformer ce budget en croissance commerciale.\n\n"
        "Velyx est un radar commercial : nous trouvons les entreprises qui ont "
        "une raison d'acheter maintenant.\n\n" + _PREUVE
    ),
}
INITIAL_TEXT = INITIAL_TEXTS["agence"]  # défaut historique


def _slug(company: str) -> str:
    return "".join(ch for ch in company.lower() if ch.isalnum())


def _excluded(contact: dict) -> bool:
    return bool(
        contact.get("bounced")
        or contact.get("replied")
        or contact.get("status") == "stop"
    )


def sends_today(contacts: list[dict], today: str) -> int:
    """Nombre d'emails déjà partis aujourd'hui (initiaux + relances)."""
    return sum(1 for c in contacts if c.get("sent_date") == today) + sum(
        1 for c in contacts for d in c.get("relances", []) if d == today
    )


def due_relances(contacts: list[dict], today: str) -> list[dict]:
    """Contacts à relancer aujourd'hui : envoyés il y a ≥ J+2, silencieux,
    non bounced, jamais relancés. Le cap quotidien s'applique en aval."""
    due = []
    threshold = date.fromisoformat(today) - timedelta(days=RELANCE_DELAY_DAYS)
    for c in contacts:
        if not c.get("sent") or _excluded(c):
            continue
        if len(c.get("relances", [])) >= MAX_RELANCES:
            continue
        sent_date = c.get("sent_date")
        if not sent_date or date.fromisoformat(sent_date) > threshold:
            continue
        due.append(c)
    return due


def due_initials(contacts: list[dict], today: str) -> list[dict]:
    """Contacts en file (jamais contactés), dans la limite du budget du jour."""
    budget = DAILY_SEND_CAP - sends_today(contacts, today)
    queued = [c for c in contacts if not c.get("sent") and not _excluded(c)]
    return queued[: max(budget, 0)]


def build_relance_target(contact: dict, today: str) -> dict:
    jour = _JOURS[date.fromisoformat(contact["sent_date"]).weekday()]
    return {
        **SEND_DEFAULTS,
        "email": contact["email"],
        "subject": f"Re: {contact['subject']}",
        "text": RELANCE_TEXT.format(jour=jour, hook=contact["hook"]),
        "idempotency_key": f"velyx-relance-{_slug(contact['company'])}-{today.replace('-', '')}",
    }


def apply_last_event(contact: dict, event: str) -> bool:
    """Applique un statut Resend (last_event) au contact. Renvoie True si changé.

    bounced → exclusion définitive ; complained → « stop » ; delivered →
    confirme la délivrance. Tout autre événement est ignoré."""
    if event == "bounced" and not contact.get("bounced"):
        contact["bounced"] = True
        contact["delivered"] = False
        return True
    if event == "complained" and contact.get("status") != "stop":
        contact["status"] = "stop"
        return True
    if event == "delivered" and not contact.get("delivered"):
        contact["delivered"] = True
        return True
    return False


def build_initial_target(contact: dict, today: str) -> dict:
    template = INITIAL_TEXTS[contact.get("template", "agence")]
    return {
        **SEND_DEFAULTS,
        "email": contact["email"],
        "subject": contact["subject"],
        "text": template.format(company=contact["company"], hook=contact["hook"]),
        "idempotency_key": f"velyx-initial-{_slug(contact['company'])}-{today.replace('-', '')}",
    }
