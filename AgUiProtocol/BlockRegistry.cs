using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Components;

namespace AgUiProtocol;

/// <summary>
/// Developer-owned singleton that maps block type strings to Blazor components.
///
/// Register every block type the agent may emit in Program.cs.
/// The registry is consumed by <c>DeclarativeRenderer</c> to resolve and
/// hydrate each block at render time.
///
/// Usage (Program.cs):
/// <code>
/// builder.Services.AddSingleton&lt;BlockRegistry&gt;(sp =>
/// {
///     var r = new BlockRegistry();
///     r.Register&lt;MetricCard, MetricCardParams&gt;("metric_card");
///     r.Register&lt;PageTitle,  PageTitleParams&gt; ("page_title");
///     r.Register&lt;SearchHeader, SearchHeaderParams&gt;("search_header");
///     r.Register&lt;FlightRow,  FlightRowParams&gt; ("flight_row");
///     return r;
/// });
/// </code>
/// </summary>
public class BlockRegistry
{
    private static readonly JsonSerializerOptions _opts = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy        = JsonNamingPolicy.SnakeCaseLower,
        NumberHandling              = JsonNumberHandling.AllowReadingFromString,
    };

    private readonly Dictionary<string, BlockRegistration> _map = new();

    /// <summary>
    /// Binds a block type string to a Blazor component.
    ///
    /// <typeparamref name="TComponent"/> must expose a single
    /// <c>[Parameter] TParams Params { get; set; }</c> property.
    /// </summary>
    public void Register<TComponent, TParams>(string blockType)
        where TComponent : ComponentBase
        where TParams    : class, new()
    {
        _map[blockType] = new BlockRegistration
        {
            ComponentType  = typeof(TComponent),
            ParametersType = typeof(TParams),
            BlockType      = blockType,
        };
    }

    /// <summary>Returns the registration for <paramref name="blockType"/>, or null if unknown.</summary>
    public BlockRegistration? GetRegistration(string blockType) =>
        _map.TryGetValue(blockType, out var reg) ? reg : null;

    /// <summary>Returns all registered block types.</summary>
    public IEnumerable<BlockRegistration> GetAll() => _map.Values;

    /// <summary>
    /// Deserialises a <see cref="DeclarativeBlock"/>'s extension data into the
    /// block's registered parameters type.  Returns null on any failure.
    /// </summary>
    public object? Hydrate(DeclarativeBlock block, BlockRegistration reg)
    {
        try
        {
            // Re-serialise the extension-data dictionary (all non-type fields)
            // to a JSON string, then deserialise into the target params type.
            // Keys stay as-is (snake_case from Python); SnakeCaseLower maps them
            // to PascalCase C# properties on deserialization.
            var json = JsonSerializer.Serialize(block.Data ?? new Dictionary<string, JsonElement>(), _opts);
            return JsonSerializer.Deserialize(json, reg.ParametersType, _opts);
        }
        catch
        {
            return null;
        }
    }
}
