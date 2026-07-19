"""Tests des sources réelles — cas normal / erreur / limite (règle 3)."""

import json

import pytest

from ai_cos.product.sources import (
    DataSourceError,
    JsonFileSource,
    StripeSource,
    measure_since,
)


# --- JsonFileSource ---------------------------------------------------------


def test_json_source_reads_real_metrics(tmp_path):
    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps({"clients": 3, "revenus": 1250.5, "qualite": 6}))
    values = JsonFileSource(journal).observe()
    assert values == {"clients": 3.0, "revenus": 1250.5, "qualite": 6.0}


def test_json_source_missing_file(tmp_path):
    with pytest.raises(DataSourceError, match="introuvable"):
        JsonFileSource(tmp_path / "absent.json").observe()


def test_json_source_invalid_content(tmp_path):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{pas du json")
    with pytest.raises(DataSourceError, match="illisible"):
        JsonFileSource(corrupt).observe()

    non_numeric = tmp_path / "bad.json"
    non_numeric.write_text(json.dumps({"clients": "trois"}))
    with pytest.raises(DataSourceError, match="non numérique"):
        JsonFileSource(non_numeric).observe()

    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    with pytest.raises(DataSourceError, match="vide"):
        JsonFileSource(empty).observe()


# --- StripeSource -----------------------------------------------------------


def fake_transport(pages):
    """Transport simulé : url → réponse, avec pagination par starting_after."""

    def transport(url, headers):
        assert headers["Authorization"].startswith("Bearer ")
        for prefix, responses in pages.items():
            if prefix in url:
                if "starting_after" in url:
                    return responses[1]
                return responses[0]
        raise AssertionError(f"URL inattendue : {url}")

    return transport


def test_stripe_source_counts_customers_and_sums_charges():
    pages = {
        "/customers": [{"data": [{"id": "c1"}, {"id": "c2"}], "has_more": False}],
        "/charges": [
            {
                "data": [
                    {"id": "ch1", "amount": 5000, "status": "succeeded"},
                    {"id": "ch2", "amount": 9900, "status": "succeeded", "refunded": True},
                    {"id": "ch3", "amount": 1000, "status": "failed"},
                ],
                "has_more": False,
            }
        ],
    }
    source = StripeSource(api_key="sk_test_x", transport=fake_transport(pages))
    assert source.observe() == {"clients": 2.0, "revenus": 50.0}  # centimes → euros


def test_stripe_source_paginates():
    pages = {
        "/customers": [
            {"data": [{"id": "c1"}], "has_more": True},
            {"data": [{"id": "c2"}], "has_more": False},
        ],
        "/charges": [{"data": [], "has_more": False}],
    }
    source = StripeSource(api_key="sk_test_x", transport=fake_transport(pages))
    assert source.observe()["clients"] == 2.0


def test_stripe_source_requires_key(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    with pytest.raises(DataSourceError, match="STRIPE_API_KEY"):
        StripeSource().observe()


# --- Mesure différée --------------------------------------------------------


def test_measure_since_computes_real_deltas():
    saved = {"clients": 2.0, "revenus": 800.0, "qualite": 5.0}
    observed = {"clients": 3.0, "revenus": 950.0, "qualite": 5.0, "hors_suivi": 42}
    measure = measure_since(saved, observed)
    assert measure.deltas == {"clients": 1.0, "revenus": 150.0, "qualite": 0.0}
    # dimension absente du relevé → non mesurée, pas inventée
    partial = measure_since(saved, {"clients": 4.0})
    assert partial.deltas == {"clients": 2.0}
