# Würzburg Gardener Map

A gardener-focused dashboard for Würzburg OpenData tree sensors.

It shows:

- a live map of the OpenData climate-tree sensor locations
- moisture/watering priority cards
- hover/click details for each tree
- a compact history sparkline for recent soil-moisture readings
- an Ollama-backed chatbox scoped only to the current tree snapshot
- a demo-friendly **Connect your AI** box for pasting an Ollama API key locally

Data source: <https://opendata.wuerzburg.de/>

Dataset used:

```text
sls-klimabaeume
```

## Quick start

```bash
git clone https://github.com/LucidPaths/OpenDataWuerzburg-GardenerMap.git
cd OpenDataWuerzburg-GardenerMap
python -m venv .venv
. .venv/bin/activate  # Windows git-bash / Linux / macOS
pip install -e .
python dashboard/app.py
```

Open:

```text
http://127.0.0.1:8777/
```

Windows CMD:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python dashboard\app.py
```

## AI connection

The dashboard has a **Connect your AI** form. Paste an Ollama API key there for demo mode.

Security boundary:

- the browser sends the key only to the local Python server
- the server stores it in process memory only
- it is not written to disk
- status endpoints never echo the key back
- the chat context is the current deterministic OpenData snapshot, not free-form browsing

Environment alternative:

```bash
export OLLAMA_API_KEY="<ollama-api-key>"
export OLLAMA_BASE_URL="https://ollama.com/v1"
export OLLAMA_MODEL="gpt-oss:20b"
python dashboard/app.py
```

If no key is configured, the app tries local Ollama at `http://127.0.0.1:11434/api/chat`.

## CLI snapshot

```bash
wuerzburg-gardener-snapshot --limit 500
```

Outputs JSON with latest tree state and per-tree moisture history.

## Development

```bash
uv run --with pytest python -m pytest
python dashboard/generate_dashboard.py
python dashboard/app.py --port 8777
```

## Demo framing

Python/OpenData is the truth source. The AI assistant only explains the loaded tree snapshot: what is dry, what looks stable, what changed recently, and what a gardener might inspect first.
