"""Buttons: resync everything on the hub, run one source on its device."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenParcelsConfigEntry
from .api import OpenParcelsError
from .const import DOMAIN
from .coordinator import OpenParcelsCoordinator
from .entity import OpenParcelsEntity, async_add_dynamic, device_for_source

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenParcelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hub's refresh button and one sync button per source."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([RefreshButton(coordinator)])
    async_add_dynamic(
        coordinator,
        entry,
        async_add_entities,
        lambda: coordinator.data.sources if coordinator.data else (),
        lambda source_id: [SourceSyncButton(coordinator, source_id)],
    )


class RefreshButton(OpenParcelsEntity, ButtonEntity):
    """Re-read everything from the server."""

    _attr_translation_key = "refresh"

    def __init__(self, coordinator: OpenParcelsCoordinator) -> None:
        """Belongs to the hub."""
        super().__init__(coordinator, "refresh")
        self._attr_device_info = device_for_source(coordinator.config_entry, None)

    async def async_press(self) -> None:
        """Resync now."""
        await self.coordinator.async_request_refresh()


class SourceSyncButton(OpenParcelsEntity, ButtonEntity):
    """Ask the server to run this source now."""

    _attr_translation_key = "refresh"

    def __init__(self, coordinator: OpenParcelsCoordinator, source_id: str) -> None:
        """Belongs to the source's device."""
        super().__init__(coordinator, f"source_{source_id}_sync")
        self._source_id = source_id
        self._attr_device_info = device_for_source(coordinator.config_entry, source_id)

    async def async_press(self) -> None:
        """Run the source; its results arrive through the event stream."""
        try:
            await self.coordinator.client.async_sync_source(self._source_id)
        except OpenParcelsError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="sync_failed",
                translation_placeholders={"error": str(err)},
            ) from err
