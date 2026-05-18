using System.Text.Json.Serialization;

namespace AgUiProtocol;

/// <summary>
/// Parameters deserialized from the agent's TOOL_CALL_ARGS for the
/// <c>open_excalidraw</c> tool (and any future MCP App tool).
///
/// Wire format sent by the Python agent:
/// <code>
/// {
///   "mcp_server_url":  "https://mcp.excalidraw.com",
///   "initial_prompt":  "Draw a sequence diagram for the login flow",
///   "title":           "Excalidraw"
/// }
/// </code>
///
/// <c>McpAppFrame</c> receives this as its <c>Params</c> parameter and uses
/// <c>McpServerUrl</c> to fetch the app manifest before rendering the iframe.
/// </summary>
public class McpAppParams
{
    /// <summary>
    /// Base URL of the MCP server that hosts the app.
    /// The manifest is fetched from <c>{McpServerUrl}/.well-known/mcp-apps</c>.
    /// </summary>
    [JsonPropertyName("mcp_server_url")]
    public string McpServerUrl { get; set; } = string.Empty;

    /// <summary>
    /// Natural-language prompt forwarded to the app after it loads.
    /// Sent via the JS bridge as a <c>mcp.prompt</c> JSON-RPC notification.
    /// </summary>
    [JsonPropertyName("initial_prompt")]
    public string InitialPrompt { get; set; } = string.Empty;

    /// <summary>
    /// Display name shown in the widget title bar.
    /// Falls back to the app's <c>name</c> from the manifest when empty.
    /// </summary>
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;
}
