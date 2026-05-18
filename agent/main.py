"""
AG-UI demo agent — FastAPI + LangGraph + Anthropic Claude + CopilotKit

CopilotKit manages all AG-UI SSE event emission automatically.
The two-tool pattern (data tool + display tool) ensures that
TOOL_CALL_ARGS carries the complete display payload that
WeatherCardParameters and FlightOptionsParameters expect.

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
from typing import Any, AsyncGenerator

import httpx
from ag_ui.core import EventType, RunAgentInput, ToolCallArgsEvent
from ag_ui.encoder import EventEncoder
from copilotkit import LangGraphAGUIAgent
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from tool_names import ToolNames

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

UI_TOOL_NAMES: frozenset[str] = ToolNames.all_ui_tools()

# ---------------------------------------------------------------------------
# Open-Meteo weather fetch (no API key required)
# ---------------------------------------------------------------------------

_WMO_CONDITIONS: list[tuple[int | range, str]] = [
    (0,              "Sunny"),
    (1,              "Sunny"),
    (2,              "Partly Cloudy"),
    (3,              "Cloudy"),
    (range(45, 50),  "Cloudy"),       # fog
    (range(51, 68),  "Rainy"),        # drizzle / rain / freezing rain
    (range(71, 78),  "Snowy"),        # snow / snow grains
    (range(80, 83),  "Rainy"),        # rain showers
    (range(85, 87),  "Snowy"),        # snow showers
    (range(95, 100), "Stormy"),       # thunderstorms
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
    Returns a dict matching WeatherCardParameters field names.
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

    hit     = results[0]
    lat     = hit["latitude"]
    lon     = hit["longitude"]
    display = hit.get("name", location)
    country = hit.get("country", "")
    if country:
        display = f"{display}, {country}"

    # Step 2 — current weather
    wx = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude":        lat,
            "longitude":       lon,
            "current":         "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
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
    h  = int(m.group(1)) if (m := re.search(r"(\d+)H", iso)) else 0
    mn = int(m.group(1)) if (m := re.search(r"(\d+)M", iso)) else 0
    return f"{h}h {mn}m" if mn else f"{h}h"


def _mock_flights(origin: str, destination: str, date: str) -> dict:
    """
    Generate deterministic but realistic-looking flight data.
    Used automatically when AMADEUS_CLIENT_ID is not configured.
    """
    import hashlib

    seed     = int(hashlib.md5(f"{origin}{destination}{date}".encode()).hexdigest()[:8], 16)
    pool     = [
        ("British Airways",    "BA"),
        ("Lufthansa",          "LH"),
        ("Air France",         "AF"),
        ("Emirates",           "EK"),
        ("Singapore Airlines", "SQ"),
        ("Qatar Airways",      "QR"),
        ("KLM",                "KL"),
        ("United Airlines",    "UA"),
    ]
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
    Returns a dict matching FlightOptionsParameters field names.
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
    body     = resp.json()
    carriers = body.get("dictionaries", {}).get("carriers", {})
    flights  = []

    for offer in body.get("data", []):
        itin         = offer["itineraries"][0]
        segments     = itin["segments"]
        first        = segments[0]
        last         = segments[-1]
        carrier_code = first["carrierCode"]

        flights.append({
            "airline":        carriers.get(carrier_code, carrier_code),
            "flight_number":  f"{carrier_code}{first['number']}",
            "departure_time": first["departure"]["at"][11:16],
            "arrival_time":   last["arrival"]["at"][11:16],
            "price_gbp":      float(offer["price"]["total"]),
            "duration":       _parse_duration(itin["duration"]),
        })

    return {
        "origin":      origin.upper(),
        "destination": destination.upper(),
        "date":        date,
        "flights":     flights,
    }


# ---------------------------------------------------------------------------
# Tool definitions — two-tool pattern
#
# Each UI capability is split into:
#   1. A data tool  — fetches real data; returns JSON to the LLM context.
#   2. A display tool — LLM re-supplies all values as explicit parameters;
#                       CopilotKit emits those as TOOL_CALL_ARGS;
#                       Blazor hydrates WeatherCardParameters /
#                       FlightOptionsParameters from those args.
# ---------------------------------------------------------------------------


# --- Weather: data tool ---------------------------------------------------

@tool(ToolNames.GET_WEATHER_DATA)
def get_weather_data(location: str) -> str:
    """Fetch current weather conditions for a city or location.

    Returns JSON containing:
      location    — the resolved display name (e.g. "London, United Kingdom")
      temperature — current temperature in °C
      condition   — one of: Sunny, Partly Cloudy, Cloudy, Rainy, Snowy, Stormy
      humidity    — relative humidity as an integer percentage
      wind_speed  — wind speed in km/h

    Call this tool BEFORE calling show_weather.  Do not invent weather values.
    """
    try:
        return json.dumps(_fetch_weather(location))
    except ValueError as exc:
        return f"Error: {exc}"
    except httpx.HTTPError as exc:
        return f"Weather service error: {exc}"


# --- Weather: display tool ------------------------------------------------

@tool(ToolNames.SHOW_WEATHER)
def show_weather(
    location:    str,
    temperature: float,
    condition:   str,
    humidity:    int,
    wind_speed:  float,
) -> str:
    """Display a weather card with the provided values.

    IMPORTANT: Call get_weather_data first to obtain real values, then pass
    ALL fields from its response to this tool unchanged.  Do not invent or
    modify temperature, condition, humidity, or wind_speed.

    location    — resolved display name from get_weather_data
    temperature — °C value from get_weather_data
    condition   — condition string from get_weather_data
    humidity    — integer percentage from get_weather_data
    wind_speed  — km/h value from get_weather_data
    """
    return "Weather card displayed."


# --- Flights: data tool ---------------------------------------------------

@tool(ToolNames.SEARCH_FLIGHTS)
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flight options between two airports.

    origin      — IATA airport code (e.g. LHR for London Heathrow)
    destination — IATA airport code (e.g. JFK for New York JFK)
    date        — departure date in YYYY-MM-DD format

    Returns JSON containing origin, destination, date, and a flights array.
    Each flight has: airline, flight_number, departure_time,
    arrival_time, price_gbp, duration.

    Call this tool BEFORE calling show_flight_options.
    """
    try:
        return json.dumps(_fetch_flights(origin, destination, date))
    except ValueError as exc:
        return f"Error: {exc}"
    except httpx.HTTPError as exc:
        return f"Flight service error: {exc}"


