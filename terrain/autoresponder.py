"""Auto-répondeur terrain — livre le rapport dès qu'un prospect répond « oui ».

Le maillon manquant : un « oui » sur hello@velyx.org doit produire le rapport
AU PIC D'INTÉRÊT, pas le lendemain à la main. Ce module lit la boîte de
réception Resend (GET /emails/receiving), classe chaque entrant, et :

  - « oui »/intérêt  → envoie le rapport (10 opportunités) automatiquement,
                       puis lève un drapeau humain pour le suivi (le RDV) ;
  - « stop »         → opt-out définitif (propagé aux campagnes) ;
  - autre message    → aucun envoi auto, mais drapeau humain (à lire/répondre).

Robustesse : logique pure et testable (transport injectable), zéro MCP au
runtime, idempotent (chaque message-id n'est traité qu'une fois, chaque
expéditeur ne reçoit le rapport qu'une fois), anti-boucle (ignore les
no-reply/mailer-daemon et sa propre adresse). L'état vit dans
terrain/inbound_state.json — rejouable, auditable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
STATE_PATH = HERE / "inbound_state.json"
CAMPAIGN_FILES = ["campaign-montpellier-cabinet.json", "campaign.json"]

FROM = "Charfa — Velyx <hello@velyx.org>"
REPLY_TO = "velyx.org@outlook.com"
OWN_ADDRESSES = {"hello@velyx.org", "velyx.org@outlook.com"}

# Marqueurs de classification (minuscules, sans accents comparés en souple).
STOP_MARKERS = ("stop", "desabonn", "désabonn", "unsubscribe", "ne plus recevoir")
POSITIVE_MARKERS = (
    "oui", "envoyez", "envoie", "interesse", "intéressé", "interessé", "intéresse",
    "volontiers", "les opportunites", "les opportunités", "je veux", "ok pour",
    "avec plaisir", "ca m'interesse", "ça m'intéresse", "go ",
)
AUTOREPLY_MARKERS = (
    "no-reply", "noreply", "no_reply", "mailer-daemon", "postmaster",
    "donotreply", "do-not-reply", "notifications@", "bounce",
)

REPORT_SUBJECT_FALLBACK = "Re: Oui — 10 opportunités gratuites"

# Le rapport livré — identique à l'envoi manuel de démonstration. Échantillon
# Montpellier (velyx-rapport-montpellier.md), voix de marque « radar commercial ».
REPORT_TEXT = (
    "Bonjour,\n\n"
    "Merci pour votre « oui ». Voici les opportunités détectées sur le marché "
    "recrutement tech Montpellier / Occitanie — chaque ligne est une entreprise "
    "qui montre un signal de recrutement AVANT d'avoir lancé une recherche "
    "cabinet.\n\n"
    "1) SYNANTO — Montpellier · Priorité HAUTE\n"
    "   Signal : plusieurs offres mobiles simultanées (iOS Senior, Android Kotlin "
    "Multiplatform).\n"
    "   Décideur probable : CTO / Head of Mobile.\n"
    "   Pourquoi maintenant : le recrutement multiple simultané signale une "
    "échéance produit ; le coût du poste vacant croît chaque semaine.\n\n"
    "2) TEAM.IS — Montpellier · Priorité HAUTE\n"
    "   Signal : recrutements tech en volume (C#/.NET, Angular, C++, DevOps IA, "
    "UX/UI).\n"
    "   Décideur probable : DRH / Head of Engineering.\n"
    "   Pourquoi maintenant : 5 familles de postes ouvertes en parallèle = "
    "croissance structurelle, budget récurrent.\n\n"
    "3) STARTUP DEEPTECH SANTÉ — Montpellier · Priorité HAUTE\n"
    "   Signal : Computer Vision, Ingénieur IA, Vision 3D.\n"
    "   Décideur probable : CTO / VP Engineering.\n"
    "   Pourquoi maintenant : le vivier IA santé est étroit ; le premier cabinet "
    "consulté prend le mandat.\n\n"
    "4) TSS (Technologie Sobriété Soutenable) · Priorité MOYENNE\n"
    "   Signal : recherche de profils dirigeants IA, croissance startup.\n"
    "   Décideur probable : CEO / fondateurs.\n"
    "   Pourquoi maintenant : un recrutement dirigeant raté coûte 12-18 mois ; "
    "l'anticipation est l'argument.\n\n"
    "5) STARTUP TRAVELTECH — Montpellier · Priorité MOYENNE\n"
    "   Signal : Fullstack FastAPI/React, recrutement développeur.\n"
    "   Décideur probable : CTO / Lead Dev.\n"
    "   Pourquoi maintenant : fenêtre courte — un poste unique se pourvoit vite "
    "ou s'externalise.\n\n"
    "6) QUANTUM SURGICAL — Montpellier · Priorité HAUTE\n"
    "   Signal : IA médicale, croissance internationale, expansion d'équipe.\n"
    "   Décideur probable : VP Engineering / DRH.\n"
    "   Pourquoi maintenant : l'expansion internationale multiplie les postes non "
    "publiés en France.\n\n"
    "—\n\n"
    "Ces opportunités sont un échantillon. En abonnement Radar (199 €/mois), elles "
    "arrivent chaque semaine, filtrées sur vos spécialités et votre zone. Si l'une "
    "d'elles génère un rendez-vous, on parle d'un modèle au résultat — sinon aucun "
    "engagement.\n\n"
    "Un créneau de 15 min cette semaine pour vous les commenter ?\n\n"
    "Charfa — Velyx\nhello@velyx.org\n\n"
    "Pour ne plus recevoir de message : répondez « stop »."
)


# ── Logique pure ────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return (text or "").lower()


def _sender_email(msg: dict) -> str:
    """Extrait l'adresse email d'un champ `from` (« Nom <a@b.c> » ou « a@b.c »)."""
    raw = msg.get("from") or ""
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    raw = str(raw)
    if "<" in raw and ">" in raw:
        raw = raw[raw.index("<") + 1 : raw.index(">")]
    return raw.strip().lower()


def is_autoreply_sender(sender: str) -> bool:
    """Expéditeur automatique/technique → jamais de réponse (anti-boucle)."""
    s = _norm(sender)
    if not s or "@" not in s:
        return True
    if s in OWN_ADDRESSES:
        return True
    return any(m in s for m in AUTOREPLY_MARKERS)


def classify_inbound(msg: dict) -> str:
    """Classe un entrant : 'stop' | 'positive' | 'other'. « stop » prime."""
    blob = _norm(msg.get("subject", "")) + "\n" + _norm(msg.get("text", "")) \
        + "\n" + _norm(msg.get("html", ""))
    if any(m in blob for m in STOP_MARKERS):
        return "stop"
    if any(m in blob for m in POSITIVE_MARKERS):
        return "positive"
    return "other"


def _msg_id(msg: dict) -> str:
    return str(msg.get("message_id") or msg.get("id") or "")


def plan_actions(received: list[dict], state: dict) -> list[dict]:
    """Décide, pour chaque entrant non encore traité, l'action à mener.

    Renvoie une liste de {message_id, sender, subject, action} où action ∈
    {'report','stop','human','skip'}. N'effectue aucun envoi (pur)."""
    handled = set(state.get("handled", []))
    reported = set(state.get("report_sent", []))
    opted_out = set(state.get("opt_out", []))
    planned_reports: set[str] = set()  # dédup INTRA-run : 1 rapport max/expéditeur
    actions: list[dict] = []
    for msg in received:
        mid = _msg_id(msg)
        if not mid or mid in handled:
            continue
        sender = _sender_email(msg)
        base = {"message_id": mid, "sender": sender, "subject": msg.get("subject", "")}
        if is_autoreply_sender(sender):
            actions.append({**base, "action": "skip"})
            continue
        kind = classify_inbound(msg)
        if kind == "stop":
            actions.append({**base, "action": "stop"})
        elif kind == "positive":
            # Déjà servi (run précédent), opt-out, ou déjà planifié dans CE run.
            if sender in reported or sender in opted_out or sender in planned_reports:
                actions.append({**base, "action": "skip"})
            else:
                planned_reports.add(sender)
                actions.append({**base, "action": "report"})
        else:
            actions.append({**base, "action": "human"})
    return actions


