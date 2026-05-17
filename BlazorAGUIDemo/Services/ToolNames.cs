namespace BlazorAGUIDemo.Services;

/// <summary>
/// Single source of truth for AG-UI tool name strings on the C# side.
///
/// These constants must be kept in sync with ToolNames in the Python agent
/// (tool_names.py). Any change here must be mirrored there, and vice versa.
/// </summary>
public static class ToolNames
{
    public const string ShowWeather         = "show_weather";
    public const string ShowFlightOptions   = "show_flight_options";
    public const string ShowDeclarativeView = "show_declarative_view";

    // Pillar 3A — MCP Apps
    public const string OpenExcalidraw      = "open_excalidraw";
}
