# Open Parcels for Home Assistant

Parcel (package) tracking in Home Assistant from an [Open Parcels](https://github.com/Bluscream/open-parcels)
server. One integration covers every carrier, shop and mailbox the server follows:

- each **source** on the server (a carrier account, a tracking source, a shop or a mailbox) becomes
  a Home Assistant device;
- each **parcel** becomes an entity on its source's device.

Changes arrive live over the server's event stream. A slow full resync runs every 30 minutes to
catch anything the stream missed. The integration never polls in a tight loop.

Coming from the per-carrier parcel integrations or the Parcel Aggregator? See
[MIGRATION.md](MIGRATION.md) for every renamed entity, attribute, event and service.

## Requirements

- An Open Parcels server reachable from Home Assistant. This can be the Home Assistant app or a
  container such as `http://192.168.1.10:4000`.
- An API token with the scopes **read** and **write**. Create it in the Open Parcels web interface
  under Settings → API tokens. The integration never needs `admin`.
- Home Assistant 2025.12 or newer.

## Installation

**HACS (custom repository):** HACS → ⋮ → Custom repositories → add this repository as an
*Integration* → install **Open Parcels** → restart Home Assistant.

**Manual:** copy `custom_components/open_parcels` into your Home Assistant
`config/custom_components/` folder and restart.

Then go to **Settings → Devices & services → Add integration → Open Parcels** and enter the server
URL and the token.

**Discovery:**
- The Open Parcels Home Assistant app announces itself (`discovery: [open_parcels]`). If the app
  passes an `api_token` in its discovery data, the entry is created right away. Otherwise you are
  asked for a token.
- Servers that advertise `_open-parcels._tcp` over zeroconf are offered too.

The token can be replaced later with *Reconfigure*. If the server ever refuses the token, Home
Assistant asks for a new one (reauthentication).

## Devices and entities

### Hub device "Open Parcels"

| Entity | Key | State | Attributes |
|---|---|---|---|
| `sensor.open_parcels_incoming_parcels` | `incoming` | number of active incoming parcels | `by_carrier`, `parcels` |
| `sensor.open_parcels_outgoing_parcels` | `outgoing` | active outgoing parcels | `by_carrier`, `parcels` |
| `sensor.open_parcels_delivered_parcels` | `delivered` | recently delivered incoming parcels | `by_carrier`, `parcels` |
| `sensor.open_parcels_outgoing_delivered_parcels` | `outgoing_delivered` | recently delivered outgoing parcels | `by_carrier`, `parcels` |
| `sensor.open_parcels_en_route_to_pickup_point` | `en_route_to_pickup_point` | heading for a pickup point | `by_carrier`, `parcels` |
| `sensor.open_parcels_awaiting_pickup` | `awaiting_pickup` | ready to collect | `by_carrier`, `parcels` |
| `sensor.open_parcels_next_delivery` | `next_delivery` | earliest `planned_from` (timestamp) | `barcode`, `sender`, `receiver`, `by_carrier`, `parcel` |
| `sensor.open_parcels_last_successful_update` | `last_update` | last full resync (diagnostic) | |
| `calendar.open_parcels_deliveries` | `deliveries` | next expected delivery | the same entries as the server's calendar and ICS feed |
| `button.open_parcels_refresh` | `refresh` | | resyncs everything now |
| `binary_sensor.open_parcels_event_stream` | `event_stream` | event stream connected (diagnostic) | `events_received` |

Parcels that no source follows (tracked by code only) live on the hub device.

### One device per source, e.g. "DHL Germany (abc123)"

The device is named `<carrier> <source label>`. When the label already starts with the carrier's
name, the name is not repeated. It is linked to the hub (`via_device`).

| Entity | State |
|---|---|
| `sensor.<device>_incoming_parcels`, `_en_route_to_pickup_point`, `_awaiting_pickup`, `_delivered_parcels`, `_outgoing_parcels`, `_outgoing_delivered_parcels` | count, with `by_carrier` and `parcels` |
| `sensor.<device>_next_delivery` | earliest expected delivery of this source |
| `sensor.<device>_last_successful_update` | the source's last successful run on the server (diagnostic) |
| `sensor.<device>_source_state` | `ok`, `needs_sign_in`, `error` or `disabled` (diagnostic), with `detail`, `plugin`, `kind`, `last_run_at`, `next_run_at`, `last_ok_at` |
| `binary_sensor.<device>_problem` | on while the source needs a sign-in or fails (diagnostic) |
| `button.<device>_refresh` | asks the server to run this source now |
| `sensor.<device>_parcel_<barcode>` | one per parcel: its status |
| `device_tracker.<device>_courier_<barcode>` | the courier's current position while a live session runs |

A parcel belongs to the source that follows it as its primary source, then a hand-off, then a
mailbox.

### Parcel sensors

The state is the canonical status: `registered`, `in_transit`, `out_for_delivery`,
`at_pickup_point`, `delivered`, `returning`, `problem` or `unknown`. A manual status set on the
server wins over the carrier's status.

The attributes start with the suite's parcel keys, in the suite's order: `carrier` (display
name), `barcode`, `sender`, `receiver`, `status`, `raw_status`, `delivered`, `delivered_at`,
`planned_from`, `planned_to`, `pickup`, `pickup_point`, `url`, `weight`, `dimensions`, `history`,
`raw`. Then come the server's additions: `id`, `carrier_id`, `direction`, `label`,
`carrier_status`, `manual_status`, `items`, `order`, `live` (without coordinates), `lookup`,
`source_id`, `first_seen_at`, `updated_at`.

- `weight`, `dimensions` and `raw` are always `null`: the server does not publish them.
- `history` is `null` unless the *Include status history* option is on.

Active parcels and recently delivered ones (see *Delivered parcels* in the options) have
entities. An entity disappears when its parcel is delivered past the retention window, archived
or removed.

### Courier positions

`device_tracker` entities show where the courier is **right now**. Latitude, longitude, accuracy,
the fix time and stops-away are kept out of the recorder, so Home Assistant stores no trail. The
entity becomes unavailable when the session ends or the courier reaches the stop before yours. The
server never publishes the position from that point on.

## Events and device triggers

Every server event is fired on the Home Assistant bus as `open_parcels_<type>`:

| Server event | Home Assistant event / device trigger |
|---|---|
| `parcel.registered` | `open_parcels_parcel_registered` |
| `parcel.status_changed` | `open_parcels_parcel_status_changed` (`old_status`, `new_status`) |
| `parcel.delivered` | `open_parcels_parcel_delivered` (the only event for the hop to delivered) |
| `parcel.delivery_time_changed` | `open_parcels_parcel_delivery_time_changed` (`old_*`, `new_*`) |
| `parcel.outgoing_registered` | `open_parcels_outgoing_parcel_registered` |
| `parcel.outgoing_delivered` | `open_parcels_outgoing_parcel_delivered` |
| `parcel.live_updated` | `open_parcels_parcel_live_updated` |
| `parcel.removed` | `open_parcels_parcel_removed` |
| `source.state_changed` | `open_parcels_source_state_changed` (`source_id`, `plugin`, `label`, `old_state`, `new_state`, `detail`) |

Parcel events carry the parcel attributes listed above (without `raw`), the server's `old_*` and
`new_*` fields, `device_id` (the parcel's source device) and `hub_device_id`. Device triggers of
the same names exist on every device: a source device's triggers fire for its own parcels, the
hub's for all of them.

- Events missed while the stream was briefly disconnected are replayed with `Last-Event-ID`.
- Events from while Home Assistant was not running are not replayed: like the per-carrier
  integrations, a restart does not re-announce old changes.

## Services

| Service | Fields | Does |
|---|---|---|
| `open_parcels.track_parcel` | `tracking_code`, optional `carrier`, `label`, `direction`, `config_entry_id` | starts tracking a code; returns `parcel_id` and `carrier` |
| `open_parcels.archive_parcel` | `tracking_code` or `parcel_id`, optional `config_entry_id` | archives the parcel on the server |
| `open_parcels.refresh` | optional `tracking_code` or `parcel_id`, `config_entry_id` | runs the sources that follow the parcel (if given), then resyncs |

`config_entry_id` is only needed when more than one server is set up.

## Options

- **Full resync interval** (default 30 min).
- **Include status history** (off).
- **Delivered parcels: filter by** days or number of parcels, and the amount (default: last 7
  days).

## Diagnostics

The diagnostics download redacts the token, the URL, tracking codes, names, addresses, item
titles, place names, source labels and configuration, and coordinates.

## Development

The gate is the suite's: `ruff check .`, `ruff format --check .`,
`mypy custom_components/open_parcels --ignore-missing-imports` and
`python -m pytest tests/ --cov=custom_components.open_parcels`. Coverage stays above 95 %.

Current Home Assistant does not import on Windows (`fcntl`). On Windows, run the tests in a
container:

```sh
docker run --rm -v "$PWD:/repo" -v opha-venv:/venv -w /repo python:3.14-slim \
  sh -c "python -m venv /venv && /venv/bin/pip install -q -r requirements-dev.txt && /venv/bin/python -m pytest tests"
```

Test fixtures contain made-up values only.
