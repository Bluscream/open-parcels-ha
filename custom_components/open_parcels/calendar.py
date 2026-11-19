"""Calendar of expected and delivered parcels, read from the server's calendar."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import OpenParcelsConfigEntry
from .api import OpenParcelsError
from .const import DOMAIN
from .coordinator import OpenParcelsCoordinator
from .entity import OpenParcelsEntity, device_for_source
from .parcels import parse_iso

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenParcelsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the deliveries calendar on the hub."""
    async_add_entities([DeliveriesCalendar(entry.runtime_data.coordinator)])


def to_calendar_event(entry: Mapping[str, Any]) -> CalendarEvent | None:
    """Turn one server calendar entry into a CalendarEvent."""
    start = parse_iso(entry.get("start"))
    end = parse_iso(entry.get("end"))
    if start is None or end is None:
        return None
    title = str(entry.get("title") or entry.get("barcode") or "Parcel")
    summary = f"Delivered: {title}" if entry.get("kind") == "delivered" else title
    lines = [
        " ".join(str(entry[k]) for k in ("carrier", "barcode") if entry.get(k)),
        f"Status: {entry['status']}" if entry.get("status") else None,
        entry.get("url"),
    ]
    description = "\n".join(line for line in lines if line) or None
    event_start: date | datetime = start
    event_end: date | datetime = end
    if entry.get("all_day"):
        # The server's whole-day windows end at midnight (exclusive) or at the
        # last second of the day (inclusive); both become an exclusive end date.
        event_start = dt_util.as_local(start).date()
        event_end = (dt_util.as_local(end) - timedelta(seconds=1)).date() + timedelta(
            days=1
        )
        if event_end <= event_start:
            event_end = event_start + timedelta(days=1)
    elif end <= start:
        event_end = start + timedelta(hours=1)
    return CalendarEvent(
        start=event_start,
        end=event_end,
        summary=summary,
        description=description,
        location=entry.get("pickup_point"),
        uid=entry.get("uid"),
    )


def _events(entries: list[dict[str, Any]]) -> list[CalendarEvent]:
    return [event for entry in entries if (event := to_calendar_event(entry))]


class DeliveriesCalendar(OpenParcelsEntity, CalendarEntity):
    """The same entries as the server's calendar and ICS feed."""

    _attr_translation_key = "deliveries"

    def __init__(self, coordinator: OpenParcelsCoordinator) -> None:
        """Belongs to the hub."""
        super().__init__(coordinator, "deliveries")
        self._attr_device_info = device_for_source(coordinator.config_entry, None)

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next expected delivery (delivered markers are skipped)."""
        now = dt_util.now()
        expected = [
            entry
            for entry in self.coordinator.calendar_entries
            if entry.get("kind") != "delivered"
        ]
        upcoming = [
            event for event in _events(expected) if event.end_datetime_local > now
        ]
        return min(upcoming, key=lambda e: e.start_datetime_local, default=None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Ask the server for the range."""
        try:
            entries = await self.coordinator.client.async_get_calendar(
                start_date, end_date
            )
        except OpenParcelsError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="calendar_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return _events(entries)
