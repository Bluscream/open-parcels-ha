"""One tracker per open parcel: its status as state, its place on the map when known.

The position is the live courier's while a map session runs, else the latest
carrier scan that had coordinates. Without either the tracker has no
coordinates, and Home Assistant leaves it off the map. Positions are kept out
of the recorder, so Home Assistant stores no trail of where a courier has been.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenParcelsConfigEntry
from .const import SIGNAL_LIVE_POSITION
from .coordinator import OpenParcelsCoordinator, ParcelPosition
from .entity import OpenParcelsEntity, async_add_dynamic, device_for_source

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenParcelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a tracker whenever a parcel is open; the coordinator removes finished ones."""
    coordinator = entry.runtime_data.coordinator
    async_add_dynamic(
        coordinator,
        entry,
        async_add_entities,
        coordinator.tracked_parcel_ids,
        lambda parcel_id: [ParcelTracker(coordinator, parcel_id)],
    )


class ParcelTracker(OpenParcelsEntity, TrackerEntity):
    """One open parcel. State: its status key; attributes: the suite's parcel dict."""

    _attr_translation_key = "parcel"
    _attr_source_type = SourceType.GPS
    _unrecorded_attributes = frozenset(
        {
            "raw",
            "history",
            "items",
            "live",
            "lookup",
            "order",
            "latitude",
            "longitude",
            "gps_accuracy",
            "position_at",
            "position_source",
            "stops_away",
        }
    )

    def __init__(self, coordinator: OpenParcelsCoordinator, parcel_id: str) -> None:
        """Place the parcel on its source's device (the hub when it has none)."""
        super().__init__(coordinator, f"parcel_{parcel_id}")
        self._parcel_id = parcel_id
        parcel = coordinator.suite_parcel(parcel_id) or {}
        self._attr_translation_placeholders = {
            "barcode": str(parcel.get("barcode") or parcel_id)
        }
        # The base class types device info as None, but a tracker may belong
        # to a device; the parcel belongs with its source.
        self._attr_device_info = device_for_source(  # type: ignore[assignment]
            coordinator.config_entry, parcel.get("source_id")
        )

    async def async_added_to_hass(self) -> None:
        """Also listen for courier positions, which skip the coordinator."""
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
    def _position(self) -> ParcelPosition | None:
        return self.coordinator.parcel_position(self._parcel_id)

    @property
    def available(self) -> bool:
        """Unavailable once the parcel is gone."""
        return (
            super().available
            and self.coordinator.suite_parcel(self._parcel_id) is not None
        )

    @property
    def location_name(self) -> str | None:
        """The parcel's status key (a manual status wins); it is the entity's state."""
        parcel = self.coordinator.suite_parcel(self._parcel_id)
        return str(parcel["status"]) if parcel else None

    @property
    def latitude(self) -> float | None:
        """Latitude of the courier or the latest scan; None keeps it off the map."""
        position = self._position
        return position.latitude if position else None

    @property
    def longitude(self) -> float | None:
        """Longitude of the courier or the latest scan."""
        position = self._position
        return position.longitude if position else None

    @property
    def location_accuracy(self) -> float:
        """Accuracy in metres (0 when unknown)."""
        position = self._position
        return position.accuracy if position else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The suite's parcel keys, then where the position comes from."""
        parcel = self.coordinator.suite_parcel(self._parcel_id) or {}
        position = self._position
        return {
            **parcel,
            "position_source": position.source if position else None,
            "position_at": position.at if position else None,
            "stops_away": position.stops_away if position else None,
        }
