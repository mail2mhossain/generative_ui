"""
AG-UI demo agent — FastAPI + LangGraph + Anthropic Claude

Emits AG-UI SSE events consumed by the Blazor frontend.
Two UI tools: show_weather and show_flight_options.

Usage:
    pip install -r requirements.txt
    ANTHROPIC_API_KEY=sk-ant-... uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import AsyncGenerator

import httpx
from tool_names import ToolNames
from ag_ui.core import (
    EventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

_encoder = EventEncoder()

load_dotenv()

# ---------------------------------------------------------------------------
# FastAPI setup
# ---------------------------------------------------------------------------

app = FastAPI(title="AG-UI Demo Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "http://localhost:5001",
        "http://localhost:5002",
        "https://localhost:7001",
        "https://localhost:7002",
        "http://localhost:*",
    ],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# AG-UI tool names that route to the Blazor frontend (not back to the LLM)
# ---------------------------------------------------------------------------

UI_TOOL_NAMES:       frozenset[str] = ToolNames.all_ui_tools()
_DEFERRED_ARG_TOOLS: frozenset[str] = ToolNames.all_ui_tools()  # both tools fetch real data

# ---------------------------------------------------------------------------
# Open-Meteo weather fetch (no API key required)
# ---------------------------------------------------------------------------

_WMO_CONDITIONS: list[tuple[int | range, str]] = [
    (0,            "Sunny"),
    (1,            "Sunny"),
    (2,            "Partly Cloudy"),
    (3,            "Cloudy"),
    (range(45, 50), "Cloudy"),      # fog
    (range(51, 68), "Rainy"),       # drizzle / rain / freezing rain
    (range(71, 78), "Snowy"),       # snow / snow grains
    (range(80, 83), "Rainy"),       # rain showers
    (range(85, 87), "Snowy"),       # snow showers
    (range(95, 100), "Stormy"),     # thunderstorms
]


def _wmo_to_condition(code: int) -> str:
    for entry, label in _WMO_CONDITIONS:
        if isinstance(entry, range) and code in entry:
            return label
        if isinstance(entry, int) and code == entry:
            return label
    return "Cloudy"


def _fetch_weather(location: str) -> dict:
    """
    Geocode *location* then fetch current conditions from Open-Meteo.
    Returns a dict ready to be serialised as UI_TOOL_CALL_ARGS.
    Raises httpx.HTTPError or ValueError on failure.
    """
    # Step 1 — geocode
    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "language": "en", "format": "json"},
        timeout=10.0,
    )
    geo.raise_for_status()
    results = geo.json().get("results")
    if not results:
        raise ValueError(f"Location not found: {location!r}")

    hit = results[0]
    lat = hit["latitude"]
    lon = hit["longitude"]
    display = hit.get("name", location)
    country = hit.get("country", "")
    if country:
        display = f"{display}, {country}"

    # Step 2 — current weather
    wx = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "wind_speed_unit": "kmh",
        },
        timeout=10.0,
    )
    wx.raise_for_status()
    current = wx.json()["current"]

    return {
        "location":    display,
        "temperature": current["temperature_2m"],
        "condition":   _wmo_to_condition(current["weather_code"]),
        "humidity":    current["relative_humidity_2m"],
        "wind_speed":  current["wind_speed_10m"],
    }


# ---------------------------------------------------------------------------
# Amadeus flight search (sandbox — free, no billing required)
# ---------------------------------------------------------------------------

_AMADEUS_BASE = "https://test.api.amadeus.com"

# Simple in-process token cache: avoids a round-trip on every request.
_amadeus_token: dict = {"value": "", "expires_at": 0.0}


def _amadeus_access_token() -> str:
    """Return a valid Amadeus OAuth2 bearer token, refreshing if expired."""
    if time.time() < _amadeus_token["expires_at"] - 30:
        return _amadeus_token["value"]

    client_id     = os.getenv("AMADEUS_CLIENT_ID", "")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError(
            "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET must be set in .env. "
            "Register free at https://developers.amadeus.com"
        )

    resp = httpx.post(
        f"{_AMADEUS_BASE}/v1/security/oauth2/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    body = resp.json()
    _amadeus_token["value"]      = body["access_token"]
    _amadeus_token["expires_at"] = time.time() + body.get("expires_in", 1799)
    return _amadeus_token["value"]


def _parse_duration(iso: str) -> str:
    """Convert ISO 8601 duration PT13H30M → '13h 30m'."""
    h = int(m.group(1)) if (m := re.search(r"(\d+)H", iso)) else 0
    mn = int(m.group(1)) if (m := re.search(r"(\d+)M", iso)) else 0
    return f"{h}h {mn}m" if mn else f"{h}h"


def _mock_flights(origin: str, destination: str, date: str) -> dict:
    """
    Generate deterministic but realistic-looking flight data.
    Used automatically when AMADEUS_CLIENT_ID is not configured.
    """
    import hashlib

    seed = int(hashlib.md5(f"{origin}{destination}{date}".encode()).hexdigest()[:8], 16)

    pool = [
        ("British Airways",    "BA"),
        ("Lufthansa",          "LH"),
        ("Air France",         "AF"),
        ("Emirates",           "EK"),
        ("Singapore Airlines", "SQ"),
        ("Qatar Airways",      "QR"),
        ("KLM",                "KL"),
        ("United Airlines",    "UA"),
    ]

    # Rough duration heuristic: longer route codes → longer flight
    route_len = abs(hash(f"{origin}{destination}")) % 10 + 2   # 2–11 h

    flights = []
    for i in range(4):
        airline, code = pool[(seed + i * 7) % len(pool)]
        number        = f"{code}{((seed + i * 13) % 900) + 100}"
        dep_h         = (6 + i * 4 + seed % 3) % 24
        dep_m         = (seed * (i + 1)) % 60
        dur_h         = route_len + (i % 2)
        dur_m         = (seed * (i + 3)) % 60
        arr_h         = (dep_h + dur_h + (dep_m + dur_m) // 60) % 24
        arr_m         = (dep_m + dur_m) % 60
        price         = round(120 + (seed % 400) + i * 45 + route_len * 30, 2)

        flights.append({
            "airline":        airline,
            "flight_number":  number,
            "departure_time": f"{dep_h:02d}:{dep_m:02d}",
            "arrival_time":   f"{arr_h:02d}:{arr_m:02d}",
            "price_gbp":      price,
            "duration":       f"{dur_h}h {dur_m}m" if dur_m else f"{dur_h}h",
        })

    return {
        "origin":      origin.upper(),
        "destination": destination.upper(),
        "date":        date,
        "flights":     flights,
    }


def _fetch_flights(origin: str, destination: str, date: str) -> dict:
    """
    Search Amadeus sandbox for up to 4 one-way flight offers.
    Falls back to mock data when AMADEUS_CLIENT_ID is not configured.
    Returns a dict ready to be serialised as UI_TOOL_CALL_ARGS.
    """
    if not os.getenv("AMADEUS_CLIENT_ID", "").strip() or \
       os.getenv("AMADEUS_CLIENT_ID", "") == "your_client_id_here":
        return _mock_flights(origin, destination, date)

    token = _amadeus_access_token()

    resp = httpx.get(
        f"{_AMADEUS_BASE}/v2/shopping/flight-offers",
        params={
            "originLocationCode":      origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate":           date,
            "adults":                  1,
            "max":                     4,
            "currencyCode":            "GBP",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    body = resp.json()

    carriers: dict = body.get("dictionaries", {}).get("carriers", {})
    flights = []

    for offer in body.get("data", []):
        itin     = offer["itineraries"][0]
        segments = itin["segments"]
        first    = segments[0]
        last     = segments[-1]

        carrier_code  = first["carrierCode"]
        airline_name  = carriers.get(carrier_code, carrier_code)
        flight_number = f"{carrier_code}{first['number']}"
        dep_time      = first["departure"]["at"][11:16]   # HH:MM
        arr_time      = last["arrival"]["at"][11:16]
        duration      = _parse_duration(itin["duration"])
        price         = float(offer["price"]["total"])

        flights.append({
            "airline":        airline_name,
            "flight_number":  flight_number,
            "departure_time": dep_time,
            "arrival_time":   arr_time,
            "price_gbp":      price,
            "duration":       duration,
        })

    return {
        "origin":      origin.upper(),
        "destination": destination.upper(),
        "date":        date,
        "flights":     flights,
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@tool(ToolNames.SHOW_WEATHER)
def show_weather(location: str) -> str:
    """Fetch live weather and display a weather card for the given city or location.

    The tool retrieves real current conditions from Open-Meteo — no need to
    supply temperature, humidity, or wind values; the tool fetches them.
    """
    try:
        data = _fetch_weather(location)
    except ValueError as exc:
        return f"Error: {exc}"
    except httpx.HTTPError as exc:
        return f"Weather service error: {exc}"
    return json.dumps(data)


@tool(ToolNames.SHOW_FLIGHT_OPTIONS)
def show_flight_options(origin: str, destination: str, date: str) -> str:
    """Search live flights and display options for the user to browse.

    Use IATA codes for origin and destination (e.g. LHR, JFK, NRT, SYD).
    date must be YYYY-MM-DD format.
    The tool fetches real offers from Amadeus — do not supply flight lists.
    """
    try:
        data = _fetch_flights(origin, destination, date)
    except ValueError as exc:
        return f"Error: {exc}"
    except httpx.HTTPError as exc:
        return f"Flight service error: {exc}"
    return json.dumps(data)


# Verify at module load that the registered constant matches the actual tool name.
# If someone changes ToolNames without updating the function (or vice versa), this
# raises immediately — before the server accepts a single request.
assert show_weather.name == ToolNames.SHOW_WEATHER, (
    f"Tool name mismatch: function registered as '{show_weather.name}', "
    f"ToolNames.SHOW_WEATHER='{ToolNames.SHOW_WEATHER}'"
)
assert show_flight_options.name == ToolNames.SHOW_FLIGHT_OPTIONS, (
    f"Tool name mismatch: function registered as '{show_flight_options.name}', "
    f"ToolNames.SHOW_FLIGHT_OPTIONS='{ToolNames.SHOW_FLIGHT_OPTIONS}'"
)


# ---------------------------------------------------------------------------
# LangGraph agent
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a helpful travel assistant.

When the user asks about weather, call show_weather with just the city or location name.
The tool fetches live data automatically — do not supply temperature, humidity, or wind values.

When the user asks about flights, call show_flight_options with:
  - origin: IATA airport or city code (e.g. LHR for London, JFK for New York, NRT for Tokyo)
  - destination: IATA airport or city code
  - date: departure date as YYYY-MM-DD (if unspecified, use today or the next convenient date)
The tool fetches real offers from Amadeus — do not supply flight lists yourself.

After calling a UI tool, follow up with one short sentence confirming what you displayed.
Keep all non-tool responses brief and conversational.
"""