# --- Flights: display tool ------------------------------------------------

@tool(ToolNames.SHOW_FLIGHT_OPTIONS)
def show_flight_options(
    origin:      str,
    destination: str,
    date:        str,
    flights:     list[dict[str, Any]],
) -> str:
    """Display a flight options panel with the provided data.

    IMPORTANT: Call search_flights first, then pass its ENTIRE response to
    this tool.  Do not modify, filter, or invent flight details.

    origin, destination, date — pass through from search_flights unchanged
    flights — the complete flights array from search_flights; each element
              must have: airline, flight_number, departure_time,
              arrival_time, price_gbp, duration
    """
    return "Flight options displayed."


# --- MCP App: Excalidraw --------------------------------------------------

@tool(ToolNames.OPEN_EXCALIDRAW)
def open_excalidraw(
    mcp_server_url: str,
    initial_prompt: str,
    title: str,
) -> str:
    """Open the Excalidraw diagramming app in a sandboxed panel.

    Use this tool when the user wants to draw, sketch, or diagram anything —
    architecture diagrams, sequence diagrams, flowcharts, wireframes, etc.

    ALWAYS call this tool with these exact values:
      mcp_server_url — ALWAYS "https://excalidraw.com" (never change this)
      initial_prompt — a clear natural-language instruction describing what to
                       draw, e.g. "Draw a sequence diagram for the login flow"
      title          — ALWAYS "Excalidraw" (never change this)

    Do NOT call any data-fetch tools before this one — Excalidraw is
    self-contained.
    """
    return "Excalidraw opened."


# --- Fully open-ended UI: generated HTML ----------------------------------

