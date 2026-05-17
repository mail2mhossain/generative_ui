namespace BlazorAGUIDemo.Components.Blocks;

/// <summary>
/// Parameters for the SearchHeader declarative block.
/// Renders a route summary: Origin → Destination with a date pill.
/// </summary>
public class SearchHeaderParams
{
    /// <summary>Departure location or IATA code, e.g. "LHR" or "London".</summary>
    public string Origin { get; set; } = string.Empty;

    /// <summary>Arrival location or IATA code, e.g. "JFK" or "New York".</summary>
    public string Destination { get; set; } = string.Empty;

    /// <summary>Travel date string, e.g. "2025-05-23" or "Friday 23 May".</summary>
    public string Date { get; set; } = string.Empty;

    /// <summary>Optional sub-label, e.g. "1 adult · Economy".</summary>
    public string Label { get; set; } = string.Empty;
}
