using System.Text.Json;
using System.Text.Json.Serialization;

namespace AgUiProtocol;

/// <summary>
/// A single building block in a Pillar-2 declarative layout.
///
/// The <see cref="Type"/> field selects the Blazor component from
/// <see cref="BlockRegistry"/>.  All remaining JSON fields (label, value,
/// icon, airline, …) land in <see cref="Data"/> via <see cref="JsonExtensionDataAttribute"/>
/// and are later deserialised into the block's registered parameters type
/// by <see cref="BlockRegistry.Hydrate"/>.
///
/// Wire format (one element of the "blocks" array):
/// <code>
/// { "type": "metric_card", "label": "Temperature", "value": "32°C", "icon": "🌡️" }
/// </code>
/// </summary>
public class DeclarativeBlock
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    /// <summary>
    /// All JSON fields beyond <c>"type"</c>.  Captured here and later
    /// deserialised into the block component's params type by
    /// <see cref="BlockRegistry.Hydrate"/>.
    /// </summary>
    [JsonExtensionData]
    public Dictionary<string, JsonElement>? Data { get; set; }
}

/// <summary>
/// The full declarative layout schema sent by the agent as TOOL_CALL_ARGS
/// for the <c>show_declarative_view</c> tool.
///
/// Wire format:
/// <code>
/// {
///   "title": "Travel Dashboard",
///   "blocks": [
///     { "type": "page_title",    "text": "Dhaka Weather" },
///     { "type": "metric_card",   "label": "Temperature", "value": "32°C", "icon": "🌡️" },
///     { "type": "metric_card",   "label": "Humidity",    "value": "75%",  "icon": "💧" },
///     { "type": "search_header", "origin": "LHR", "destination": "JFK", "date": "2025-05-23" },
///     { "type": "flight_row",    "airline": "British Airways", ... }
///   ]
/// }
/// </code>
/// </summary>
public class DeclarativeSchema
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("blocks")]
    public List<DeclarativeBlock> Blocks { get; set; } = new();
}
