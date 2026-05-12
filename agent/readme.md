## API Keys Required

| Service | Used for | Cost | Sign-up |
|---|---|---|---|
| Anthropic | Claude LLM | Paid (per token) | https://console.anthropic.com |
| Open-Meteo | Live weather | Free, no key needed | — |
| Amadeus | Live flight search | Free sandbox | https://developers.amadeus.com |

### Get an Amadeus sandbox key (free)

1. Go to [developers.amadeus.com](https://developers.amadeus.com) and create an account
2. Click **My Apps → Create new app**
3. Copy **Client ID** and **Client Secret** into `.env`:
   ```
   AMADEUS_CLIENT_ID=your_client_id_here
   AMADEUS_CLIENT_SECRET=your_client_secret_here
   ```
   The sandbox is free with no billing required and returns realistic test data.

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

   # Interactive REPL
   python client.py
   ```

   Press **Ctrl+C** to stop the server.

### `uvicorn` flags reference

| Flag | Purpose |
|---|---|
| `--reload` | Auto-restart on file save (development) |
| `--port 8000` | Port number — change if 8000 is in use |
| `--host 0.0.0.0` | Accept connections from other machines |