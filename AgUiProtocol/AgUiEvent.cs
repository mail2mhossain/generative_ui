using System.Text.Json.Serialization;

namespace AgUiProtocol;

// ---------------------------------------------------------------------------
// AG-UI event type discriminator — mirrors the "type" string on the wire
// ---------------------------------------------------------------------------

public enum AgUiEventType
{
    Unknown,
    RunStarted,
    TextMessageStart,
    TextMessageContent,
    TextMessageEnd,
    ToolCallStart,
    ToolCallArgs,
    ToolCallEnd,
    StateDelta,
    RunFinished,
    RunError,
}

// ---------------------------------------------------------------------------
// Raw event envelope — deserialised from each SSE "data: {...}" line
// ---------------------------------------------------------------------------

public class AgUiEvent
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    // The Python ag-ui-protocol SDK serialises these fields in camelCase JSON.
    [JsonPropertyName("runId")]
    public string? RunId { get; set; }

    [JsonPropertyName("messageId")]
    public string? MessageId { get; set; }

    /// <summary>
    /// Incremental token for TEXT_MESSAGE_CONTENT events,
    /// or a JSON string payload for TOOL_CALL_ARGS events.
    /// </summary>
    [JsonPropertyName("delta")]
    public string? Delta { get; set; }

    [JsonPropertyName("toolCallId")]
    public string? ToolCallId { get; set; }

    [JsonPropertyName("toolCallName")]
    public string? ToolCallName { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    /// <summary>Strongly-typed discriminator derived from the raw <see cref="Type"/> string.</summary>
    public AgUiEventType EventType => Type switch
    {
        "RUN_STARTED"          => AgUiEventType.RunStarted,
        "TEXT_MESSAGE_START"   => AgUiEventType.TextMessageStart,
        "TEXT_MESSAGE_CONTENT" => AgUiEventType.TextMessageContent,
        "TEXT_MESSAGE_END"     => AgUiEventType.TextMessageEnd,
        "TOOL_CALL_START"      => AgUiEventType.ToolCallStart,
        "TOOL_CALL_ARGS"       => AgUiEventType.ToolCallArgs,
        "TOOL_CALL_END"        => AgUiEventType.ToolCallEnd,
        "STATE_DELTA"          => AgUiEventType.StateDelta,
        "RUN_FINISHED"         => AgUiEventType.RunFinished,
        "RUN_ERROR"            => AgUiEventType.RunError,
        _                      => AgUiEventType.Unknown,
    };
}
