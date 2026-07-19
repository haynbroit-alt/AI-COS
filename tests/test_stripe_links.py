"""Tests du connecteur Payment Links — cas normal / erreur / limite (règle 3)."""

import urllib.parse

import pytest

from ai_cos.product.connectors.stripe_links import PaymentLinkConnector
from ai_cos.product.sources import DataSourceError


def make_transport(response, captured):
    def transport(url, headers, data):
        captured["url"] = url
        captured["headers"] = headers
        captured["fields"] = dict(urllib.parse.parse_qsl(data.decode()))
        return response

    return transport


def test_creates_link_and_returns_url():
    captured = {}
    connector = PaymentLinkConnector(
        api_key="rk_test_x",
        transport=make_transport({"url": "https://buy.stripe.com/abc123"}, captured),
    )
    url = connector.create_payment_link(
        "price_123", metadata={"source": "ai-cos", "action": "offre premium"}
    )
    assert url == "https://buy.stripe.com/abc123"
    assert captured["url"].endswith("/payment_links")
    assert captured["headers"]["Authorization"] == "Bearer rk_test_x"
    assert captured["fields"] == {
        "line_items[0][price]": "price_123",
        "line_items[0][quantity]": "1",
        "metadata[source]": "ai-cos",
        "metadata[action]": "offre premium",
    }


def test_invalid_inputs_rejected():
    connector = PaymentLinkConnector(api_key="rk_test_x", transport=lambda *a: {})
    with pytest.raises(DataSourceError, match="price_"):
        connector.create_payment_link("prod_123")  # produit ≠ prix
    with pytest.raises(DataSourceError, match="Quantité"):
        connector.create_payment_link("price_123", quantity=0)


def test_missing_key_and_bad_response(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    with pytest.raises(DataSourceError, match="STRIPE_API_KEY"):
        PaymentLinkConnector().create_payment_link("price_123")
    # Cas limite : l'API répond sans URL → erreur claire, pas de lien fantôme
    connector = PaymentLinkConnector(api_key="rk_test_x", transport=lambda *a: {"id": "plink_1"})
    with pytest.raises(DataSourceError, match="sans URL"):
        connector.create_payment_link("price_123")
