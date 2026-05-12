using System.Net.Http.Json;
using System.Runtime.CompilerServices;
using System.Text.Json;

namespace AgUiProtocol;

/// <summary>
/// Posts a user message to an AG-UI agent endpoint and streams back
/// strongly-typed <see cref="AgUiEvent"/> objects over Server-Sent Events.
///
/// Transport contract:
///   POST /api/agent/run  →  text/event-stream
///   Each line:  data: { "type": "...", ... }\n\n
///
/// Register with DI via AddHttpClient&lt;AgUiStreamService&gt;, pointing
/// the base address at your agent backend.
/// </summary>
public class AgUiStreamService
{
    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private readonly HttpClient _http;

    public AgUiStreamService(HttpClient http) => _http = http;

    /// <summary>
    /// Streams AG-UI events for a single run.
    /// Caller should iterate with <c>await foreach</c> and pass a
    /// <see cref="CancellationToken"/> tied to the user's cancel action.
    /// </summary>
    public async IAsyncEnumerable<AgUiEvent> StreamRunAsync(
        string userMessage,
        string? threadId = null,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/agent/run")
        {
            Content = JsonContent.Create(new
            {
                message   = userMessage,
                thread_id = threadId ?? string.Empty,
            }),
        };

        using var response = await _http.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            ct);

        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream);

        while (!reader.EndOfStream && !ct.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync(ct);

            // SSE format: meaningful lines begin with "data: "
            if (line is null || !line.StartsWith("data: ", StringComparison.Ordinal))
                continue;

            var json = line[6..]; // strip the "data: " prefix
            AgUiEvent? evt;
            try
            {
                evt = JsonSerializer.Deserialize<AgUiEvent>(json, _jsonOptions);
            }
            catch (JsonException)
            {
                continue; // skip any malformed event rather than crashing the stream
            }

            if (evt is not null)
                yield return evt;
        }
    }
}
