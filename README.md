# Generative UI Demo — Blazor + AG-UI + LangGraph

A working end-to-end demo of **Controlled Generative UI**: a LangGraph agent (Python) decides which UI component to show, and a Blazor frontend (C#) renders it — connected by the AG-UI protocol over Server-Sent Events.

The agent can render two components on demand:
- **WeatherCard** — shows current conditions for any city
- **FlightOptions** — shows a list of flights between two cities

---

## Project structure

```
demo/
├── agent/               Python — LangGraph agent backend
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example
│
└── BlazorAGUIDemo/      C# — ASP.NET Blazor Server frontend
    ├── BlazorAGUIDemo.csproj
    ├── appsettings.json
    ├── Program.cs
    ├── Services/
    │   ├── AgUiModels.cs          AG-UI event types and chat models
    │   ├── ComponentRegistry.cs   Maps tool names → Blazor components
    │   └── AgUiStreamService.cs   SSE stream consumer
    ├── Components/
    │   ├── GenUI/
    │   │   ├── AgentChat.razor    Core AG-UI event loop
    │   │   ├── ChatMessage.razor  Message bubble
    │   │   └── ChatInput.razor    Input bar
    │   └── Widgets/
    │       ├── WeatherCard.razor       Weather display component
    │       └── FlightOptions.razor     Flight list component
    └── wwwroot/
        └── app.css
```

---

## Prerequisites

| Tool | Minimum version | Download |
|---|---|---|
| Python | 3.11 | https://python.org |
| .NET SDK | 8.0 | https://dotnet.microsoft.com/download |
| Anthropic API key | — | https://console.anthropic.com |

---

## Setup and Running the Source Code:

1. **Create a Conda environment (Assuming Anaconda is installed)**:
   ```bash
   conda create --prefix Z:\\conda_env\\generative_ui_agent_env Python=3.11 -y && conda activate Z:\conda_env\generative_ui_agent_env
   ```

2. **Activate the environment**:
   ```bash
   conda activate Z:\conda_env\generative_ui_agent_env
   ```

3. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   
   ```


*To remove the environment after use:*
```bash
conda remove --prefix Z:\conda_env\generative_ui_agent_env --all
```

---

## Run the Agent

4. **Start the agent server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

   You should see:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   INFO:     Application startup complete.
   ```

5. **Verify it is running** — open a browser or run:
   ```bash
   curl http://localhost:8000/health
   ```
   Expected response: `{"status":"ok"}`

6. **Test with the Python client** — open a second terminal, activate the environment, then:
   ```bash
   # Single message
   python client.py "What's the weather in Dhaka?"

   python client.py "Show me flights from London to New York on 2026-06-01"

   Give me a travel dashboard for a trip from London to New York
   

   # Interactive REPL
   python client.py
   ```

   Press **Ctrl+C** to stop the server.
   

### Dependencies

All dependencies come from the .NET 8 SDK — no NuGet packages need to be added manually. The project uses only framework-included libraries:

| Library | Source |
|---|---|
| `Microsoft.AspNetCore.Components` | Included in .NET 8 SDK |
| `System.Net.Http` | Included in .NET 8 SDK |
| `System.Text.Json` | Included in .NET 8 SDK |


---

## Using the demo

The chat interface shows two **suggestion chips** when it first loads — one for each registered component. Click a chip to pre-fill the input, or type your own message:

| What you type | What the agent renders |
|---|---|
| "What's the weather in Tokyo?" | **WeatherCard** with temperature, condition, humidity, wind |
| "Show me flights from London to New York" | **FlightOptions** with airline, times, and prices |

The agent streams its text response token-by-token while deciding which component to show. A skeleton placeholder holds the layout space until the component is fully hydrated (preventing Cumulative Layout Shift).

---

## How it works

```
User types a message
        │
        ▼
Blazor POSTs to /api/agent/run
        │
        ▼
LangGraph runs Claude, decides to call show_weather or show_flight_options
        │
        ▼
Agent emits AG-UI events over SSE:
  RUN_STARTED
  TEXT_MESSAGE_CONTENT  (streamed tokens)
  UI_TOOL_CALL_START    (skeleton appears in Blazor)
  UI_TOOL_CALL_ARGS     (component parameters)
  UI_TOOL_CALL_END      (component hydrates and renders)
  RUN_FINISHED
        │
        ▼
Blazor ComponentRegistry looks up the tool name,
deserialises the args, and renders the Blazor component
via DynamicComponent
```

---

## Troubleshooting

**"Could not reach agent"** in the chat UI  
→ The Python agent is not running. Start `uvicorn main:app --reload --port 8000` first.

**HTTPS certificate warning in browser**  
→ Run `dotnet dev-certs https --trust` once to trust the local development certificate.

**`ANTHROPIC_API_KEY` not found error from the agent**  
→ Make sure `.env` exists in `demo/agent/` and contains your key. The `.env.example` file shows the expected format.

**Agent responds but no component appears**  
→ Check the browser console and the uvicorn terminal for errors. The most common cause is a JSON schema mismatch between the tool parameters the LLM returned and what the C# model expects.
