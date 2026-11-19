"""Constants for the Open Parcels integration."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "open_parcels"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


class ParcelStatus(StrEnum):
    """Carrier-agnostic parcel status, identical to the server's and the suite's list."""

    REGISTERED = "registered"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    AT_PICKUP_POINT = "at_pickup_point"
    DELIVERED = "delivered"
    RETURNING = "returning"
    PROBLEM = "problem"
    UNKNOWN = "unknown"


class SourceState(StrEnum):
    """State of an Open Parcels source."""

    OK = "ok"
    NEEDS_SIGN_IN = "needs_sign_in"
    ERROR = "error"
    DISABLED = "disabled"


CONF_API_TOKEN = "api_token"

# Options. The delivered filter is the suite's, unchanged.
CONF_RESYNC_MINUTES = "resync_minutes"
DEFAULT_RESYNC_MINUTES = 30
MIN_RESYNC_MINUTES = 5
MAX_RESYNC_MINUTES = 1440
CONF_INCLUDE_HISTORY = "include_history"
DEFAULT_INCLUDE_HISTORY = False
CONF_DELIVERED_FILTER_TYPE = "delivered_filter_type"
CONF_DELIVERED_FILTER_AMOUNT = "delivered_filter_amount"
DEFAULT_DELIVERED_FILTER_TYPE = "days"
DEFAULT_DELIVERED_FILTER_AMOUNT = 7

# Keep each parcel's history attribute well under HA's ~16 KB attribute limit.
HISTORY_MAX_EVENTS = 20

# The server lists at most this many parcels per request.
PARCEL_LIST_LIMIT = 1000

# Calendar cache window used for the entity's "next event" state.
CALENDAR_PAST_DAYS = 1
CALENDAR_FUTURE_DAYS = 60

# Event stream reconnect backoff.
STREAM_BACKOFF_INITIAL_SECONDS = 1.0
STREAM_BACKOFF_MAX_SECONDS = 300.0
# The server sends a heartbeat every 25 s; three missed ones mean the link is dead.
STREAM_READ_TIMEOUT_SECONDS = 90.0

# Server event type -> Home Assistant bus event suffix (fired as f"{DOMAIN}_{suffix}").
# Names follow the suite's contract, so automations only swap the prefix.
SERVER_EVENT_SUFFIXES: dict[str, str] = {
    "parcel.registered": "parcel_registered",
    "parcel.status_changed": "parcel_status_changed",
    "parcel.delivered": "parcel_delivered",
    "parcel.delivery_time_changed": "parcel_delivery_time_changed",
    "parcel.outgoing_registered": "outgoing_parcel_registered",
    "parcel.outgoing_delivered": "outgoing_parcel_delivered",
    "parcel.live_updated": "parcel_live_updated",
    "parcel.removed": "parcel_removed",
    "parcel.deleted": "parcel_deleted",
    "source.state_changed": "source_state_changed",
}
LIVE_POSITION_EVENT = "parcel.live_position"

# Source removed (deleted, or merged into another): fired on the bus, but not a device
# trigger, because the device it would belong to is removed with it.
SOURCE_REMOVED_EVENT = "source.removed"

# Dispatcher signal for courier positions, formatted with the entry id.
SIGNAL_LIVE_POSITION = f"{DOMAIN}_live_position_{{}}"

# Live session states during which the courier's position is meaningful.
LIVE_TRACKING_STATES = frozenset({"en_route"})

ATTRIBUTION = "Data provided by Open Parcels"
