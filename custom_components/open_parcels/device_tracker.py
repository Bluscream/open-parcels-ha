"""Courier position for parcels with a live session: current position only.

The coordinates are kept out of the recorder, so Home Assistant stores no
trail of where the courier has been.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenParcelsConfigEntry
from .const import SIGNAL_LIVE_POSITION
from .coordinator import CourierPosition, OpenParcelsCoordinator
from .entity import OpenParcelsEntity, async_add_dynamic, device_for_source

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenParcelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a courier tracker whenever a parcel gets a live session."""
    coordinator = entry.runtime_data.coordinator
    async_add_dynamic(
        coordinator,
        entry,
        async_add_entities,
        coordinator.courier_parcel_ids,
        lambda parcel_id: [CourierTracker(coordinator, parcel_id)],
    )


class CourierTracker(OpenParcelsEntity, TrackerEntity):
    """Where the courier carrying a parcel is right now."""

    _attr_translation_key = "courier"
    _attr_source_type = SourceType.GPS
    _unrecorded_attributes = frozenset(
        {"latitude", "longitude", "gps_accuracy", "position_at", "stops_away"}
    )

    def __init__(self, coordinator: OpenParcelsCoordinator, parcel_id: str) -> None:
        """Place the tracker on the parcel's source device."""
        super().__init__(coordinator, f"courier_{parcel_id}")
        self._parcel_id = parcel_id
        parcel = coordinator.suite_parcel(parcel_id) or {}
        self._attr_translation_placeholders = {
            "barcode": str(parcel.get("barcode") or parcel_id)
        }
        # The base class types device info as None, but a tracker may belong
        # to a device; the courier belongs with its parcel's source.
        self._attr_device_info = device_for_source(  # type: ignore[assignment]
            coordinator.config_entry, parcel.get("source_id")
        )

    async def async_added_to_hass(self) -> None:
        """Also listen for position messages, which skip the coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_LIVE_POSITION.format(self.coordinator.config_entry.entry_id),
                self._handle_position,
            )
        )

    @callback
    def _handle_position(self, parcel_id: str) -> None:
        if parcel_id == self._parcel_id:
            self.async_write_ha_state()

    @property
    def _position(self) -> CourierPosition | None:
        return self.coordinator.positions.get(self._parcel_id)

    @property
    def available(self) -> bool:
        """Available while the courier's position is known."""
        return super().available and self._position is not None

    @property
    def latitude(self) -> float | None:
        """Courier latitude."""
        position = self._position
        return position.latitude if position else None

    @property
    def longitude(self) -> float | None:
        """Courier longitude."""
        position = self._position
        return position.longitude if position else None

    @property
    def location_accuracy(self) -> float:
        """Accuracy in metres (0 when unknown)."""
        position = self._position
        return (position.accuracy or 0) if position else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Stops away and the time of the fix."""
        position = self._position
        parcel = self.coordinator.suite_parcel(self._parcel_id) or {}
        live = parcel.get("live") or {}
        return {
            "barcode": parcel.get("barcode"),
            "live_state": live.get("state"),
            "stops_away": position.stops_away if position else live.get("stops_away"),
            "position_at": position.position_at if position else None,
        }