def build_report_target(action: dict) -> dict:
    """Construit la cible d'envoi (format ResendSender) pour un « oui »."""
    subject = action.get("subject") or ""
    re_subject = subject if subject.lower().startswith("re:") else (
        f"Re: {subject}" if subject else REPORT_SUBJECT_FALLBACK
    )
    mid = action["message_id"]
    headers = {"List-Unsubscribe": "<mailto:hello@velyx.org?subject=unsubscribe>"}
    if mid.startswith("<"):  # thread proprement la réponse
        headers["In-Reply-To"] = mid
        headers["References"] = mid
    key_suffix = "".join(ch for ch in mid if ch.isalnum())[:40] or "noid"
    return {
        "from": FROM,
        "reply_to": REPLY_TO,
        "email": action["sender"],
        "subject": re_subject,
        "text": REPORT_TEXT,
        "headers": headers,
        "idempotency_key": f"velyx-report-{key_suffix}",
    }


def apply_result(state: dict, action: dict, sent_ok: bool) -> None:
    """Met à jour l'état après traitement d'une action (mutation en place)."""
    mid, sender, kind = action["message_id"], action["sender"], action["action"]
    handled = state.setdefault("handled", [])
    if kind == "report" and sent_ok:
        reported = state.setdefault("report_sent", [])
        if sender not in reported:
            reported.append(sender)
    if kind == "stop":
        oo = state.setdefault("opt_out", [])
        if sender not in oo:
            oo.append(sender)
    # 'report' non envoyé (erreur) → NE PAS marquer handled : réessai au prochain run.
    if not (kind == "report" and not sent_ok):
        if mid not in handled:
            handled.append(mid)
    state.setdefault("log", []).append({
        "message_id": mid, "sender": sender, "action": kind, "sent_ok": sent_ok,
    })


