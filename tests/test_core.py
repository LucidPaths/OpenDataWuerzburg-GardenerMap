from wuerzburg_gardener_map.chat import CONNECTED_AI, ai_status, answer_from_response, chat_request, connect_ai, normalize_ai_connection
from wuerzburg_gardener_map.opendata import parse_sample, priority_for, snapshot_context
from wuerzburg_gardener_map.server import build_static_html


SAMPLE_RECORD = {
    "vwc": 16,
    "bat": 86,
    "temp": 19.49,
    "fieldcapacity30": 100.0,
    "moisturecategory": 0,
    "ss_serialnumber": "AB04173BF302B433",
    "ss_baumart": "Platanus x hispanica",
    "ss_latitude": 49.793194,
    "ss_baumnummer": "Unbekannt",
    "ss_longitude": 9.927876,
    "originatorname": "Grafeneckart 1",
    "timestamp": "2026-06-04T19:50:31+00:00",
    "koordinaten": {"lon": 9.927876, "lat": 49.793194},
}


def sample_snapshot():
    sample = parse_sample(SAMPLE_RECORD)
    tree = sample.__dict__.copy()
    tree.update({"priority": priority_for(sample), "history": [sample.__dict__], "historyCount": 1, "vwcTrend": 0})
    return {"generatedAt": "test", "source": "https://opendata.wuerzburg.de/", "dataset": "sls-klimabaeume", "treeCount": 1, "dryOrWatchCount": 1, "averageVwc": 16, "trees": [tree]}


def test_parse_tree_sample_and_priority():
    sample = parse_sample(SAMPLE_RECORD)
    assert sample.serial == "AB04173BF302B433"
    assert sample.lat == 49.793194
    assert priority_for(sample)["level"] == "critical"


def test_snapshot_context_mentions_gardener_relevant_fields():
    context = snapshot_context(sample_snapshot())
    assert "Grafeneckart 1" in context
    assert "VWC 16" in context
    assert "Water first" in context


def test_dashboard_contains_map_hover_chat_and_connect_flow():
    html = build_static_html(sample_snapshot())
    assert "Würzburg Gardener Map" in html
    assert "Leaflet" in html or "leaflet" in html
    assert "Connect your AI" in html
    assert "/api/connect-ai" in html
    assert "/api/chat" in html
    assert "Hover a tree" in html


def test_ollama_cloud_request_shape():
    config = normalize_ai_connection({"apiKey": "demo-key", "baseUrl": "https://ollama.com/v1", "model": "demo-model"})
    api_url, payload = chat_request("Which tree first?", sample_snapshot(), config=config)
    assert api_url == "https://ollama.com/v1/chat/completions"
    assert payload["model"] == "demo-model"
    assert "options" not in payload
    assert "demo-key" not in str(payload)


def test_connect_ai_status_never_echoes_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    CONNECTED_AI.clear()
    status = connect_ai({"apiKey": "demo-key", "baseUrl": "https://ollama.com/v1", "model": "demo-model"})
    assert status == {"connected": True, "source": "browser", "baseUrl": "https://ollama.com/v1", "model": "demo-model"}
    assert "demo-key" not in str(status)
    assert ai_status()["source"] == "browser"
    CONNECTED_AI.clear()


def test_answer_from_native_and_openai_responses():
    assert answer_from_response({"message": {"content": "native"}}) == "native"
    assert answer_from_response({"choices": [{"message": {"content": "compat"}}]}) == "compat"
