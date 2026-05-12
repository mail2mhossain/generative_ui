using System.Text.Json.Serialization;

namespace BlazorAGUIDemo.Components.Widgets;

/// <summary>
/// Matches the parameters the LangGraph agent sends in UI_TOOL_CALL_ARGS
/// for the <c>show_weather</c> tool.  Snake-case JSON keys are handled by
/// the <see cref="System.Text.Json.JsonNamingPolicy.SnakeCaseLower"/> policy
/// set in <see cref="Services.PendingComponentModel"/>.
/// </summary>
public class WeatherCardParameters
{
    public string Location    { get; set; } = string.Empty;
    public double Temperature { get; set; }
    public string Condition   { get; set; } = string.Empty;
    public int    Humidity    { get; set; }
    public double WindSpeed   { get; set; }

    public string ConditionEmoji => Condition.ToLowerInvariant() switch
    {
        "sunny"         => "☀️",
        "cloudy"        => "☁️",
        "partly cloudy" => "⛅",
        "rainy"         => "🌧️",
        "stormy"        => "⛈️",
        "snowy"         => "❄️",
        "windy"         => "💨",
        _               => "🌡️",
    };
}
