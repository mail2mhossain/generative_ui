using AgUiProtocol;
using BlazorAGUIDemo.Components;
using BlazorAGUIDemo.Components.Blocks;
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
// MCP manifest service — Pillar 3A
// AddHttpClient<T>() registers McpManifestService as a typed client (scoped),
// injecting a pooled HttpClient that is safe to use in Blazor Server circuits.
// No base address is set here — the MCP server URL comes from McpAppParams at
// runtime and is passed directly to McpManifestService.FetchAsync().
// ---------------------------------------------------------------------------
builder.Services.AddHttpClient<McpManifestService>();

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

    registry.Register<DeclarativeView, DeclarativeSchema>(
        toolName:        ToolNames.ShowDeclarativeView,
        description:     "Display a composable dashboard built from metric cards, flight rows, and more.",
        suggestedPrompt: "Give me a travel dashboard for a trip from London to New York",
        expectedHeight:  420);

    // Pillar 3A — MCP App
    registry.Register<McpAppFrame, McpAppParams>(
        toolName:        ToolNames.OpenExcalidraw,
        description:     "Open the Excalidraw diagramming app to create or edit diagrams.",
        suggestedPrompt: "Draw a sequence diagram for the login flow",
        expectedHeight:  520);

    return registry;
});

// ---------------------------------------------------------------------------
// BlockRegistry — maps declarative block type strings → Blazor components
// ---------------------------------------------------------------------------
builder.Services.AddSingleton<BlockRegistry>(sp =>
{
    var registry = new BlockRegistry();
    registry.Register<MetricCard,    MetricCardParams>   ("metric_card");
    registry.Register<PageTitle,     PageTitleParams>    ("page_title");
    registry.Register<SearchHeader,  SearchHeaderParams> ("search_header");
    registry.Register<FlightRow,     FlightRowParams>    ("flight_row");
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
