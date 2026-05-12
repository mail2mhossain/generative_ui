using Microsoft.AspNetCore.Components;

namespace AgUiProtocol;

/// <summary>
/// Developer-owned singleton that maps AG-UI tool names to Blazor components.
///
/// Register every tool the agent can emit in Program.cs.
/// The registry is then used by two consumers:
///   1. The chat UI — to render suggestion chips
///   2. <see cref="PendingComponentModel"/> — to hydrate incoming tool calls
///
/// Usage (Program.cs):
/// <code>
/// builder.Services.AddSingleton&lt;ComponentRegistry&gt;(sp =>
/// {
///     var r = new ComponentRegistry();
///     r.Register&lt;WeatherCard, WeatherCardParameters&gt;(
///         toolName:        ToolNames.ShowWeather,
///         description:     "Current weather conditions for any city.",
///         suggestedPrompt: "What's the weather like in Tokyo?",
///         expectedHeight:  220);
///     return r;
/// });
/// </code>
/// </summary>
public class ComponentRegistry
{
    private readonly Dictionary<string, ComponentRegistration> _map = new();

    /// <summary>
    /// Binds an AG-UI tool name to a Blazor component.
    ///
    /// <typeparamref name="TComponent"/> must expose a single
    /// <c>[Parameter] TParams Params { get; set; }</c> property.
    /// </summary>
    public void Register<TComponent, TParams>(
        string toolName,
        string description,
        string suggestedPrompt,
        int    expectedHeight = 200)
        where TComponent : ComponentBase
        where TParams    : class, new()
    {
        _map[toolName] = new ComponentRegistration
        {
            ComponentType   = typeof(TComponent),
            ParametersType  = typeof(TParams),
            ToolName        = toolName,
            Description     = description,
            SuggestedPrompt = suggestedPrompt,
            ExpectedHeight  = expectedHeight,
        };
    }

    /// <summary>Returns the registration for <paramref name="toolName"/>, or null if not registered.</summary>
    public ComponentRegistration? GetRegistration(string toolName) =>
        _map.TryGetValue(toolName, out var reg) ? reg : null;

    /// <summary>Returns all registered components (used for suggestion chips).</summary>
    public IEnumerable<ComponentRegistration> GetAll() => _map.Values;
}
