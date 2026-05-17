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
    SHOW_WEATHER        = "show_weather"
    SHOW_FLIGHT_OPTIONS = "show_flight_options"

    # ------------------------------------------------------------------
    # Data tools — internal; invisible to Blazor
    # ------------------------------------------------------------------
    GET_WEATHER_DATA = "get_weather_data"
    SEARCH_FLIGHTS   = "search_flights"

    @classmethod
    def all_ui_tools(cls) -> frozenset[str]:
        """Only UI tools.  Data tools are deliberately excluded."""
        return frozenset({cls.SHOW_WEATHER, cls.SHOW_FLIGHT_OPTIONS})
