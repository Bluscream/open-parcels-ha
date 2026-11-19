"""The schema-library shim."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import voluptuous

from custom_components.open_parcels import schema


def test_falls_back_to_voluptuous() -> None:
    """Without probatio, voluptuous is used."""
    try:
        with patch.dict(sys.modules, {"probatio": None}):
            reloaded = importlib.reload(schema)
            assert reloaded.vol is voluptuous
    finally:
        importlib.reload(schema)
    assert schema.vol is not None
