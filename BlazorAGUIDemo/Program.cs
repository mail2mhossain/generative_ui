using AgUiProtocol;
using BlazorAGUIDemo.Components;
using BlazorAGUIDemo.Components.Widgets;
using BlazorAGUIDemo.Services;

var builder = WebApplication.CreateBuilder(args);

// ---------------------------------------------------------------------------
// Blazor Interactive Server rendering
// ---------------------------------------------------------------------------
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// ---------------------------------------------------------------------------
// AG-UI stream service — HttpClient targeting the Python agent backend
// ---------------------------------------------------------------------------
builder.Services.AddHttpClient<AgUiStreamService>(client =>
{
    var agentUrl = builder.Configuration["AgentUrl"] ?? "http://localhost:8000";
    client.BaseAddress = new Uri(agentUrl);
    client.Timeout = TimeSpan.FromMinutes(5); // allow long streaming runs
});

// ---------------------------------------------------------------------------
// ComponentRegistry — the developer-owned map of AG-UI tool names → components
// Descriptions here become the suggestion chips in the chat UI.
// ---------------------------------------------------------------------------
builder.Services.AddSingleton<ComponentRegistry>(sp =>
{
    var registry = new ComponentRegistry();

    registry.Register<WeatherCard, WeatherCardParameters>(
        toolName:        ToolNames.ShowWeather,
        description:     "Display a weather card with current conditions for any location.",
        suggestedPrompt: "What's the weather like in London right now?",
        expectedHeight:  220);

    registry.Register<FlightOptions, FlightOptionsParameters>(
        toolName:        ToolNames.ShowFlightOptions,
        description:     "Display available flight options between two cities.",
        suggestedPrompt: "Show me flights from London to New York next Friday",
        expectedHeight:  360);

    return registry;
});

var app = builder.Build();

// ---------------------------------------------------------------------------
// Startup validation — verify every registered tool name exists in the agent.
// Throws on mismatch so the app refuses to start with broken configuration.
// ---------------------------------------------------------------------------
using (var scope = app.Services.CreateScope())
{
    var registry  = scope.ServiceProvider.GetRequiredService<ComponentRegistry>();
    var httpFactory = scope.ServiceProvider.GetRequiredService<IHttpClientFactory>();
    var http      = httpFactory.CreateClient(nameof(AgUiStreamService));
    var logger    = scope.ServiceProvider
                         .GetRequiredService<ILoggerFactory>()
                         .CreateLogger(nameof(AgentSchemaValidator));

    await AgentSchemaValidator.ValidateAsync(registry, http, logger);
}

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseAntiforgery();

app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
