"""Device naming."""

from __future__ import annotations

from custom_components.open_parcels.device import source_device_name

CARRIERS = {"dhl": "DHL", "gls": "GLS"}


def test_source_device_name() -> None:
    """Carrier plus label, without repeating the carrier."""
    assert source_device_name({"plugin": "dhl", "label": "Germany (x)"}, CARRIERS) == (
        "DHL Germany (x)"
    )
    assert source_device_name({"plugin": "gls", "label": "gls home"}, CARRIERS) == (
        "gls home"
    )
    assert source_device_name({"plugin": "dhl", "label": ""}, CARRIERS) == "DHL"
    assert source_device_name({"plugin": "", "label": "Mail"}, CARRIERS) == "Mail"
