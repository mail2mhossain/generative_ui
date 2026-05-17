namespace BlazorAGUIDemo.Components.Blocks;

/// <summary>
/// Parameters for the FlightRow declarative block.
/// Renders a single flight entry inside a declarative view.
/// Reuses the same CSS classes as the Pillar-1 FlightOptions widget rows.
/// </summary>
public class FlightRowParams
{
    public string  Airline       { get; set; } = string.Empty;
    public string  FlightNumber  { get; set; } = string.Empty;
    public string  DepartureTime { get; set; } = string.Empty;
    public string  ArrivalTime   { get; set; } = string.Empty;
    public string  Duration      { get; set; } = string.Empty;
    public decimal PriceGbp      { get; set; }

    /// <summary>First letter of the airline name — used for the badge.</summary>
    public string AirlineInitial => Airline.Length > 0 ? Airline[0].ToString() : "?";
}
