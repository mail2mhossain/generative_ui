namespace BlazorAGUIDemo.Components.Widgets;

/// <summary>
/// Matches the parameters the LangGraph agent sends for the
/// <c>show_flight_options</c> tool.  The nested <see cref="FlightOption"/> list
/// uses snake_case JSON keys handled by the SnakeCaseLower naming policy.
/// </summary>
public class FlightOptionsParameters
{
    public string             Origin      { get; set; } = string.Empty;
    public string             Destination { get; set; } = string.Empty;
    public string             Date        { get; set; } = string.Empty;
    public List<FlightOption> Flights     { get; set; } = new();
}

public class FlightOption
{
    public string  Airline       { get; set; } = string.Empty;
    public string  FlightNumber  { get; set; } = string.Empty;
    public string  DepartureTime { get; set; } = string.Empty;
    public string  ArrivalTime   { get; set; } = string.Empty;
    public decimal PriceGbp      { get; set; }
    public string  Duration      { get; set; } = string.Empty;

    public string AirlineInitial => Airline.Length > 0 ? Airline[0].ToString() : "?";
}
