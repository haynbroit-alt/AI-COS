"""KPIs de campagne — funnel outreach, fonctions pures, stdlib.

Alimenté par terrain/campaign.json (registre par contact). Chaque contact porte
des booléens d'étape (sent/delivered/bounced/replied/meeting/signed) et un
revenu. Les taux sont calculés sur la base de l'étape précédente, avec garde
contre la division par zéro (retour None quand la base est nulle → « n/a »).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CAMPAIGN = Path(__file__).with_name("campaign.json")


def _rate(num: int, den: int) -> float | None:
    """Taux num/den, ou None si base nulle (évite le faux 0 %)."""
    return (num / den) if den else None


@dataclass
class Funnel:
    sent: int
    delivered: int
    bounced: int
    replies: int
    meetings: int
    signed: int
    revenue_eur: float

    @property
    def delivery_rate(self) -> float | None:
        return _rate(self.delivered, self.sent)

    @property
    def reply_rate(self) -> float | None:
        return _rate(self.replies, self.delivered)

    @property
    def meeting_rate(self) -> float | None:
        return _rate(self.meetings, self.replies)

    @property
    def sign_rate(self) -> float | None:
        return _rate(self.signed, self.meetings)

    def as_dict(self) -> dict:
        def pct(x: float | None) -> str:
            return "n/a" if x is None else f"{x * 100:.0f}%"

        return {
            "sent": self.sent,
            "delivered": self.delivered,
            "bounced": self.bounced,
            "replies": self.replies,
            "meetings": self.meetings,
            "signed": self.signed,
            "revenue_eur": self.revenue_eur,
            "delivery_rate": pct(self.delivery_rate),
            "reply_rate": pct(self.reply_rate),
            "meeting_rate": pct(self.meeting_rate),
            "sign_rate": pct(self.sign_rate),
        }


def compute_funnel(contacts: list[dict]) -> Funnel:
    """Agrège les compteurs de funnel depuis la liste de contacts."""
    def count(flag: str) -> int:
        return sum(1 for c in contacts if c.get(flag))

    return Funnel(
        sent=count("sent"),
        delivered=count("delivered"),
        bounced=count("bounced"),
        replies=count("replied"),
        meetings=count("meeting"),
        signed=count("signed"),
        revenue_eur=float(sum(c.get("revenue_eur", 0) or 0 for c in contacts)),
    )


def load_campaign(path: Path = DEFAULT_CAMPAIGN) -> dict:
    if not path.exists():
        return {"campaign": None, "contacts": []}
    return json.loads(path.read_text())


def report(path: Path = DEFAULT_CAMPAIGN) -> dict:
    data = load_campaign(path)
    funnel = compute_funnel(data.get("contacts", []))
    return {"campaign": data.get("campaign"), "funnel": funnel.as_dict()}


if __name__ == "__main__":
    import sys

    print(json.dumps(report(), ensure_ascii=False, indent=2))
    sys.exit(0)
