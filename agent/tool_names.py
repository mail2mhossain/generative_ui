"""
Single source of truth for AG-UI tool name strings on the Python side.

Every tool name used in @tool definitions, UI_TOOL_NAMES, and
_DEFERRED_ARG_TOOLS must be imported from here — never written as a
bare string literal anywhere else.
"""


class ToolNames:
    SHOW_WEATHER        = "show_weather"
    SHOW_FLIGHT_OPTIONS = "show_flight_options"

    @classmethod
    def all_ui_tools(cls) -> frozenset[str]:
        return frozenset({cls.SHOW_WEATHER, cls.SHOW_FLIGHT_OPTIONS})
