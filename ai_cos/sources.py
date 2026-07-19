"""Alias de compatibilité — module déplacé vers ai_cos.product.sources."""
from ai_cos.product.sources import (  # noqa: F401
    DataSource, DataSourceError, JsonFileSource, RealityMeasure, StripeSource,
    measure_since,
)
