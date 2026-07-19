"""Connecteur Stripe Payment Links — premier connecteur d'ACTION réel.

Rend une offre exécutable en 1 clic : crée un lien de paiement partageable
sur un prix Stripe existant. Toute vente devient visible au relevé du
lendemain (charges > 0) — la boucle mesure, le lien vend.

Clé dans STRIPE_API_KEY. La clé doit avoir la permission d'écriture
« Payment Links » (une clé restreinte lecture seule ne suffit pas).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from ai_cos.product.sources import DataSourceError

# transport(url, headers, data) -> réponse JSON décodée ; injectable en test.
PostTransport = Callable[[str, dict[str, str], bytes], dict]


def _http_post_json(url: str, headers: dict[str, str], data: bytes) -> dict:
    request = urllib.request.Request(url, headers=headers, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise DataSourceError(f"API Stripe {exc.code} : {detail}") from exc
    except Exception as exc:
        raise DataSourceError(f"Appel API échoué ({url}) : {exc}") from exc


@dataclass
class PaymentLinkConnector:
    """Crée des Payment Links Stripe (form-encoding natif de l'API)."""

    api_key: str | None = None
    transport: PostTransport = _http_post_json

    BASE = "https://api.stripe.com/v1"

    def _key(self) -> str:
        key = self.api_key or os.environ.get("STRIPE_API_KEY", "")
        if not key:
            raise DataSourceError(
                "STRIPE_API_KEY absent — impossible de créer un lien de paiement."
            )
        return key

    def create_payment_link(
        self,
        price_id: str,
        quantity: int = 1,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Retourne l'URL partageable du lien de paiement créé."""
        if not price_id.startswith("price_"):
            raise DataSourceError(
                f"Identifiant de prix invalide : « {price_id} » (attendu : price_…)"
            )
        if quantity < 1:
            raise DataSourceError(f"Quantité invalide : {quantity}")
        fields: dict[str, str] = {
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": str(quantity),
        }
        for key, value in (metadata or {}).items():
            fields[f"metadata[{key}]"] = value
        payload = urllib.parse.urlencode(fields).encode()
        response = self.transport(
            f"{self.BASE}/payment_links",
            {
                "Authorization": f"Bearer {self._key()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            payload,
        )
        url = response.get("url")
        if not url:
            raise DataSourceError(f"Réponse Stripe sans URL : {response}")
        return url
