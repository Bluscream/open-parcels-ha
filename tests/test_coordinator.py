"""Event-stream messages: state updates and Home Assistant bus events."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_parcels.api import OpenParcelsConnectionError
from custom_components.open_parcels.const import DOMAIN
from custom_components.open_parcels.coordinator import (
    OpenParcelsCoordinator,
    _position_from_live,
)
from custom_components.open_parcels.device import find_device

from . import payloads
from .conftest import FakeStream, events


def _parcel(index: int, **changes) -> dict:
    parcel = payloads.parcels()[index]
    parcel.update(changes)
    return parcel


async def test_status_change_fires_event_and_updates(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """parcel.status_changed -> open_parcels_parcel_status_changed with device ids."""
    fired = events(hass, f"{DOMAIN}_parcel_status_changed")
    parcel = _parcel(1, status="returning")
    stream.push(
        "parcel.status_changed",
        json.dumps(
            {
                "parcel": parcel,
                "old_status": "at_pickup_point",
                "new_status": "returning",
            }
        ),
        "41",
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.gls_99999_parcel_test0000000002").state == "returning"
    )
    assert len(fired) == 1
    data = fired[0].data
    assert data["barcode"] == "TEST0000000002"
    assert data["old_status"] == "at_pickup_point"
    assert data["new_status"] == "returning"
    assert "raw" not in data
    gls = find_device(
        hass,
        loaded.entry_id,
        (DOMAIN, f"{loaded.entry_id}_source_{payloads.SOURCE_GLS}"),
    )
    hub = find_device(hass, loaded.entry_id, (DOMAIN, loaded.entry_id))
    assert data["device_id"] == gls.id
    assert data["hub_device_id"] == hub.id
    assert loaded.runtime_data.coordinator.last_event_id == "41"


async def test_new_parcel_adds_entity(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """A registered parcel gets its sensor without a resync."""
    fired = events(hass, f"{DOMAIN}_parcel_registered")
    parcel = _parcel(
        1,
        id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        barcode="TEST0000000005",
        status="registered",
        pickup=False,
    )
    stream.push("parcel.registered", json.dumps({"parcel": parcel}), "42")
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.gls_99999_parcel_test0000000005").state == "registered"
    )
    assert hass.states.get("sensor.open_parcels_incoming_parcels").state == "3"
    assert len(fired) == 1


async def test_removed_parcel_drops_entity(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """parcel.removed takes the parcel and its courier away."""
    fired = events(hass, f"{DOMAIN}_parcel_removed")
    stream.push("parcel.removed", json.dumps({"parcel": _parcel(0)}), "43")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.dhl_germany_abc123_parcel_test0000000001") is None
    assert (
        hass.states.get("device_tracker.dhl_germany_abc123_courier_test0000000001")
        is None
    )
    assert len(fired) == 1


async def test_delivered_and_delivery_time_and_outgoing_events(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """Every server event maps to its suite-style bus event."""
    names = [
        "parcel_delivered",
        "parcel_delivery_time_changed",
        "outgoing_parcel_registered",
        "outgoing_parcel_delivered",
        "parcel_live_updated",
    ]
    fired = {name: events(hass, f"{DOMAIN}_{name}") for name in names}
    delivered = _parcel(
        0,
        status="delivered",
        delivered=True,
        delivered_at="2999-01-01T00:00:00Z",
        live=None,
    )
    stream.push("parcel.delivered", json.dumps({"parcel": delivered}), "50")
    stream.push(
        "parcel.delivery_time_changed",
        json.dumps(
            {
                "parcel": _parcel(1, planned_from="2030-01-05T10:00:00Z"),
                "old_planned_from": None,
                "new_planned_from": "2030-01-05T10:00:00Z",
            }
        ),
        "51",
    )
    stream.push("parcel.outgoing_registered", json.dumps({"parcel": _parcel(3)}), "52")
    stream.push(
        "parcel.outgoing_delivered",
        json.dumps({"parcel": _parcel(3, status="delivered", delivered=True)}),
        "53",
    )
    stream.push(
        "parcel.live_updated",
        json.dumps({"parcel": _parcel(1), "old_live_state": None}),
        "54",
    )
    await hass.async_block_till_done()
    for name in names:
        assert len(fired[name]) == 1, name
    assert fired["parcel_delivery_time_changed"][0].data["new_planned_from"] == (
        "2030-01-05T10:00:00Z"
    )
    assert hass.states.get("sensor.open_parcels_delivered_parcels").state == "2"
    # Live session ended with the delivery: the courier tracker goes away.
    assert (
        hass.states.get("device_tracker.dhl_germany_abc123_courier_test0000000001")
        is None
    )


async def test_source_state_change(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """source.state_changed updates the source and fires an event."""
    fired = events(hass, f"{DOMAIN}_source_state_changed")
    stream.push(
        "source.state_changed",
        json.dumps(
            {
                "source": {"id": payloads.SOURCE_DHL, "plugin": "dhl", "label": "x"},
                "old_state": "ok",
                "new_state": "error",
                "detail": "Carrier unreachable",
            }
        ),
        "60",
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.dhl_germany_abc123_source_state").state == "error"
    assert hass.states.get("binary_sensor.dhl_germany_abc123_problem").state == "on"
    assert fired[0].data["new_state"] == "error"
    assert fired[0].data["device_id"] is not None


async def test_unknown_source_or_parcel_source_triggers_resync(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream, client: MagicMock
) -> None:
    """Events naming a source this entry has not seen cause a resync."""
    before = client.async_get_sources.await_count
    stream.push(
        "source.state_changed",
        json.dumps({"source": {"id": "new"}, "old_state": "ok", "new_state": "error"}),
    )
    stream.push(
        "parcel.registered",
        json.dumps(
            {
                "parcel": _parcel(
                    1,
                    id="ffffffff-ffff-4fff-8fff-ffffffffffff",
                    sources=[
                        {
                            "source_id": "unknown-source",
                            "plugin": "gls",
                            "role": "primary",
                            "last_seen_at": "2030-01-01T00:00:00Z",
                        }
                    ],
                )
            }
        ),
    )
    await hass.async_block_till_done()
    assert client.async_get_sources.await_count > before


async def test_ignored_messages(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """Malformed, non-object, unknown and incomplete messages change nothing."""
    coordinator = loaded.runtime_data.coordinator
    stream.push("parcel.registered", "{not json")
    stream.push("parcel.registered", "[1, 2]")
    stream.push("vocab.unknown", json.dumps({"key": "x"}), "70")
    stream.push("parcel.registered", json.dumps({"parcel": {"no": "id"}}))
    stream.push("parcel.live_position", json.dumps({"parcel_id": 5}))
    await hass.async_block_till_done()
    assert coordinator.last_event_id == "70"
    assert hass.states.get("sensor.open_parcels_incoming_parcels").state == "2"


async def test_history_kept_when_event_lacks_it(
    hass: HomeAssistant, loaded: MockConfigEntry, stream: FakeStream
) -> None:
    """A parcel event without history keeps what the resync loaded."""
    coordinator = loaded.runtime_data.coordinator
    parcel = _parcel(0)
    del parcel["history"]
    stream.push("parcel.status_changed", json.dumps({"parcel": parcel}), "80")
    await hass.async_block_till_done()
    assert len(coordinator.data.parcels[payloads.PARCEL_A]["history"]) == 2


async def test_resync_failure_keeps_entities(
    hass: HomeAssistant, loaded: MockConfigEntry, client: MagicMock
) -> None:
    """A failed resync marks entities unavailable but keeps them."""
    client.async_get_parcels.side_effect = OpenParcelsConnectionError("down")
    coordinator = loaded.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.open_parcels_incoming_parcels").state == "unavailable"
    )
    # The event stream sensor reports the stream, not the resync.
    assert hass.states.get("binary_sensor.open_parcels_event_stream").state == "on"


async def test_calendar_failure_is_not_fatal(
    hass: HomeAssistant, loaded: MockConfigEntry, client: MagicMock
) -> None:
    """A failing calendar endpoint leaves the cached entries alone."""
    coordinator = loaded.runtime_data.coordinator
    cached = list(coordinator.calendar_entries)
    client.async_get_calendar.side_effect = OpenParcelsConnectionError("down")
    await coordinator.async_refresh_calendar()
    assert coordinator.calendar_entries == cached
    assert coordinator.last_update_success


async def test_views_before_first_refresh(
    hass: HomeAssistant, entry: MockConfigEntry, client: MagicMock
) -> None:
    """Before any data arrives, every view is empty instead of failing."""
    entry.add_to_hass(hass)
    coordinator = OpenParcelsCoordinator(hass, entry, client)
    assert coordinator.suite_parcel(payloads.PARCEL_A) is None
    assert coordinator.visible_parcel_ids() == set()
    assert coordinator.courier_parcel_ids() == set()
    coordinator.async_sync_registry()


def test_position_needs_numeric_coordinates() -> None:
    """A live block without numbers gives no position."""
    assert _position_from_live({"state": "en_route", "latitude": "x"}) is None
    assert (
        _position_from_live({"state": "next_stop", "latitude": 1, "longitude": 2})
        is None
    )
