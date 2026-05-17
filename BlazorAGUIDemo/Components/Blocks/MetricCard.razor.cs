namespace BlazorAGUIDemo.Components.Blocks;

/// <summary>
/// Parameters for the MetricCard declarative block.
/// Matches the JSON the agent sends in a "metric_card" block entry.
/// </summary>
public class MetricCardParams
{
    /// <summary>Short label shown below the value, e.g. "Temperature".</summary>
    public string Label { get; set; } = string.Empty;

    /// <summary>Formatted value string, e.g. "32°C" or "75%".</summary>
    public string Value { get; set; } = string.Empty;

    /// <summary>Optional emoji icon, e.g. "🌡️" or "💧".</summary>
    public string Icon { get; set; } = string.Empty;

    /// <summary>Optional trend direction: "up", "down", or empty for neutral.</summary>
    public string Trend { get; set; } = string.Empty;

    public string TrendArrow => Trend.ToLowerInvariant() switch
    {
        "up"   => "↑",
        "down" => "↓",
        _      => string.Empty,
    };

    public string TrendCssClass => Trend.ToLowerInvariant() switch
    {
        "up"   => "metric-card__trend--up",
        "down" => "metric-card__trend--down",
        _      => string.Empty,
    };
}
