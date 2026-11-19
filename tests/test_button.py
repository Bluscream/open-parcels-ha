"""Buttons."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_parcels.api import OpenParcelsConnectionError

from . import payloads


async def test_source_sync_button(
    hass: HomeAssistant, loaded: MockConfigEntry, client: MagicMock
) -> None:
    """The source button runs the source; the hub button resyncs."""
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.dhl_germany_abc123_refresh"},
        blocking=True,
    )
    client.async_sync_source.assert_awaited_once_with(payloads.SOURCE_DHL)

    before = client.async_get_parcels.await_count
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.open_parcels_refresh"}, blocking=True
    )
    await hass.async_block_till_done()
    assert client.async_get_parcels.await_count > before

    client.async_sync_source.side_effect = OpenParcelsConnectionError("down")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.dhl_germany_abc123_refresh"},
            blocking=True,
        )
