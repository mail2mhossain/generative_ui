using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace AgUiProtocol;

// ---------------------------------------------------------------------------
// Manifest types
// ---------------------------------------------------------------------------

/// <summary>
/// Full manifest returned by <c>GET {mcpServerUrl}/.well-known/mcp-apps</c>.
///
/// Minimal wire format (additional fields are ignored):
/// <code>
/// {
///   "app_url":     "https://mcp.excalidraw.com/app",
///   "name":        "Excalidraw",
///   "capabilities": ["draw", "export"]
/// }
/// </code>
/// </summary>
public class McpAppManifest
{
    /// <summary>The URL to load inside the sandboxed iframe.</summary>
    [JsonPropertyName("app_url")]
    public string AppUrl { get; set; } = string.Empty;

    /// <summary>Human-readable app name from the manifest.</summary>
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    /// <summary>Optional list of capability tokens the app advertises.</summary>
    [JsonPropertyName("capabilities")]
    public List<string> Capabilities { get; set; } = new();
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

/// <summary>
/// Fetches and caches MCP app manifests.
///
/// Register as a scoped service in <c>Program.cs</c>:
/// <code>
/// builder.Services.AddHttpClient&lt;McpManifestService&gt;();
/// </code>
///
/// Each Blazor Server circuit (scoped) gets its own instance, so the
/// in-process <see cref="_cache"/> is per-circuit — fine for demo use.
/// For production, promote the cache to a singleton memory cache.
/// </summary>
public class McpManifestService
{
    private readonly HttpClient _http;
    private readonly Dictionary<string, McpAppManifest> _cache = new();

    public McpManifestService(HttpClient http) => _http = http;

    /// <summary>
    /// Fetches the manifest from <c>{mcpServerUrl}/.well-known/mcp-apps</c>.
    ///
    /// Results are cached for the lifetime of this service instance.
    /// On HTTP or JSON failure, throws <see cref="McpManifestException"/>.
    /// </summary>
    /// <param name="mcpServerUrl">Base URL of the MCP server, e.g. <c>https://mcp.excalidraw.com</c>.</param>
    /// <param name="cancellationToken">Optional cancellation token.</param>
    public async Task<McpAppManifest> FetchAsync(
        string mcpServerUrl,
        CancellationToken cancellationToken = default)
    {
        if (_cache.TryGetValue(mcpServerUrl, out var cached))
            return cached;

        var manifestUrl = mcpServerUrl.TrimEnd('/') + "/.well-known/mcp-apps";

        McpAppManifest? manifest;
        try
        {
            manifest = await _http.GetFromJsonAsync<McpAppManifest>(
                manifestUrl, cancellationToken);
        }
        catch (HttpRequestException ex)
        {
            throw new McpManifestException(
                $"Could not reach MCP server at {manifestUrl}: {ex.Message}", ex);
        }
        catch (Exception ex)
        {
            throw new McpManifestException(
                $"Failed to parse manifest from {manifestUrl}: {ex.Message}", ex);
        }

        if (manifest is null || string.IsNullOrWhiteSpace(manifest.AppUrl))
            throw new McpManifestException(
                $"Manifest from {manifestUrl} is missing a valid 'app_url'.");

        _cache[mcpServerUrl] = manifest;
        return manifest;
    }
}

// ---------------------------------------------------------------------------
// Exception
// ---------------------------------------------------------------------------

/// <summary>
/// Thrown by <see cref="McpManifestService.FetchAsync"/> when the manifest
/// cannot be retrieved or is structurally invalid.
/// </summary>
public class McpManifestException : Exception
{
    public McpManifestException(string message)
        : base(message) { }

    public McpManifestException(string message, Exception inner)
        : base(message, inner) { }
}
