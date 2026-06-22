from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import urllib.request
import urllib.error

from .opendata import snapshot_context

ROOT = Path(__file__).resolve().parents[2]
CONNECTED_AI: dict[str, str] = {}


def load_env_file(path: Path | None = None) -> None:
    env_paths = [path] if path else [ROOT / ".env"]
    for env_path in env_paths:
        if not env_path or not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def normalize_ai_connection(config: dict[str, Any]) -> dict[str, str]:
    api_key = str(config.get("apiKey") or config.get("api_key") or "").strip()
    if not api_key:
        raise ValueError("Ollama API key is required")
    base_url = str(config.get("baseUrl") or config.get("base_url") or "https://ollama.com/v1").strip().rstrip("/")
    model = str(config.get("model") or "gpt-oss:20b").strip()
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("Base URL must start with http:// or https://")
    if not model:
        raise ValueError("Model is required")
    return {"api_key": api_key, "base_url": base_url, "model": model}


def connect_ai(config: dict[str, Any]) -> dict[str, Any]:
    CONNECTED_AI.clear()
    CONNECTED_AI.update(normalize_ai_connection(config))
    return ai_status()


def ai_status() -> dict[str, Any]:
    load_env_file()
    source = "browser" if CONNECTED_AI.get("api_key") else "environment" if os.getenv("OLLAMA_API_KEY") else "local"
    return {
        "connected": bool(CONNECTED_AI.get("api_key") or os.getenv("OLLAMA_API_KEY")),
        "source": source,
        "baseUrl": CONNECTED_AI.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
        "model": CONNECTED_AI.get("model") or os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
    }


def build_chat_messages(question: str, snapshot: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a gardener-facing assistant for a Würzburg OpenData tree dashboard. "
                "Answer only from the tree snapshot context. Quote exact counts from the context when asked; do not round, reinterpret, or substitute record counts for tree counts. "
                "Be practical: watering priority, sensor condition, latest reading, and what to inspect next. "
                "If the context does not contain the answer, say the dashboard does not show it. Do not invent locations, weather, policies, or routes."
            ),
        },
        {"role": "user", "content": f"Tree dashboard context:\n{snapshot_context(snapshot)}\n\nQuestion: {question}"},
    ]


def chat_request(question: str, snapshot: dict[str, Any], *, config: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    config = config or {}
    explicit_api_url = (config.get("api_url") or os.getenv("OLLAMA_API_URL") or "").rstrip("/")
    base_url = (config.get("base_url") or os.getenv("OLLAMA_BASE_URL") or "").rstrip("/")
    model = config.get("model") or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    messages = build_chat_messages(question, snapshot)
    if explicit_api_url:
        api_url = explicit_api_url
    elif base_url.endswith("/v1") or "/v1/" in base_url:
        api_url = f"{base_url}/chat/completions"
    elif base_url:
        api_url = base_url if base_url.endswith("/api/chat") else f"{base_url}/api/chat"
    elif config.get("api_key") or os.getenv("OLLAMA_API_KEY"):
        api_url = "https://ollama.com/api/chat"
    else:
        api_url = "http://127.0.0.1:11434/api/chat"

    if "/chat/completions" in api_url:
        return api_url, {"model": model, "messages": messages, "stream": False, "temperature": 0.2}
    return api_url, {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.2}}


def answer_from_response(result: dict[str, Any]) -> str:
    answer = (result.get("message") or {}).get("content") or result.get("response")
    if not answer and result.get("choices"):
        answer = ((result["choices"][0] or {}).get("message") or {}).get("content")
    if not answer:
        raise RuntimeError(f"Ollama API response did not contain an answer: {result!r}")
    return str(answer).strip()


def ask_ai(question: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    load_env_file()
    config = dict(CONNECTED_AI)
    api_key = config.get("api_key") or os.getenv("OLLAMA_API_KEY")
    api_url, payload = chat_request(question, snapshot, config=config)
    model = str(payload.get("model") or os.getenv("OLLAMA_MODEL", "gpt-oss:20b"))
    headers = {"Content-Type": "application/json", "User-Agent": "wuerzburg-gardener-map/0.1"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(api_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"Ollama API returned HTTP {exc.code}: {body}") from exc
    return {"answer": answer_from_response(result), "model": model, "contextGeneratedAt": snapshot.get("generatedAt")}
