namespace AgUiProtocol;

/// <summary>
/// Immutable descriptor for one AG-UI tool → Blazor component binding.
/// Created by <see cref="ComponentRegistry.Register{TComponent,TParams}"/>
/// and consumed by <see cref="PendingComponentModel"/> at hydration time.
/// </summary>
public record ComponentRegistration
{
    /// <summary>The Blazor component type to render when this tool fires.</summary>
    public required Type ComponentType { get; init; }

    /// <summary>
    /// The strongly-typed parameters class that <see cref="PendingComponentModel"/>
    /// deserialises the tool's JSON args into.
    /// Must match the <c>Params</c> parameter on <see cref="ComponentType"/>.
    /// </summary>
    public required Type ParametersType { get; init; }

    /// <summary>AG-UI tool name string — must match the Python agent exactly.</summary>
    public required string ToolName { get; init; }

    /// <summary>Human-readable description (shown in documentation / dev tooling).</summary>
    public required string Description { get; init; }

    /// <summary>Pre-filled prompt surfaced as a suggestion chip in the chat UI.</summary>
    public required string SuggestedPrompt { get; init; }

    /// <summary>
    /// Pixel height reserved by the skeleton placeholder while the component
    /// streams in. Prevents Cumulative Layout Shift (CLS).
    /// </summary>
    public int ExpectedHeight { get; init; } = 200;
}