@tool(ToolNames.GENERATE_UI)
def generate_ui(html_content: str, title: str) -> str:
    """Display a custom interactive HTML interface generated entirely from scratch.

    Use this tool for:
      - Animations and visual effects (e.g. "make it rain tacos")
      - Mini-games and interactive toys
      - Calculators, converters, and custom input tools
      - Data visualisations without live data
      - Any creative or open-ended UI request that doesn't fit
        weather / flight / dashboard patterns

    IMPORTANT — the HTML runs inside a double-sandboxed iframe.
    You MUST follow ALL rules below or the UI will be broken or blank:

    html_content rules:
      1. Start with <!DOCTYPE html><html> and end with </html>
      2. ALL CSS must be inside <style> tags in <head> — nowhere else
      3. ALL JavaScript must be inside <script> tags in <body> — no src= attributes
      4. NO external URLs of any kind:
           ✗ No CDN links  ✗ No Google Fonts  ✗ No <img src="http…">
           ✗ No import statements referencing external modules
      5. Use EMOJI for icons and visual elements (they render without images)
      6. Sandbox restrictions — these APIs are NOT available:
           ✗ localStorage / sessionStorage  ✗ document.cookie
           ✗ fetch / XMLHttpRequest         ✗ window.parent / window.top
      7. For animations: use requestAnimationFrame, NOT setInterval/setTimeout
         for the render loop — this produces smooth 60fps and avoids jank
      8. DOM cleanup: ALWAYS remove elements that leave the viewport to prevent
         unbounded memory growth (e.g. after a taco falls off-screen, call
         element.remove())
      9. The viewport is exactly 100vw × 100vh inside the iframe
     10. The document must be visually complete immediately on load —
         no loading states, no placeholder text

    title — short panel header label, e.g. "Taco Rain" or "Fibonacci Spiral"
    """
    return "UI displayed."


# --- Declarative view: display tool ---------------------------------------

@tool(ToolNames.SHOW_DECLARATIVE_VIEW)
def show_declarative_view(title: str, blocks: list[dict[str, Any]]) -> str:
    """Display a rich declarative UI layout assembled from typed building blocks.

    Use this tool when the user asks for a dashboard, summary, overview, or
    comparison — anything that benefits from a mixed layout of metrics,
    flight rows, and headings rather than a single card.

    title  — a short heading for the whole layout (e.g. "London → New York Travel Summary")
    blocks — ordered list of block objects.  Each block MUST have a "type" field.

    Supported block types and their required fields:

    page_title
      text      — the heading text (string)
      subtitle  — optional subheading (string, omit if not needed)

    search_header
      origin      — departure city or airport code (string)
      destination — arrival city or airport code (string)
      date        — travel date, e.g. "2025-06-15" (string)
      label       — optional summary label, e.g. "4 flights found" (string)

    metric_card
      label — short label below the value (string)
      value — the highlighted metric string, e.g. "£245" or "13°C" (string)
      icon  — optional emoji icon, e.g. "✈" or "🌡" (string)
      trend — optional direction: "up", "down", or "" (string)

    flight_row
      airline        — full airline name (string)
      flight_number  — IATA code + number, e.g. "BA117" (string)
      departure_time — HH:MM (string)
      arrival_time   — HH:MM (string)
      duration       — human readable, e.g. "7h 30m" (string)
      price_gbp      — numeric price as a float (number)
      airline_initial — single letter badge, e.g. "B" (string)

    Rules:
    - Always start with a page_title block.
    - For travel summaries: add a search_header, then metric_cards (cheapest price,
      fastest flight, weather), then individual flight_row blocks.
    - Consecutive metric_card blocks are automatically arranged in a grid row —
      group them together for best layout.
    - Call the relevant data tools (get_weather_data, search_flights) FIRST to
      obtain real values.  Never invent prices, times, or weather figures.
    """
    return "Declarative view displayed."


# ---------------------------------------------------------------------------
# Assertions — fail at module load on any name mismatch
# ---------------------------------------------------------------------------

