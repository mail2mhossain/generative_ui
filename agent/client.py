"""
AG-UI Python client for the demo agent.

Usage:
    python client.py                                              # interactive REPL
    python client.py "What's the weather in Paris?"              # single message
    python client.py --url http://localhost:8000 "Show flights from NYC to Tokyo"
    python client.py --thread abc123 "Any cheap morning options?"  # continue a thread
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Iterator

import httpx
from ag_ui.core import (
    BaseEvent,
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

# Map event type strings → Pydantic model classes for deserialisation.
_EVENT_MODELS: dict[str, type[BaseEvent]] = {
    "RUN_STARTED":           RunStartedEvent,
    "RUN_FINISHED":          RunFinishedEvent,
    "RUN_ERROR":             RunErrorEvent,
    "TEXT_MESSAGE_START":    TextMessageStartEvent,
    "TEXT_MESSAGE_CONTENT":  TextMessageContentEvent,
    "TEXT_MESSAGE_END":      TextMessageEndEvent,
    "TOOL_CALL_START":       ToolCallStartEvent,
    "TOOL_CALL_ARGS":        ToolCallArgsEvent,
    "TOOL_CALL_END":         ToolCallEndEvent,
}

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_R  = "\033[0m"
_B  = "\033[1m"       # bold
_D  = "\033[2m"       # dim
_CY = "\033[36m"      # cyan
_GR = "\033[32m"      # green
_YL = "\033[33m"      # yellow
_RD = "\033[31m"      # red
_BL = "\033[34m"      # blue


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_R}"


# ---------------------------------------------------------------------------
# SSE parser — yields typed ag_ui.core event objects
# ---------------------------------------------------------------------------


def _iter_sse(response: httpx.Response) -> Iterator[BaseEvent]:
    """Deserialise each SSE data line into a typed ag_ui.core event object."""
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        try:
            data        = json.loads(line[6:])
            model_class = _EVENT_MODELS.get(data.get("type", ""))
            if model_class:
                yield model_class.model_validate(data)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Component renderers
# ---------------------------------------------------------------------------


def _render_weather(args: dict) -> None:
    print()
    print(_c(_B + _CY, "┌─ WeatherCard " + "─" * 42))
    print(f"  📍  Location    : {_c(_B, str(args.get('location', '?')))}")
    print(f"  🌡   Temperature : {_c(_B, str(args.get('temperature', '?')))} °C")
    print(f"  ⛅  Condition   : {args.get('condition', '?')}")
    print(f"  💧  Humidity    : {args.get('humidity', '?')} %")
    print(f"  💨  Wind Speed  : {args.get('wind_speed', '?')} km/h")
    print(_c(_D, "└" + "─" * 56))
    print()


def _render_flights(args: dict) -> None:
    origin      = args.get("origin", "?")
    destination = args.get("destination", "?")
    date        = args.get("date", "?")
    flights     = args.get("flights", [])

    print()
    header = f"┌─ FlightOptions  {origin} → {destination}  ({date}) "
    print(_c(_B + _CY, header + "─" * max(0, 56 - len(header) + 2)))

    for i, f in enumerate(flights, 1):
        airline  = _c(_GR, f.get("airline", "?"))
        fnum     = _c(_D, f.get("flight_number", ""))
        dep      = f.get("departure_time", "?")
        arr      = f.get("arrival_time", "?")
        dur      = _c(_D, f"({f.get('duration', '?')})")
        price    = _c(_YL, f"£{f.get('price_gbp', '?')}")
        print(f"  {_c(_B, str(i))}.  {airline}  {fnum}  {dep} → {arr}  {dur}  {price}")

    print(_c(_D, "└" + "─" * 56))
    print()


_RENDERERS: dict[str, object] = {
    "show_weather":        _render_weather,
    "show_flight_options": _render_flights,
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class AgUiClient:
    """Synchronous AG-UI client that streams events from the demo agent."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout

    # ── health ───────────────────────────────────────────────────────────────

    def health(self) -> bool:
        """Return True if the agent is reachable and healthy."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=5.0)
            return r.status_code == 200 and r.json().get("status") == "ok"
        except Exception:
            return False

    # ── run ──────────────────────────────────────────────────────────────────

    def run(self, message: str, thread_id: str = "") -> None:
        """
        Send *message* to the agent and print the AG-UI event stream to stdout.

        Text tokens are printed as they arrive.
        UI components (WeatherCard, FlightOptions) are rendered inline.
        """
        if not thread_id:
            thread_id = str(uuid.uuid4())

        with httpx.stream(
            "POST",
            f"{self.base_url}/api/agent/run",
            json={"message": message, "thread_id": thread_id},
            timeout=self.timeout,
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            self._handle_stream(response)

    # ── internal stream handler ───────────────────────────────────────────────

    def _handle_stream(self, response: httpx.Response) -> None:
        pending_tool: str | None = None
        text_open = False

        for event in _iter_sse(response):

            if isinstance(event, RunStartedEvent):
                print(_c(_D, f"\n[run {event.run_id[:8]}… started]"))

            elif isinstance(event, TextMessageStartEvent):
                print(_c(_GR + _B, "\nAssistant: "), end="", flush=True)
                text_open = True

            elif isinstance(event, TextMessageContentEvent):
                print(event.delta, end="", flush=True)

            elif isinstance(event, TextMessageEndEvent):
                if text_open:
                    print()
                    text_open = False

            elif isinstance(event, ToolCallStartEvent):
                pending_tool = event.tool_call_name
                print(_c(_D, f"[rendering {pending_tool}…]"))

            elif isinstance(event, ToolCallArgsEvent):
                # delta is a JSON string — parse it back to a dict for the renderer
                try:
                    args = json.loads(event.delta)
                except json.JSONDecodeError:
                    args = {}
                renderer = _RENDERERS.get(pending_tool or "")
                if callable(renderer):
                    renderer(args)  # type: ignore[call-arg]
                else:
                    print(_c(_YL, f"\n[unknown component args]\n{json.dumps(args, indent=2)}"))

            elif isinstance(event, ToolCallEndEvent):
                pending_tool = None

            elif isinstance(event, RunFinishedEvent):
                print(_c(_D, f"[run {event.run_id[:8]}… finished]\n"))

            elif isinstance(event, RunErrorEvent):
                print(_c(_RD, f"\n[ERROR] {event.message}\n"))


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------


def _repl(client: AgUiClient) -> None:
    thread_id = str(uuid.uuid4())

    print(_c(_B, "AG-UI Demo Client"))
    print(_c(_D, f"Agent  : {client.base_url}"))
    print(_c(_D, f"Thread : {thread_id[:8]}…  (shared across the whole session)"))
    print(_c(_D, "Ctrl+C or Ctrl+D to exit\n"))
    print(_c(_D, "Try:"))
    print(_c(_D, "  • What's the weather in Tokyo?"))
    print(_c(_D, "  • Show me flights from London to New York\n"))

    while True:
        try:
            user_input = input(_c(_BL + _B, "You: ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(_c(_D, "\n[goodbye]"))
            break

        if not user_input:
            continue

        try:
            client.run(user_input, thread_id=thread_id)
        except httpx.ConnectError:
            print(_c(_RD, f"[connection refused — is the agent running at {client.base_url}?]"))
        except httpx.HTTPStatusError as exc:
            print(_c(_RD, f"[HTTP {exc.response.status_code}] {exc.response.text}"))
        except KeyboardInterrupt:
            print(_c(_D, "\n[interrupted — press Ctrl+D to quit]"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AG-UI Python client for the demo agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Message to send. Omit to start the interactive REPL.",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        metavar="URL",
        help="Agent base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--thread",
        default="",
        metavar="ID",
        help="Thread ID for multi-turn continuity (auto-generated if omitted)",
    )
    args = parser.parse_args()

    client = AgUiClient(base_url=args.url)

    if not client.health():
        print(_c(_RD, f"[warning] Agent not reachable at {args.url}/health"))
        if args.message:
            sys.exit(1)

    if args.message:
        try:
            client.run(args.message, thread_id=args.thread)
        except httpx.ConnectError:
            print(_c(_RD, f"[connection refused — is the agent running at {args.url}?]"))
            sys.exit(1)
        except httpx.HTTPStatusError as exc:
            print(_c(_RD, f"[HTTP {exc.response.status_code}] {exc.response.text}"))
            sys.exit(1)
    else:
        _repl(client)


if __name__ == "__main__":
    main()
