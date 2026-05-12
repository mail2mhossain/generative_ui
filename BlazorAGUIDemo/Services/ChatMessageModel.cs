using AgUiProtocol;

namespace BlazorAGUIDemo.Services;

/// <summary>
/// A single entry in the chat history — either plain text or an agent-rendered component.
/// This is a UI-layer model; it does not belong in the protocol library.
/// </summary>
public class ChatMessageModel
{
    public string? Content { get; init; }
    public bool IsUser { get; init; }
    public bool IsError { get; init; }
    public bool IsStreaming { get; init; }

    /// <summary>Non-null when the message is an agent-rendered UI component.</summary>
    public PendingComponentModel? Component { get; init; }

    public bool IsComponent => Component is not null;

    public static ChatMessageModel Text(string content, bool isUser = false, bool isError = false) =>
        new() { Content = content, IsUser = isUser, IsError = isError };

    public static ChatMessageModel FromComponent(PendingComponentModel component) =>
        new() { Component = component };
}
