"""Courier tracker."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import payloads
from .conftest import FakeStream


async def test_courier_tracker(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """Current position from the resync, then from live messages; never recorded."""
    entity_id = "device_tracker.dhl_germany_abc123_courier_test0000000001"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["latitude"] == 50.0
    assert state.attributes["stops_away"] == 3
    assert state.attributes["gps_accuracy"] == 15

    stream.push(
        "parcel.live_position",
        json.dumps(
            {
                "parcel_id": payloads.PARCEL_A,
                "latitude": 50.5,
                "longitude": 8.5,
                "accuracy": None,
                "positionAt": "2030-01-02T09:31:00.000Z",
                "stops_away": 2,
            }
        ),
    )
    stream.push(
        "parcel.live_position",
        json.dumps({"parcel_id": payloads.PARCEL_B, "latitude": 1, "longitude": 2}),
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["latitude"] == 50.5
    assert state.attributes["position_at"] == "2030-01-02T09:31:00.000Z"
    assert state.attributes["stops_away"] == 2

    entity = hass.data["device_tracker"].get_entity(entity_id)
    assert {"latitude", "longitude", "gps_accuracy"} <= set(
        entity._Entity__combined_unrecorded_attributes
    )

    # A position message without coordinates clears the position.
    stream.push(
        "parcel.live_position",
        json.dumps({"parcel_id": payloads.PARCEL_A, "latitude": None}),
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unavailable"