assert get_weather_data.name == ToolNames.GET_WEATHER_DATA, (
    f"Tool name mismatch: function='{get_weather_data.name}' "
    f"constant='{ToolNames.GET_WEATHER_DATA}'"
)
assert show_weather.name == ToolNames.SHOW_WEATHER, (
    f"Tool name mismatch: function='{show_weather.name}' "
    f"constant='{ToolNames.SHOW_WEATHER}'"
)
assert search_flights.name == ToolNames.SEARCH_FLIGHTS, (
    f"Tool name mismatch: function='{search_flights.name}' "
    f"constant='{ToolNames.SEARCH_FLIGHTS}'"
)
assert show_flight_options.name == ToolNames.SHOW_FLIGHT_OPTIONS, (
    f"Tool name mismatch: function='{show_flight_options.name}' "
    f"constant='{ToolNames.SHOW_FLIGHT_OPTIONS}'"
)
assert show_declarative_view.name == ToolNames.SHOW_DECLARATIVE_VIEW, (
    f"Tool name mismatch: function='{show_declarative_view.name}' "
    f"constant='{ToolNames.SHOW_DECLARATIVE_VIEW}'"
)
assert open_excalidraw.name == ToolNames.OPEN_EXCALIDRAW, (
    f"Tool name mismatch: function='{open_excalidraw.name}' "
    f"constant='{ToolNames.OPEN_EXCALIDRAW}'"
)
assert generate_ui.name == ToolNames.GENERATE_UI, (
    f"Tool name mismatch: function='{generate_ui.name}' "
    f"constant='{ToolNames.GENERATE_UI}'"
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a helpful travel assistant.

== SINGLE-FOCUS REQUESTS ==

When the user asks ONLY about weather (no flights):
  1. Call get_weather_data with the city or location name.
  2. Call show_weather and pass ALL fields from get_weather_data exactly:
       location    → the display name returned (e.g. "London, United Kingdom")
       temperature → the temperature value
       condition   → the condition string (e.g. "Partly Cloudy")
       humidity    → the humidity integer
       wind_speed  → the wind_speed value
  Never invent or estimate weather values.

When the user asks ONLY about flights (no weather):
  1. Call search_flights with:
       origin      → IATA code (e.g. LHR, JFK, NRT, SYD)
       destination → IATA code
       date        → YYYY-MM-DD (use today or next convenient date if unspecified)
  2. Call show_flight_options and pass ALL fields exactly as returned:
       origin, destination, date → unchanged
       flights → the complete flights array, every element intact
  Never modify, filter, or invent flight details.

== DASHBOARD / SUMMARY / OVERVIEW REQUESTS ==

When the user asks for a "dashboard", "travel summary", "overview", "trip plan",
or anything that combines flights AND weather for the same trip:
  1. Call search_flights to get real flight data.
  2. Call get_weather_data for the DESTINATION city.
  3. Then call show_declarative_view with:
       title  → e.g. "London → New York Travel Summary"
       blocks → an ordered list of blocks:

       a. page_title block — title text + subtitle with the travel date
       b. search_header block — origin, destination, date, label = "N flights found"
       c. Three metric_card blocks side-by-side:
            - Cheapest flight: label="Cheapest Flight", value="£<price>", icon="✈"
            - Fastest flight:  label="Fastest Flight", value="<duration>", icon="⏱"
            - Destination weather: label="Weather at <city>", value="<temp>°C <condition>", icon="🌡"
       d. One flight_row block per flight from search_flights (all fields, including
          airline_initial = first letter of airline name)

  IMPORTANT: All values must come from the data tools — never invent prices,
  times, durations, or weather figures.

== DIAGRAMMING / DRAWING REQUESTS ==

When the user asks to draw, sketch, diagram, or visualise anything
(architecture, sequence diagrams, flowcharts, wireframes, mind maps, etc.):
  1. Call open_excalidraw with ALL THREE parameters set exactly as follows:
       mcp_server_url → ALWAYS the literal string "https://excalidraw.com"
       initial_prompt → a clear, specific instruction describing what to draw,
                        e.g. "Draw a sequence diagram showing the OAuth 2.0
                        login flow between browser, frontend, and auth server."
       title          → ALWAYS the literal string "Excalidraw"
  2. Do NOT call any data tools before open_excalidraw — the app is
     self-contained.
  After the tool call, confirm in one sentence what you asked Excalidraw to draw.

== CUSTOM / CREATIVE UI REQUESTS ==

When the user asks for an animation, game, calculator, visual effect, chart,
or any interactive interface that does NOT fit weather / flight / dashboard:
  1. Call generate_ui with:
       title        → short label, e.g. "Taco Rain" or "Bounce Simulator"
       html_content → a COMPLETE, self-contained HTML document. Rules:
                      - Start with <!DOCTYPE html><html>
                      - ALL CSS in <style> tags in <head>
                      - ALL JS in <script> tags in <body> — no external src
                      - NO external URLs (no CDN, no images via URL, no fonts)
                      - Use emoji for visual elements instead of images
                      - Use requestAnimationFrame for animation loops
                      - Remove DOM elements when they leave the viewport
                      - 100vw × 100vh viewport — fill it completely
                      - Visually complete immediately on load

  Be SPECIFIC and CREATIVE. A vague prompt produces a boring result.
  Include exact visual elements, colours, physics, and interactivity.

  Examples:
    "Make it rain tacos" →
      title="Taco Rain", html with 🌮 emoji falling at random angles,
      randomised sizes 1em–3em, requestAnimationFrame loop, DOM cleanup

    "Show a bouncing DVD logo" →
      title="DVD Bounce", html with a colourful "DVD" text bouncing off walls,
      colour changing on each wall hit, smooth rAF animation

    "Build a BPM tap tempo tool" →
      title="Tap Tempo", html with a large tap button, running BPM average,
      visual pulse that flashes on each tap

== GENERAL ==

After calling any UI display tool, follow up with one short sentence confirming
what was displayed. Keep all non-tool responses brief and conversational.
"""

# ---------------------------------------------------------------------------
# LangGraph agent
# ---------------------------------------------------------------------------

llm = ChatAnthropic(
    model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
    streaming=True,
)

agent = create_react_agent(
    llm,
    tools=[
        get_weather_data,
        show_weather,
        search_flights,
        show_flight_options,
        show_declarative_view,
        open_excalidraw,
        generate_ui,
    ],
    prompt=_SYSTEM_PROMPT,
    checkpointer=MemorySaver(),
)

# ---------------------------------------------------------------------------
# CopilotKit agent — LangGraphAGUIAgent wraps the compiled graph and handles
# all AG-UI event emission.  A fresh clone is created per request so that
# per-request state (active_run) is never shared across concurrent calls.
# ---------------------------------------------------------------------------

_travel_agent = LangGraphAGUIAgent(
    name="travel_agent",
    description=(
        "A travel assistant that shows real-time weather cards, "
        "flight option panels, and composable travel dashboards."
    ),
    graph=agent,
)

# ---------------------------------------------------------------------------
# Blazor compatibility endpoint
#
# The C# AgUiStreamService posts:
#   POST /api/agent/run
#   { "message": "...", "thread_id": "..." }
#
# We convert that to a RunAgentInput and call _travel_agent.run() directly —
# the same way add_langgraph_fastapi_endpoint works internally.
# No HTTP proxy, no extra round-trip.
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    message:   str
    thread_id: str = ""


@app.post("/api/agent/run")
async def run_agent(body: RunRequest) -> StreamingResponse:
    """Blazor-compatible endpoint: converts the simple request format to
    RunAgentInput and streams AG-UI SSE events back to the C# frontend."""

    run_input = RunAgentInput(
        thread_id=body.thread_id or str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        messages=[
            {
                "id":      str(uuid.uuid4()),
                "role":    "user",
                "content": body.message,
            }
        ],
        state={},
        tools=[],
        context=[],
        forwarded_props=None,
    )

    encoder       = EventEncoder(accept="text/event-stream")
    request_agent = _travel_agent.clone()

    async def event_generator() -> AsyncGenerator[str, None]:
        # ag_ui_langgraph streams TOOL_CALL_ARGS as multiple partial JSON deltas
        # (one per LLM token).  The C# AgentChat.razor calls JsonDocument.Parse()
        # on every delta, which throws on a partial fragment like {"location":"Dh…
        #
        # Fix: accumulate all partial deltas per tool_call_id, then emit ONE
        # complete TOOL_CALL_ARGS event just before TOOL_CALL_END.
        args_buffer: dict[str, str] = {}

        try:
            async for event in request_agent.run(run_input):
                t = event.type

                if t == EventType.TOOL_CALL_START:
                    args_buffer[event.tool_call_id] = ""
                    yield encoder.encode(event)

                elif t == EventType.TOOL_CALL_ARGS:
                    args_buffer.setdefault(event.tool_call_id, "")
                    args_buffer[event.tool_call_id] += event.delta or ""
                    # Hold — do not yield partial deltas

                elif t == EventType.TOOL_CALL_END:
                    accumulated = args_buffer.pop(event.tool_call_id, "")
                    if accumulated:
                        # Emit the fully-assembled args as one event
                        yield encoder.encode(ToolCallArgsEvent(
                            type=EventType.TOOL_CALL_ARGS,
                            tool_call_id=event.tool_call_id,
                            delta=accumulated,
                        ))
                    yield encoder.encode(event)

                else:
                    yield encoder.encode(event)

        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("Agent stream error: %s", exc)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/agent/schema")
async def schema() -> dict:
    """Expose the list of UI tool names so the Blazor frontend can validate
    its ComponentRegistry at startup.  Only UI tools are listed here —
    data tools are internal and invisible to Blazor."""
    return {"ui_tools": sorted(UI_TOOL_NAMES)}
