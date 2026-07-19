"""Sources de données réelles — Réalité > Hypothèse.

Une source observe le monde et retourne les métriques réelles par dimension.
Contrairement au simulateur, elle ne prédit rien : elle relève.

- JsonFileSource : journal JSON alimenté par l'utilisateur ou par n'importe
  quel export (CRM, analytics, cron). Zéro credential, utilisable aujourd'hui.
- StripeSource : clients et revenus lus directement depuis l'API Stripe
  (clé dans STRIPE_API_KEY).

En mode réel, la mesure est différée : l'action du jour J est mesurée au
relevé du jour J+1 (deltas = observé − état sauvegardé).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


class DataSourceError(RuntimeError):
    """Relevé impossible : fichier manquant, API en erreur, données invalides."""


class DataSource(Protocol):
    name: str

    def observe(self) -> dict[str, float]:
        """Retourne les valeurs réelles courantes par dimension."""
        ...


@dataclass
class JsonFileSource:
    """Journal JSON : {"clients": 3, "revenus": 1250.0, "qualite": 6}.

    Le fichier est la réalité — mis à jour à la main ou par un export
    automatique. Les valeurs non numériques sont refusées.
    """

    path: str | Path
    name: str = "journal"

    def observe(self) -> dict[str, float]:
        path = Path(self.path)
        if not path.exists():
            raise DataSourceError(
                f"Journal introuvable : {path}. Créez-le avec vos métriques "
                'réelles, ex. {"clients": 3, "revenus": 1250, "qualite": 6}.'
            )
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise DataSourceError(f"Journal illisible ({path}) : {exc}") from exc
        if not isinstance(raw, dict) or not raw:
            raise DataSourceError(f"Journal vide ou mal formé : {path}")
        values: dict[str, float] = {}
        for key, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DataSourceError(
                    f"Valeur non numérique pour « {key} » dans {path} : {value!r}"
                )
            values[key] = float(value)
        return values


# transport(url, headers) -> corps JSON décodé ; injectable pour les tests.
Transport = Callable[[str, dict[str, str]], dict]


def _http_get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except Exception as exc:  # urllib lève des types variés (HTTP, URL, socket)
        raise DataSourceError(f"Appel API échoué ({url}) : {exc}") from exc


@dataclass
class StripeSource:
    """Relevé Stripe : clients = nombre de customers, revenus = somme des
    charges réussies (montants convertis depuis les centimes).

    La clé API vient de STRIPE_API_KEY (jamais en dur, jamais commitée).
    """

    api_key: str | None = None
    transport: Transport = _http_get_json
    name: str = "stripe"
    page_limit: int = 100

    BASE = "https://api.stripe.com/v1"

    def _key(self) -> str:
        key = self.api_key or os.environ.get("STRIPE_API_KEY", "")
        if not key:
            raise DataSourceError(
                "STRIPE_API_KEY absent — exportez la clé avant d'utiliser StripeSource."
            )
        return key

    def _get(self, endpoint: str, **params) -> dict:
        query = urllib.parse.urlencode({"limit": self.page_limit, **params})
        return self.transport(
            f"{self.BASE}/{endpoint}?{query}",
            {"Authorization": f"Bearer {self._key()}"},
        )

    def _iterate(self, endpoint: str, **params) -> list[dict]:
        items: list[dict] = []
        starting_after: str | None = None
        while True:
            page_params = dict(params)
            if starting_after:
                page_params["starting_after"] = starting_after
            page = self._get(endpoint, **page_params)
            data = page.get("data", [])
            items.extend(data)
            if not page.get("has_more") or not data:
                return items
            starting_after = data[-1]["id"]

    def observe(self) -> dict[str, float]:
        customers = self._iterate("customers")
        charges = self._iterate("charges")
        revenus = sum(
            c.get("amount", 0) / 100.0
            for c in charges
            if c.get("status") == "succeeded" and not c.get("refunded")
        )
        return {"clients": float(len(customers)), "revenus": revenus}


@dataclass
class RealityMeasure:
    """Mesure différée : deltas réels entre l'état sauvegardé hier et le
    relevé de ce matin, attribués à l'action décidée hier."""

    deltas: dict[str, float]

    def __call__(self, state, action, lever) -> dict[str, float]:
        return dict(self.deltas)


def measure_since(saved_values: dict[str, float], observed: dict[str, float]) -> RealityMeasure:
    """Deltas = observé − sauvegardé, sur les dimensions suivies uniquement."""
    deltas = {
        dim: observed[dim] - saved_values[dim]
        for dim in saved_values
        if dim in observed
    }
    return RealityMeasure(deltas=deltas)