llm = ChatAnthropic(
    model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
    streaming=True,
)

agent = create_react_agent(
    llm,
    tools=[show_weather, show_flight_options],
    prompt=_SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------


def _extract_text(chunk) -> str:
    """Pull plain text out of a LangChain message chunk, ignoring tool-call deltas."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


# ---------------------------------------------------------------------------
# AG-UI event stream generator
# ---------------------------------------------------------------------------


async def _ag_ui_stream(message: str, thread_id: str) -> AsyncGenerator[str, None]:
    run_id   = str(uuid.uuid4())
    tid      = thread_id or run_id

    yield _encoder.encode(RunStartedEvent(
        type=EventType.RUN_STARTED,
        run_id=run_id,
        thread_id=tid,
    ))

    current_message_id: str | None = None
    text_open = False
    # Maps tool run_id → tool_call_name for deferred-arg tools mid-flight.
    pending_deferred: dict[str, str] = {}

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": tid}},
            version="v2",
        ):
            kind: str = event["event"]

            # ----------------------------------------------------------
            # Text streaming
            # ----------------------------------------------------------
            if kind == "on_chat_model_start":
                current_message_id = str(uuid.uuid4())
                text_open = False

            elif kind == "on_chat_model_stream":
                text = _extract_text(event["data"]["chunk"])
                if text:
                    if not text_open:
                        yield _encoder.encode(TextMessageStartEvent(
                            type=EventType.TEXT_MESSAGE_START,
                            message_id=current_message_id,
                            role="assistant",
                        ))
                        text_open = True
                    yield _encoder.encode(TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=current_message_id,
                        delta=text,
                    ))

            elif kind == "on_chat_model_end":
                if text_open:
                    yield _encoder.encode(TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=current_message_id,
                    ))
                    text_open = False

            # ----------------------------------------------------------
            # Tool calls — start
            # ----------------------------------------------------------
            elif kind == "on_tool_start":
                tool_name: str = event["name"]
                tool_input: dict = event["data"].get("input", {})
                tool_call_id: str = str(event.get("run_id", uuid.uuid4()))

                # AG-UI contract: close any in-progress text first
                if text_open:
                    yield _encoder.encode(TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=current_message_id,
                    ))
                    text_open = False

                if tool_name in UI_TOOL_NAMES:
                    yield _encoder.encode(ToolCallStartEvent(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=tool_call_id,
                        tool_call_name=tool_name,
                    ))

                    if tool_name in _DEFERRED_ARG_TOOLS:
                        # Args will arrive via on_tool_end once the real fetch completes.
                        pending_deferred[tool_call_id] = tool_name
                    else:
                        # LLM-populated tool: emit args immediately from the input.
                        yield _encoder.encode(ToolCallArgsEvent(
                            type=EventType.TOOL_CALL_ARGS,
                            tool_call_id=tool_call_id,
                            delta=json.dumps(tool_input),
                        ))
                        yield _encoder.encode(ToolCallEndEvent(
                            type=EventType.TOOL_CALL_END,
                            tool_call_id=tool_call_id,
                        ))

            # ----------------------------------------------------------
            # Tool calls — end (deferred-arg tools only)
            # ----------------------------------------------------------
            elif kind == "on_tool_end":
                tool_call_id = str(event.get("run_id", ""))
                if tool_call_id in pending_deferred:
                    raw_output = event["data"].get("output", "")
                    if hasattr(raw_output, "content"):
                        raw_output = raw_output.content
                    # Validate the tool returned valid JSON; fall back gracefully.
                    try:
                        json.loads(raw_output)
                        args_json = raw_output
                    except (json.JSONDecodeError, TypeError):
                        args_json = json.dumps({"error": str(raw_output)})

                    yield _encoder.encode(ToolCallArgsEvent(
                        type=EventType.TOOL_CALL_ARGS,
                        tool_call_id=tool_call_id,
                        delta=args_json,
                    ))
                    yield _encoder.encode(ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=tool_call_id,
                    ))
                    del pending_deferred[tool_call_id]

    except Exception as exc:  # noqa: BLE001
        yield _encoder.encode(RunErrorEvent(
            type=EventType.RUN_ERROR,
            message=str(exc),
        ))

    yield _encoder.encode(RunFinishedEvent(
        type=EventType.RUN_FINISHED,
        run_id=run_id,
        thread_id=tid,
    ))


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    message: str
    thread_id: str = ""


@app.post("/api/agent/run")
async def run_agent(body: RunRequest) -> StreamingResponse:
    return StreamingResponse(
        _ag_ui_stream(body.message, body.thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/agent/schema")
async def schema() -> dict:
    """Expose the list of UI tool names so the Blazor frontend can validate
    its ComponentRegistry against the agent at startup."""
    return {"ui_tools": sorted(UI_TOOL_NAMES)}
