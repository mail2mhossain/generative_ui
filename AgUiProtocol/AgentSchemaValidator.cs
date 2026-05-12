using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace AgUiProtocol;

/// <summary>
/// Validates at startup that every tool name in <see cref="ComponentRegistry"/>
/// is also present in the agent's /api/agent/schema response.
///
/// Fail-fast strategy: throws <see cref="InvalidOperationException"/> on any
/// mismatch so the host refuses to start — the misconfiguration is visible
/// immediately rather than silently failing at runtime when a user triggers
/// the missing tool.
///
/// If the agent is unreachable (e.g. not yet started), validation is skipped
/// with a warning so local development isn't blocked.
/// </summary>
public static class AgentSchemaValidator
{
    public static async Task ValidateAsync(
        ComponentRegistry registry,
        HttpClient        http,
        ILogger           logger,
        CancellationToken ct = default)
    {
        IReadOnlyList<string> agentTools;

        try
        {
            var response = await http.GetAsync("/api/agent/schema", ct);
            response.EnsureSuccessStatusCode();

            var body = await response.Content.ReadAsStringAsync(ct);
            var doc  = JsonDocument.Parse(body);

            agentTools = doc.RootElement
                            .GetProperty("ui_tools")
                            .EnumerateArray()
                            .Select(e => e.GetString() ?? string.Empty)
                            .ToList();
        }
        catch (Exception ex)
        {
            logger.LogWarning(
                "Could not reach agent schema endpoint — skipping tool name validation. ({Message})",
                ex.Message);
            return;
        }

        var agentSet   = agentTools.ToHashSet(StringComparer.Ordinal);
        var registered = registry.GetAll().Select(r => r.ToolName).ToList();
        var mismatches = registered.Where(name => !agentSet.Contains(name)).ToList();

        if (mismatches.Count == 0)
        {
            logger.LogInformation(
                "AG-UI tool name validation passed — all {Count} registered tools found in agent schema.",
                registered.Count);
            return;
        }

        foreach (var name in mismatches)
        {
            logger.LogError(
                "Tool name mismatch: '{ToolName}' is registered in ComponentRegistry " +
                "but NOT found in agent schema [{AgentTools}]. " +
                "The component will never render. " +
                "Ensure ToolNames.cs and tool_names.py are in sync.",
                name,
                string.Join(", ", agentTools));
        }

        throw new InvalidOperationException(
            $"AG-UI tool name mismatch for: {string.Join(", ", mismatches)}. " +
            "Ensure ToolNames.cs and tool_names.py are in sync.");
    }
}
