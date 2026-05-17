namespace AgUiProtocol;

/// <summary>
/// Immutable descriptor for one block type → Blazor component binding.
/// Created by <see cref="BlockRegistry.Register{TComponent,TParams}"/>
/// and consumed by <c>DeclarativeRenderer</c> when hydrating each block.
/// </summary>
public record BlockRegistration
{
    /// <summary>The Blazor component to render for this block type.</summary>
    public required Type ComponentType { get; init; }

    /// <summary>
    /// The parameters class the block's JSON data is deserialised into.
    /// Must match the <c>Params</c> [Parameter] on <see cref="ComponentType"/>.
    /// </summary>
    public required Type ParametersType { get; init; }

    /// <summary>Block type string — matches the "type" field in the agent JSON.</summary>
    public required string BlockType { get; init; }
}
