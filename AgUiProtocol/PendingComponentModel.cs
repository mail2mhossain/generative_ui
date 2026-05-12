using System.Text.Json;
using System.Text.Json.Serialization;

namespace AgUiProtocol;

/// <summary>
/// Represents a UI component whose JSON arguments are still arriving over the stream.
///
/// Lifecycle:
///   TOOL_CALL_START  → created (skeleton shown)
///   TOOL_CALL_ARGS   → <see cref="SetArgs"/> accumulates the JSON payload
///   TOOL_CALL_END    → <see cref="Hydrate"/> deserialises args; <see cref="IsReady"/> → true
///
/// Once ready, <see cref="Parameters"/> is passed directly to Blazor's DynamicComponent.
/// </summary>
public class PendingComponentModel
{
    // Python sends snake_case keys; C# params classes use PascalCase properties.
    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy        = JsonNamingPolicy.SnakeCaseLower,
        NumberHandling              = JsonNumberHandling.AllowReadingFromString,
    };

    public required ComponentRegistration Registration { get; init; }

    /// <summary>True after <see cref="Hydrate"/> successfully deserialises the args.</summary>
    public bool IsReady { get; private set; }

    /// <summary>Pixel height forwarded from <see cref="Registration"/> for skeleton sizing.</summary>
    public int ExpectedHeight => Registration.ExpectedHeight;

    /// <summary>The Blazor component type to render.</summary>
    public Type ComponentType => Registration.ComponentType;

    private JsonElement? _args;

    /// <summary>
    /// Stores the args JSON element received in a TOOL_CALL_ARGS event.
    /// Call <see cref="JsonElement.Clone"/> before passing so the element
    /// survives the enclosing JsonDocument's disposal.
    /// </summary>
    public void SetArgs(JsonElement? args) => _args = args;

    /// <summary>
    /// Deserialises the accumulated args into the registered parameters type
    /// and marks the component as ready to render.
    /// </summary>
    public void Hydrate()
    {
        if (_args is null) return;

        var raw       = _args.Value.GetRawText();
        var paramsObj = JsonSerializer.Deserialize(raw, Registration.ParametersType, _jsonOptions);
        if (paramsObj is null) return;

        // "Params" is the conventional [Parameter] name on all GenUI widget components.
        Parameters = new Dictionary<string, object?> { ["Params"] = paramsObj };
        IsReady    = true;
    }

    /// <summary>
    /// Ready to pass to <c>&lt;DynamicComponent Parameters="..."&gt;</c> after hydration.
    /// </summary>
    public IDictionary<string, object?>? Parameters { get; private set; }
}
