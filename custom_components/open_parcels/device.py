"""Devices: one hub for the server, one device per Open Parcels source."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN

HUB_NAME = "Open Parcels"


def hub_identifier(entry_id: str) -> tuple[str, str]:
    """Device identifier of the hub."""
    return (DOMAIN, entry_id)


def source_identifier(entry_id: str, source_id: str) -> tuple[str, str]:
    """Device identifier of a source."""
    return (DOMAIN, f"{entry_id}_source_{source_id}")


def find_device(
    hass: HomeAssistant, entry_id: str, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """This entry's device with an identifier.

    Searches the entry's own devices, which works on every supported Home
    Assistant release (the identifier lookup changed in newer ones).
    """
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry_id):
        if identifier in device.identifiers:
            return device
    return None


def server_url(entry: ConfigEntry) -> str:
    """The server URL stored in the entry."""
    return str(entry.data.get("url", "")).rstrip("/")


def hub_device_info(entry: ConfigEntry) -> DeviceInfo:
    """DeviceInfo of the hub every summary entity belongs to."""
    return DeviceInfo(
        identifiers={hub_identifier(entry.entry_id)},
        name=HUB_NAME,
        manufacturer=HUB_NAME,
        model="Server",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=server_url(entry) or None,
    )


def source_device_name(source: Mapping[str, Any], carriers: Mapping[str, str]) -> str:
    """Name a source's device "<carrier> <label>", unless the label already says it.

    With the source labelled like the old integration's entry title (for
    example "Germany (7c6c9a)"), the device name, and therefore every entity
    id derived from it, matches what the per-carrier integration produced.
    """
    plugin = str(source.get("plugin") or "")
    carrier = carriers.get(plugin, plugin)
    label = str(source.get("label") or "").strip()
    if not label:
        return carrier
    if not carrier or label.casefold().startswith(carrier.casefold()):
        return label
    return f"{carrier} {label}"


def source_device_info(
    entry: ConfigEntry, source: Mapping[str, Any], carriers: Mapping[str, str]
) -> DeviceInfo:
    """DeviceInfo of one source.

    The link to the hub is set by device id when the device is registered
    (``via_device_id``), which every supported Home Assistant release accepts.
    """
    plugin = str(source.get("plugin") or "")
    return DeviceInfo(
        identifiers={source_identifier(entry.entry_id, str(source["id"]))},
        name=source_device_name(source, carriers),
        manufacturer=carriers.get(plugin, plugin) or None,
        model=str(source.get("kind") or "") or None,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=server_url(entry) or None,
    )
