using AgUiProtocol;
using Microsoft.AspNetCore.Components;
using Microsoft.JSInterop;

namespace BlazorAGUIDemo.Components.Widgets;

/// <summary>
/// Code-behind for <c>GeneratedUiFrame.razor</c>.
///
/// Manages the lifecycle of the double-sandboxed iframe that renders
/// agent-generated HTML (Pillar 3B).
///
/// <para><strong>Update detection:</strong> Blazor calls
/// <see cref="OnParametersSet"/> whenever the parent passes new
/// <c>[Parameter]</c> values.  We compare <see cref="GeneratedUiParams.HtmlContent"/>
/// against the previously injected value; only when it changes do we
/// set <c>_shouldInject = true</c> and schedule a JS call in the next
/// <see cref="OnAfterRenderAsync"/>.</para>
///
/// <para><strong>Lazy module load:</strong> <c>generatedUiBridge.js</c> is
/// imported on the first render that has content and cached for subsequent
/// content changes.  This avoids an import round-trip if the component is
/// mounted but the agent hasn't finished generating yet.</para>
/// </summary>
public partial class GeneratedUiFrame : IAsyncDisposable
{
    // -----------------------------------------------------------------------
    // References
    // -----------------------------------------------------------------------

    /// <summary>Reference to the container div that hosts the outer iframe.</summary>
    private ElementReference _container;

    private IJSObjectReference? _bridgeModule;

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    private string _injectedHtml  = string.Empty;
    private bool   _shouldInject  = false;

    // -----------------------------------------------------------------------
    // Lifecycle — parameter change detection
    // -----------------------------------------------------------------------

    protected override void OnParametersSet()
    {
        // Only re-inject when the generated HTML has actually changed.
        // Blazor may call OnParametersSet multiple times with identical values.
        if (Params.HtmlContent != _injectedHtml &&
            !string.IsNullOrEmpty(Params.HtmlContent))
        {
            _shouldInject = true;
        }
    }

    // -----------------------------------------------------------------------
    // Lifecycle — JS injection after DOM is ready
    // -----------------------------------------------------------------------

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if (!_shouldInject) return;
        _shouldInject = false;

        // Lazy-load the ES module once; reuse for content updates.
        _bridgeModule ??= await JS.InvokeAsync<IJSObjectReference>(
            "import", "./js/generatedUiBridge.js");

        await _bridgeModule.InvokeVoidAsync(
            "setContent", _container, Params.HtmlContent);

        // Record what we injected so we can detect genuine changes next time.
        _injectedHtml = Params.HtmlContent;
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
                await _bridgeModule.InvokeVoidAsync("dispose", _container);
                await _bridgeModule.DisposeAsync();
            }
            catch (JSDisconnectedException) { /* circuit already gone */ }
            catch (JSException)             { /* module already unloaded */ }
        }
    }
}
