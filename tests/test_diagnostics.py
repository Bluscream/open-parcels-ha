"""Diagnostics."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_parcels.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import TOKEN


async def test_diagnostics_redact(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """Tokens, URLs, codes, names and addresses never appear."""
    result = await async_get_config_entry_diagnostics(hass, loaded)
    text = json.dumps(result)
    for secret in (
        TOKEN,
        "TEST0000000001",
        "Jane Example",
        "Example Shop",
        "Example Kiosk",
        "Germany (abc123)",
        "open-parcels.example.test",
        "Sign in again",
    ):
        assert secret not in text, secret
    assert result["parcel_count"] == 4
    assert result["stream"]["connected"] is True
    assert result["sources"][0]["state"] == "ok"
