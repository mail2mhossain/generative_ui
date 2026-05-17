using AgUiProtocol;
using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;

namespace BlazorAGUIDemo.Components.Widgets;

/// <summary>
/// Code-behind for <c>McpAppFrame.razor</c>.
///
/// Manages the three-phase lifecycle of a sandboxed MCP App:
///
/// <list type="number">
///   <item>
///     <term>Manifest fetch</term>
///     <description>
///       <see cref="OnParametersSetAsync"/> calls
///       <see cref="McpManifestService.FetchAsync"/> to resolve the actual
///       iframe URL from <c>{McpServerUrl}/.well-known/mcp-apps</c>.
///     </description>
///   </item>
///   <item>
///     <term>Bridge init + prompt</term>
///     <description>
///       <see cref="OnAfterRenderAsync"/> waits for the first render after
///       the manifest arrives, then calls <c>mcpAppBridge.js:initBridge</c>
///       and <c>mcpAppBridge.js:sendPrompt</c> via <see cref="IJSRuntime"/>.
///     </description>
///   </item>
///   <item>
///     <term>Cleanup</term>
///     <description>
///       <see cref="DisposeAsync"/> calls <c>mcpAppBridge.js:disposeBridge</c>
///       to remove the <c>window.message</c> listener and dispose the
///       <see cref="DotNetObjectReference{T}"/>.
///     </description>
///   </item>
/// </list>
/// </summary>
public partial class McpAppFrame : IAsyncDisposable
{
    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    private bool    _loading      = true;
    private string? _error        = null;
    private string  _appUrl       = string.Empty;
    private string  _appOrigin    = string.Empty;
    private string  _displayTitle = string.Empty;

    /// <summary>Stable element id used to locate the iframe in the DOM.</summary>
    private readonly string _iframeId = $"mcp-app-{Guid.NewGuid():N}";

    private bool                              _bridgeReady = false;
    private IJSObjectReference?               _bridgeModule;
    private DotNetObjectReference<McpAppFrame>? _selfRef;

    // -----------------------------------------------------------------------
    // Lifecycle — manifest fetch
    // -----------------------------------------------------------------------

    protected override async Task OnParametersSetAsync()
    {
        // Re-fetch whenever the MCP server URL changes (e.g. a new tool call)
        if (string.IsNullOrWhiteSpace(Params.McpServerUrl))
        {
            _error   = "No MCP server URL provided.";
            _loading = false;
            return;
        }

        _loading      = true;
        _error        = null;
        _bridgeReady  = false;
        _displayTitle = Params.Title;

        StateHasChanged();

        try
        {
            var manifest = await ManifestService.FetchAsync(Params.McpServerUrl);

            _appUrl    = manifest.AppUrl;
            _appOrigin = new Uri(_appUrl).GetLeftPart(UriPartial.Authority);

            // Fall back to manifest name if the agent did not supply a title
            if (string.IsNullOrWhiteSpace(_displayTitle))
                _displayTitle = manifest.Name;
        }
        catch (McpManifestException)
        {
            // Graceful degradation: the server doesn't expose a manifest yet.
            // Use McpServerUrl directly as the iframe src.  The postMessage
            // bridge will still initialise — mcp.prompt will be sent, but
            // the app may silently ignore it if it doesn't handle that method.
            _appUrl    = Params.McpServerUrl;
            _appOrigin = new Uri(_appUrl).GetLeftPart(UriPartial.Authority);
        }
        catch (Exception ex)
        {
            _error   = $"Unexpected error loading app: {ex.Message}";
            _loading = false;
            return;
        }

        _loading = false;
    }

    // -----------------------------------------------------------------------
    // Lifecycle — JS bridge init (runs after first render with the iframe)
    // -----------------------------------------------------------------------

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        // Only wire up the bridge once, and only when we have a valid app URL
        if (_bridgeReady || _loading || _error is not null || string.IsNullOrEmpty(_appUrl))
            return;

        _bridgeReady = true;

        try
        {
            _bridgeModule = await JS.InvokeAsync<IJSObjectReference>(
                "import", "./js/mcpAppBridge.js");

            _selfRef = DotNetObjectReference.Create(this);

            await _bridgeModule.InvokeVoidAsync(
                "initBridge", _iframeId, _appOrigin, _selfRef);

            // Send the initial prompt once the bridge is listening
            if (!string.IsNullOrWhiteSpace(Params.InitialPrompt))
            {
                await _bridgeModule.InvokeVoidAsync(
                    "sendPrompt", _iframeId, _appOrigin, Params.InitialPrompt);
            }
        }
        catch (JSException ex)
        {
            // Non-fatal — app still renders; prompt just won't be forwarded
            Console.Error.WriteLine($"[McpAppFrame] JS bridge error: {ex.Message}");
        }
    }

    // -----------------------------------------------------------------------
    // JS-invokable — receives JSON-RPC notifications from the MCP app
    // -----------------------------------------------------------------------

    /// <summary>
    /// Called by <c>mcpAppBridge.js</c> when the app posts a message.
    /// <paramref name="payloadJson"/> is the full JSON-RPC object as a string.
    /// </summary>
    [JSInvokable]
    public Task OnMcpMessage(string payloadJson)
    {
        // Currently we just log — future iterations can parse and act on
        // specific methods (e.g. "mcp.exportSvg", "mcp.ready").
        Console.WriteLine($"[McpAppFrame] Message from app: {payloadJson}");
        return Task.CompletedTask;
    }

    // -----------------------------------------------------------------------
    // Cleanup
    // -----------------------------------------------------------------------

    public async ValueTask DisposeAsync()
    {
        if (_bridgeModule is not null)
        {
            try
            {
                await _bridgeModule.InvokeVoidAsync("disposeBridge", _iframeId);
                await _bridgeModule.DisposeAsync();
            }
            catch (JSDisconnectedException) { /* circuit already gone */ }
            catch (JSException) { /* module already unloaded */ }
        }

        _selfRef?.Dispose();
    }
}
