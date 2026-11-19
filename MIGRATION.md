# Moving from the per-carrier integrations and the Parcel Aggregator

Open Parcels replaces two kinds of integration:
- the per-carrier integrations (`dhl`, `gls`, `hermes`, `amazon_orders`, …), with one device per
  configured account;
- the Parcel Aggregator (`parcel_aggregator`).

The entity keys, attribute names, status values and event names stay the same wherever the
server provides the same data. What changes is listed below.

**Keep the entity IDs of a carrier account.** Label the Open Parcels source like the old config
entry's title. For example, the DHL entry "Germany (7c6c9a)" produced the device "DHL Germany
(7c6c9a)". A source with the label `Germany (7c6c9a)` and the plugin `dhl` produces the same
device name, so it gets the same entity IDs (`sensor.dhl_germany_7c6c9a_incoming_parcels`, …).
A **disabled** config entry keeps its entities in the registry, so their IDs stay taken and the
new entities would get a `_2` suffix. To avoid that, do one of these before adding Open Parcels:
- delete the old entry;
- or rename the old entities' IDs (for example add `_old`) and then disable the entry.

Otherwise, rename the new entities afterwards under Settings → Entities.

## Entities

| Old | New | Notes |
|---|---|---|
| `sensor.parcel_aggregator_incoming_parcels` | `sensor.open_parcels_incoming_parcels` | same key (`incoming`), state and attributes (`by_carrier`, `parcels`) |
| `sensor.parcel_aggregator_outgoing_parcels` | `sensor.open_parcels_outgoing_parcels` | same |
| `sensor.parcel_aggregator_delivered_parcels` | `sensor.open_parcels_delivered_parcels` | same |
| `sensor.parcel_aggregator_outgoing_delivered_parcels` | `sensor.open_parcels_outgoing_delivered_parcels` | same |
| `sensor.parcel_aggregator_en_route_to_pickup_point` | `sensor.open_parcels_en_route_to_pickup_point` | same |
| `sensor.parcel_aggregator_awaiting_pickup` | `sensor.open_parcels_awaiting_pickup` | same |
| `sensor.parcel_aggregator_next_delivery` | `sensor.open_parcels_next_delivery` | adds `barcode`, `sender`, `receiver` beside `by_carrier` and `parcel` |
| `calendar.parcel_aggregator_deliveries` | `calendar.open_parcels_deliveries` | entries come from the server's calendar: title is the server's (label, shop or sender), delivered parcels show as `Delivered: …`, whole-day windows are all-day events |
| `sensor.<carrier device>_incoming_parcels` | `sensor.<source device>_incoming_parcels` | same; per source |
| `sensor.<carrier device>_en_route_to_pickup_point` | `sensor.<source device>_en_route_to_pickup_point` | now on every source (GLS named it "En route to ParcelShop"; it is "En route to pickup point" here) |
| `sensor.<carrier device>_awaiting_pickup` | `sensor.<source device>_awaiting_pickup` | same |
| `sensor.<carrier device>_delivered_parcels` | `sensor.<source device>_delivered_parcels` | same |
| `sensor.<carrier device>_outgoing_parcels`, `_outgoing_delivered_parcels` | same names on the source device | now on every source |
| `sensor.<carrier device>_next_delivery` | `sensor.<source device>_next_delivery` | same `barcode`, `sender`, `receiver`; adds `by_carrier` and `parcel` |
| `sensor.<carrier device>_last_successful_update` | `sensor.<source device>_last_successful_update` | now the source's last successful run on the server, not Home Assistant's last poll; the hub's has the last resync |
| `sensor.<carrier device>_parcel_<barcode>` | `device_tracker.<source device>_parcel_<barcode>` | open parcels only, same state (the status) and suite attributes, plus a position for the map; delivered parcels have no entity and are listed in `sensor.*_delivered_parcels` (`parcel_ids`, `parcels`) |
| `button.<carrier device>_refresh` | `button.<source device>_refresh` | asks the server to run the source; `button.open_parcels_refresh` resyncs everything |
| `calendar.<carrier device>_deliveries` | `calendar.open_parcels_deliveries` | one calendar for all sources |
| (none) | `sensor.<source device>_source_state`, `binary_sensor.<source device>_problem` | new: the source's state, including "needs sign-in" |
| (none) | `binary_sensor.open_parcels_event_stream` | new: connection to the server's event stream |

## Parcel attributes

| Old | New |
|---|---|
| `carrier` (display name such as "DHL") | unchanged; the server's id is in the new `carrier_id` |
| `status` | unchanged values. A manual status set on the server wins; the carrier's own is in the new `carrier_status` |
| `weight`, `dimensions` | always `null` (the server does not publish them) |
| `raw` | always `null` (the server does not publish raw payloads to clients) |
| `history` entries `{timestamp, status, raw_status}` | the same keys plus `location` |
| (none) | `id`, `direction`, `label`, `manual_status`, `items`, `order`, `live` (no coordinates), `lookup`, `source_id`, `first_seen_at`, `updated_at` |

## Events

| Old | New |
|---|---|
| `<carrier>_parcel_registered`, `parcel_aggregator_parcel_registered` | `open_parcels_parcel_registered` |
| `<carrier>_parcel_status_changed`, `parcel_aggregator_parcel_status_changed` | `open_parcels_parcel_status_changed` |
| `<carrier>_parcel_delivered`, `parcel_aggregator_parcel_delivered` | `open_parcels_parcel_delivered` |
| `<carrier>_parcel_delivery_time_changed`, `parcel_aggregator_parcel_delivery_time_changed` | `open_parcels_parcel_delivery_time_changed` |
| `<carrier>_outgoing_parcel_delivered`, `parcel_aggregator_outgoing_parcel_delivered` | `open_parcels_outgoing_parcel_delivered` |
| `<carrier>_outgoing_parcel_status_changed`, `parcel_aggregator_outgoing_parcel_status_changed` | no equivalent: the server has no status-change event for outgoing parcels |
| (none) | `open_parcels_outgoing_parcel_registered`, `open_parcels_parcel_live_updated`, `open_parcels_parcel_removed`, `open_parcels_source_state_changed` |

Event data:
- It is the parcel's attributes plus `device_id`, as before. The per-carrier events included
  `raw`; these never do, as with the aggregator.
- `hub_device_id` is new.
- To filter on a carrier, use `carrier` (display name) or `carrier_id`. To filter on one
  account, use `device_id`.

Device triggers keep their type names (`parcel_registered`, `parcel_status_changed`, …). They exist
on every source device and on the hub.

## Services

| Old | New |
|---|---|
| `<carrier>.track_parcel` (`tracking_code`) | `open_parcels.track_parcel` (`tracking_code`, optional `carrier`, `label`, `direction`) |
| `<carrier>.untrack_parcel` (`tracking_code`) | `open_parcels.archive_parcel` (`tracking_code` or `parcel_id`) |
| per-carrier refresh button | `open_parcels.refresh` (optionally for one parcel) |

## Not carried over

- **Options:**
  - Per-carrier polling options and tracking-code lists: sources and codes are managed on the
    server.
  - The delivered-parcels filter and the history option stay, on this integration.
- **The aggregator's Assist sentences and LLM tools.** Not part of this integration.
- **The aggregator's "no carrier integrations found" repair issue.** Not needed: the sources come
  from the server.
