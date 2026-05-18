"""
Single source of truth for AG-UI tool name strings on the Python side.

UI tools  — registered in the Blazor ComponentRegistry; CopilotKit emits
            TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END for these.
            Must match ToolNames.cs in the AgUiProtocol project exactly.

Data tools — internal only; they fetch real data and return it to the LLM
             as context.  They are never registered in Blazor and must NOT
             appear in all_ui_tools().
"""


class ToolNames:
    # ------------------------------------------------------------------
    # UI tools — must match Blazor ComponentRegistry exactly
    # ------------------------------------------------------------------
    SHOW_WEATHER          = "show_weather"
    SHOW_FLIGHT_OPTIONS   = "show_flight_options"
    SHOW_DECLARATIVE_VIEW = "show_declarative_view"

    # Pillar 3A — MCP Apps
    OPEN_EXCALIDRAW       = "open_excalidraw"

    # Pillar 3B — Fully Open-Ended Generative UI
    GENERATE_UI           = "generate_ui"

    # ------------------------------------------------------------------
    # Data tools — internal; invisible to Blazor
    # ------------------------------------------------------------------
    GET_WEATHER_DATA = "get_weather_data"
    SEARCH_FLIGHTS   = "search_flights"

    @classmethod
    def all_ui_tools(cls) -> frozenset[str]:
        """Only UI tools.  Data tools are deliberately excluded."""
        return frozenset({
            cls.SHOW_WEATHER,
            cls.SHOW_FLIGHT_OPTIONS,
            cls.SHOW_DECLARATIVE_VIEW,
            cls.OPEN_EXCALIDRAW,
            cls.GENERATE_UI,
        })
