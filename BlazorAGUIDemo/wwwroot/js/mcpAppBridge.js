/**
 * mcpAppBridge.js — Pillar 3A: MCP App postMessage bridge
 *
 * Called from McpAppFrame.razor.cs via IJSRuntime.InvokeVoidAsync.
 *
 * Responsibilities:
 *   1. initBridge(iframeId, appOrigin, dotNetRef)
 *      - Listens for "message" events from the iframe.
 *      - Forwards structured JSON-RPC notifications from the app to Blazor
 *        via dotNetRef.invokeMethodAsync("OnMcpMessage", payload).
 *
 *   2. sendPrompt(iframeId, appOrigin, prompt)
 *      - Posts a { method: "mcp.prompt", params: { text } } JSON-RPC
 *        notification into the iframe so the app can act on the initial
 *        prompt from the agent.
 *
 * Security model:
 *   - All postMessage calls use an explicit targetOrigin (appOrigin) —
 *     never "*".
 *   - Incoming messages are validated: wrong origin or non-object payloads
 *     are silently dropped.
 *   - The iframe sandbox attribute (set in markup) restricts capabilities:
 *       allow-scripts allow-same-origin allow-forms
 */

// Registry: iframeId → { listener, dotNetRef }
const _bridges = new Map();

/**
 * Initialise the bridge for a given iframe.
 *
 * @param {string} iframeId   - The HTML id attribute of the iframe element.
 * @param {string} appOrigin  - The expected origin of the MCP app, e.g.
 *                              "https://mcp.excalidraw.com".
 * @param {object} dotNetRef  - A DotNetObjectReference<McpAppFrame> for
 *                              invoking [JSInvokable] methods back in Blazor.
 */
export function initBridge(iframeId, appOrigin, dotNetRef) {
    // Clean up any previous listener for this iframe
    disposeBridge(iframeId);

    const listener = (event) => {
        // Drop messages from unexpected origins
        if (event.origin !== appOrigin) return;

        const data = event.data;
        if (typeof data !== 'object' || data === null) return;

        // Forward to Blazor — fire-and-forget; errors are swallowed so a
        // misbehaving app cannot break the Blazor circuit.
        dotNetRef.invokeMethodAsync('OnMcpMessage', JSON.stringify(data))
            .catch(err => console.warn('[mcpAppBridge] Blazor callback failed:', err));
    };

    window.addEventListener('message', listener);
    _bridges.set(iframeId, { listener, dotNetRef });
}

/**
 * Send the initial-prompt JSON-RPC notification to the app inside the iframe.
 *
 * @param {string} iframeId  - The HTML id of the target iframe.
 * @param {string} appOrigin - Must match the iframe's origin exactly.
 * @param {string} prompt    - The natural-language prompt text.
 */
export function sendPrompt(iframeId, appOrigin, prompt) {
    const iframe = document.getElementById(iframeId);
    if (!iframe || !iframe.contentWindow) {
        console.warn('[mcpAppBridge] iframe not found:', iframeId);
        return;
    }

    const message = {
        jsonrpc: '2.0',
        method:  'mcp.prompt',
        params:  { text: prompt },
    };

    iframe.contentWindow.postMessage(message, appOrigin);
}

/**
 * Remove the message listener and DotNet reference for a given iframe.
 * Called from McpAppFrame.razor.cs IAsyncDisposable.DisposeAsync().
 *
 * @param {string} iframeId
 */
export function disposeBridge(iframeId) {
    const bridge = _bridges.get(iframeId);
    if (!bridge) return;

    window.removeEventListener('message', bridge.listener);

    // Release the DotNet reference to avoid memory leaks on the Blazor side
    try { bridge.dotNetRef.dispose(); } catch (_) { /* already disposed */ }

    _bridges.delete(iframeId);
}