# ── État ────────────────────────────────────────────────────────────────

def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"handled": [], "report_sent": [], "opt_out": [], "log": []}
    return json.loads(path.read_text())


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _propagate_optout(sender: str) -> None:
    """Un « stop » met le contact correspondant en status=stop dans les campagnes."""
    for name in CAMPAIGN_FILES:
        p = HERE / name
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        changed = False
        for c in data.get("contacts", []):
            if c.get("email", "").lower() == sender and c.get("status") != "stop":
                c["status"] = "stop"
                changed = True
        if changed:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ── Câblage réel (hors chemin testé) ────────────────────────────────────

def _load_outreach():
    import importlib.util
    spec = importlib.util.spec_from_file_location("outreach", HERE / "outreach.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["outreach"] = mod
    spec.loader.exec_module(mod)
    return mod


def run(state_path: Path = STATE_PATH) -> dict:
    """Traite la boîte de réception. Renvoie un rapport ; envoie réellement."""
    outreach = _load_outreach()
    state = load_state(state_path)
    try:
        received = outreach.list_received(limit=100)
    except outreach.OutreachError as exc:
        return {"ok": False, "error": str(exc), "needs_human": False, "actions": []}

    # L'endpoint liste ne porte pas le corps : enrichir les candidats non traités
    # (text/html) pour classer un « oui » écrit dans le corps, pas dans le sujet.
    handled = set(state.get("handled", []))
    enriched = []
    for msg in received:
        mid = _msg_id(msg)
        rid = msg.get("id")
        if mid and mid not in handled and rid:
            try:
                full = outreach.get_received(rid)
                msg = {**msg, "text": full.get("text", ""), "html": full.get("html", "")}
            except outreach.OutreachError:
                pass  # classification sur le sujet seul, best-effort
        enriched.append(msg)

    actions = plan_actions(enriched, state)
    sender = outreach.ResendSender()
    results, needs_human = [], False
    for act in actions:
        kind = act["action"]
        if kind == "report":
            if not os.environ.get("RESEND_API_KEY"):
                results.append({**act, "status": "error", "error": "RESEND_API_KEY absent"})
                continue  # non marqué handled → réessai
            try:
                res = sender.send(build_report_target(act))
                apply_result(state, act, True)
                needs_human = True  # rapport livré → suivi humain (le RDV)
                results.append({**act, "status": "report_sent", "id": res.get("id")})
            except outreach.OutreachError as exc:
                results.append({**act, "status": "error", "error": str(exc)})
        elif kind == "stop":
            apply_result(state, act, False)
            _propagate_optout(act["sender"])
            results.append({**act, "status": "opted_out"})
        elif kind == "human":
            apply_result(state, act, False)
            needs_human = True
            results.append({**act, "status": "flagged_human"})
        else:  # skip
            apply_result(state, act, False)
            results.append({**act, "status": "skipped"})

    save_state(state, state_path)
    return {"ok": True, "needs_human": needs_human, "actions": results}


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Auto-répondeur terrain — Resend.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Liste et classe les entrants sans rien envoyer.")
    args = parser.parse_args(argv)

    if args.dry_run:
        outreach = _load_outreach()
        received = outreach.list_received(limit=100)
        actions = plan_actions(received, load_state())
        print(json.dumps({"received": len(received), "actions": actions},
                         ensure_ascii=False, indent=2))
        return 0

    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        return 1
    # Code 3 = un humain doit enchaîner (rapport livré → RDV, ou message à lire).
    return 3 if report["needs_human"] else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
