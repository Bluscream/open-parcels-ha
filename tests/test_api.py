"""The HTTP client and the SSE parser."""

from __future__ import annotations

from datetime import UTC, datetime
import re

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.open_parcels.api import (
    OpenParcelsApiError,
    OpenParcelsAuthError,
    OpenParcelsClient,
    OpenParcelsConnectionError,
    OpenParcelsNotFoundError,
    OpenParcelsScopeError,
    SseParser,
    normalize_url,
)

BASE = "http://op.example.test:4000"
API = f"{BASE}/api/v1"
TOKEN = "op_" + "fake"


def _client(hass: HomeAssistant) -> OpenParcelsClient:
    return OpenParcelsClient(async_get_clientsession(hass), f"{BASE}/api/v1/", TOKEN)


def test_normalize_url() -> None:
    """Trailing slashes and the API prefix are dropped."""
    assert normalize_url(" http://x:1/ ") == "http://x:1"
    assert normalize_url("http://x:1/api/v1") == "http://x:1"


def test_sse_parser() -> None:
    """Fields, comments, multi-line data and empty dispatches."""
    parser = SseParser()
    lines = [
        "retry: 5000",
        "",
        ": keep-alive",
        "",
        "id: 5",
        "event: parcel.registered",
        'data: {"a":',
        "data: 1}",
        "",
        "data:no-space",
        "",
        "id: bad\0id",
        "unknown: field",
        "",
    ]
    messages = [m for line in lines if (m := parser.feed_line(line)) is not None]
    assert len(messages) == 2
    assert messages[0].id == "5"
    assert messages[0].event == "parcel.registered"
    assert messages[0].data == '{"a":\n1}'
    assert messages[1].event == "message"
    assert messages[1].data == "no-space"
    assert messages[1].id is None


async def test_requests_send_token_and_parse(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Each method hits its route with the Bearer token."""
    aioclient_mock.get(f"{API}/sources", json=[{"id": "s"}])
    aioclient_mock.get(f"{API}/carriers", json=[{"id": "dhl"}])
    aioclient_mock.get(f"{API}/parcels", json=[{"id": "p"}])
    aioclient_mock.get(f"{API}/calendar", json=[])
    aioclient_mock.post(f"{API}/parcels", json={"id": "p"}, status=201)
    aioclient_mock.patch(f"{API}/parcels/p", json={"id": "p"})
    aioclient_mock.post(f"{API}/sources/s/sync", status=202)
    client = _client(hass)

    assert await client.async_get_sources() == [{"id": "s"}]
    assert await client.async_get_carriers() == [{"id": "dhl"}]
    assert await client.async_get_parcels(include_history=True, limit=5) == [
        {"id": "p"}
    ]
    moment = datetime(2030, 1, 1, tzinfo=UTC)
    assert await client.async_get_calendar(moment, moment) == []
    assert await client.async_track_parcel(
        "TEST0001", carrier="dhl", label="Shoes"
    ) == {"id": "p"}
    assert await client.async_archive_parcel("p") == {"id": "p"}
    assert await client.async_sync_source("s") is None

    for _, url, data, headers in aioclient_mock.mock_calls:
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        if str(url).endswith("/parcels") and data:
            assert data == {
                "barcode": "TEST0001",
                "direction": "incoming",
                "carrier": "dhl",
                "label": "Shoes",
            }


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, OpenParcelsAuthError),
        (403, OpenParcelsScopeError),
        (404, OpenParcelsNotFoundError),
        (500, OpenParcelsApiError),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: type[Exception],
) -> None:
    """HTTP errors map to typed exceptions, with the server's message."""
    aioclient_mock.get(
        f"{API}/sources", status=status, json={"error": "code", "message": "text"}
    )
    with pytest.raises(error) as info:
        await _client(hass).async_get_sources()
    assert isinstance(info.value, OpenParcelsApiError)
    assert info.value.code == "code"
    assert info.value.message == "text"


async def test_error_without_json_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-JSON error body still raises cleanly."""
    aioclient_mock.get(f"{API}/sources", status=502, text="Bad gateway")
    with pytest.raises(OpenParcelsApiError) as info:
        await _client(hass).async_get_sources()
    assert info.value.code is None


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Network errors become OpenParcelsConnectionError."""
    aioclient_mock.get(f"{API}/sources", exc=aiohttp.ClientConnectionError("down"))
    with pytest.raises(OpenParcelsConnectionError):
        await _client(hass).async_get_sources()


async def test_validate(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Read is checked by listing sources, write by a sync that must 404."""
    aioclient_mock.get(f"{API}/sources", json=[])
    aioclient_mock.post(
        re.compile(rf"{API}/sources/.+/sync"),
        status=404,
        json={"error": "not_found"},
    )
    await _client(hass).async_validate()


async def test_validate_without_write_scope(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A read-only token fails validation with a scope error."""
    aioclient_mock.get(f"{API}/sources", json=[])
    aioclient_mock.post(
        re.compile(rf"{API}/sources/.+/sync"),
        status=403,
        json={"error": "forbidden"},
    )
    with pytest.raises(OpenParcelsScopeError):
        await _client(hass).async_validate()


class _FakeContent:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for line in self._lines:
            yield line


class _FakeResponse:
    def __init__(self, status: int, lines: list[bytes]) -> None:
        self.status = status
        self.content = _FakeContent(lines)

    async def text(self) -> str:
        return '{"error": "unauthorized"}'

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None


class _FakeSession:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response
        self.headers: dict[str, str] | None = None

    def get(self, url: str, *, headers: dict[str, str], timeout) -> _FakeResponse:
        self.headers = headers
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


async def test_stream_events() -> None:
    """The stream sends Last-Event-ID, calls on_open and yields parsed messages."""
    session = _FakeSession(
        _FakeResponse(
            200,
            [
                b"retry: 5000\n",
                b"\n",
                b"id: 3\n",
                b"event: x\n",
                b"data: {}\r\n",
                b"\n",
            ],
        )
    )
    client = OpenParcelsClient(session, BASE, TOKEN)  # type: ignore[arg-type]
    opened: list[bool] = []
    messages = [
        m
        async for m in client.async_stream_events("2", 90, lambda: opened.append(True))
    ]
    assert opened == [True]
    assert session.headers["Last-Event-ID"] == "2"
    assert [(m.id, m.event, m.data) for m in messages] == [("3", "x", "{}")]


async def test_stream_errors() -> None:
    """A 401 and a network error surface as typed exceptions."""
    client = OpenParcelsClient(_FakeSession(_FakeResponse(401, [])), BASE, TOKEN)  # type: ignore[arg-type]
    with pytest.raises(OpenParcelsAuthError):
        async for _ in client.async_stream_events(None, 90):
            pass
    client = OpenParcelsClient(
        _FakeSession(aiohttp.ClientConnectionError("down")),  # type: ignore[arg-type]
        BASE,
        TOKEN,
    )
    with pytest.raises(OpenParcelsConnectionError):
        async for _ in client.async_stream_events(None, 90):
            pass
