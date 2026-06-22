from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import argparse
import json
import traceback
import urllib.parse

from .chat import ai_status, ask_ai, connect_ai
from .opendata import build_snapshot

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8777

DASHBOARD_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Würzburg Gardener Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="" />
  <style>
    :root { color-scheme: dark; --bg:#07130c; --panel:#102017; --line:#254832; --text:#effff5; --muted:#9bb9a5; --ok:#44d27d; --watch:#f5c84b; --critical:#ff6b6b; --blue:#86c5ff; --shadow: 0 22px 70px #0008; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif; background: radial-gradient(circle at 12% 10%, #246b3f88 0 18rem, transparent 42rem), linear-gradient(180deg, #07130c, #071016 65%, #030604); color:var(--text); }
    header { padding: 32px clamp(18px, 4vw, 56px) 20px; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:20px; align-items:end; }
    .eyebrow { color:#9fffc1; text-transform:uppercase; letter-spacing:.16em; font-size:13px; font-weight:800; }
    h1 { margin:8px 0 12px; font-size:clamp(34px,6vw,76px); line-height:.92; }
    .subtitle { color:#cbe3d1; max-width:900px; font-size:clamp(16px,2vw,20px); line-height:1.45; margin:0; }
    .statusBox { min-width:250px; border:1px solid var(--line); background:#0b1a11cc; border-radius:22px; padding:16px 18px; box-shadow:var(--shadow); }
    .statusBox b { display:block; font-size:28px; } .statusBox span { color:var(--muted); font-size:13px; }
    .layout { display:grid; grid-template-columns: minmax(340px, 1.35fr) minmax(320px, .65fr); gap:18px; padding:0 clamp(18px,4vw,56px) 44px; }
    .panel { border:1px solid var(--line); background:linear-gradient(180deg,#102017ee,#08130cee); border-radius:26px; box-shadow:var(--shadow); overflow:hidden; }
    #map { height: 660px; min-height: 70vh; background:#06100a; }
    .side { display:grid; gap:16px; align-content:start; }
    .cards { display:grid; gap:12px; padding:16px; }
    .treeCard { border:1px solid #2b5138; background:#08150dee; border-radius:18px; padding:14px; transition:.2s ease; cursor:pointer; }
    .treeCard:hover, .treeCard.active { transform:translateY(-1px); border-color:#7ee6a2; background:#0d2014; }
    .treeTop { display:flex; justify-content:space-between; gap:12px; } .treeTitle { font-weight:900; } .treeMeta { color:var(--muted); font-size:12px; margin-top:4px; }
    .metric { font-size:24px; font-weight:900; text-align:right; } .metric small { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; }
    .pill { display:inline-flex; margin-top:10px; padding:5px 8px; border-radius:999px; font-size:12px; font-weight:800; border:1px solid #345f41; }
    .critical { color:#ffd6d6; background:#4a1118; border-color:#8b2b36; } .watch { color:#fff2c0; background:#3a2d08; border-color:#80651c; } .ok,.good { color:#caffda; background:#0b2d19; border-color:#2b8149; } .unknown { color:#d9e3eb; background:#17212a; }
    .spark { width:100%; height:34px; margin-top:12px; overflow:visible; }
    .detail { padding:16px; border-top:1px solid var(--line); color:#d8eadc; min-height:170px; } .detail h2 { margin:0 0 8px; } .detail dl { display:grid; grid-template-columns:auto 1fr; gap:6px 12px; } .detail dt { color:var(--muted); } .detail dd { margin:0; }
    .chat { margin: 0 clamp(18px,4vw,56px) 34px; } .chatHead { padding:18px 20px; display:flex; justify-content:space-between; gap:16px; border-bottom:1px solid var(--line); }
    .chatBadge { color:#9fffc1; text-transform:uppercase; letter-spacing:.1em; font-size:12px; font-weight:800; white-space:nowrap; }
    .connect { display:grid; grid-template-columns:1.5fr 1fr auto; gap:10px; padding:14px 20px; border-bottom:1px solid var(--line); background:#07130c99; }
    input, button { border:1px solid #315a3e; border-radius:12px; padding:10px 12px; color:var(--text); background:#0a1810; font:inherit; }
    button { cursor:pointer; border:0; background:linear-gradient(135deg,#15803d,#2563eb); font-weight:850; } button:hover { filter:brightness(1.12); }
    .hint { grid-column:1/-1; color:var(--muted); font-size:12px; }
    .chatLog { display:grid; gap:10px; max-height:300px; overflow:auto; padding:16px 20px; } .msg { border:1px solid #2a4b37; background:#08140d; border-radius:16px; padding:12px 14px; white-space:pre-wrap; line-height:1.45; } .msg.user { justify-self:end; background:#103054; max-width:82%; } .msg.error { background:#351219; border-color:#82313a; }
    .chatForm { display:flex; gap:10px; padding:14px 20px 20px; } .chatForm input { flex:1; }
    footer { padding:0 clamp(18px,4vw,56px) 30px; color:var(--muted); }
    @media (max-width: 980px) { header,.layout { grid-template-columns:1fr; } #map { height:520px; } .connect { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <div><div class="eyebrow">Würzburg OpenData · gardener view</div><h1>Gardener Map</h1><p class="subtitle">Live climate-tree moisture readings mapped for watering priority. Hover a tree marker or card to fade the latest sensor details into view.</p></div>
    <div class="statusBox"><b id="treeCount">—</b><span id="generatedAt">Loading OpenData tree sensors…</span></div>
  </header>
  <section class="layout">
    <div class="panel"><div id="map"></div></div>
    <aside class="side panel"><div class="cards" id="cards"></div><div class="detail" id="detail"><h2>Hover a tree</h2><p>Latest moisture, battery, temperature, action hint, and mini history will appear here.</p></div></aside>
  </section>
  <section class="chat panel">
    <div class="chatHead"><div><h2>Ask the gardener assistant</h2><p>Scoped to this live tree snapshot only.</p></div><div class="chatBadge" id="aiStatus">AI not connected</div></div>
    <form id="connectForm" class="connect"><input id="apiKeyInput" type="password" placeholder="Connect your AI · paste Ollama API key" autocomplete="off" /><input id="modelInput" value="gpt-oss:20b" aria-label="Ollama model" /><button type="submit">Connect AI</button><div class="hint">The key goes only to this localhost Python server, stays in memory for this run, and is never written or echoed back.</div></form>
    <div id="chatLog" class="chatLog"><div class="msg">Try: “Which tree should a gardener inspect first?” or “Summarize the watering situation.”</div></div>
    <form id="chatForm" class="chatForm"><input id="chatInput" placeholder="Ask about these tree sensors…" autocomplete="off" /><button type="submit">Ask</button></form>
  </section>
  <footer>Source: <a href="https://opendata.wuerzburg.de/" style="color:#9fffc1">opendata.wuerzburg.de</a> · Dataset: <code>sls-klimabaeume</code></footer>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<script>
const treeCount = document.getElementById('treeCount'), generatedAt = document.getElementById('generatedAt'), cards = document.getElementById('cards'), detail = document.getElementById('detail');
const chatLog = document.getElementById('chatLog'), chatInput = document.getElementById('chatInput'), aiStatus = document.getElementById('aiStatus'), apiKeyInput = document.getElementById('apiKeyInput'), modelInput = document.getElementById('modelInput');
let snapshot = null, map = null, markers = new Map();
const esc = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function color(level){ return {critical:'#ff6b6b',watch:'#f5c84b',ok:'#44d27d',good:'#44d27d',unknown:'#9bb9a5'}[level] || '#9bb9a5'; }
function spark(history){
  const vals = history.map(h => Number(h.vwc)).filter(Number.isFinite); if(vals.length < 2) return '<div class="treeMeta">No history line yet</div>';
  const min=Math.min(...vals), max=Math.max(...vals), span=Math.max(1,max-min);
  const pts = vals.map((v,i)=>`${(i/(vals.length-1)*100).toFixed(1)},${(32-((v-min)/span)*28).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none"><polyline fill="none" stroke="#9fffc1" stroke-width="2" points="${pts}"/><line x1="0" y1="32" x2="100" y2="32" stroke="#2b5138"/></svg>`;
}
function renderDetail(t){
  const p=t.priority || {}; detail.innerHTML = `<h2>${esc(t.origin)}</h2><p><span class="pill ${esc(p.level)}">${esc(p.label)} · ${esc(p.level)}</span></p>${spark(t.history || [])}<dl><dt>Species</dt><dd>${esc(t.species)}</dd><dt>Moisture</dt><dd>${esc(t.vwc)}% VWC · trend ${esc(t.vwcTrend)}</dd><dt>Temperature</dt><dd>${esc(t.temperature)} °C</dd><dt>Battery</dt><dd>${esc(t.battery)}%</dd><dt>Latest</dt><dd>${esc(t.timestamp)}</dd><dt>Action</dt><dd>${esc(p.action)}</dd></dl>`;
  document.querySelectorAll('.treeCard').forEach(el => el.classList.toggle('active', el.dataset.serial === t.serial));
}
function card(t){ const p=t.priority||{}; return `<article class="treeCard" data-serial="${esc(t.serial)}"><div class="treeTop"><div><div class="treeTitle">${esc(t.origin)}</div><div class="treeMeta">${esc(t.species)} · ${esc(t.historyCount)} records</div></div><div class="metric">${esc(t.vwc)}<small>% VWC</small></div></div><span class="pill ${esc(p.level)}">${esc(p.label)}</span>${spark(t.history || [])}</article>`; }
function initMap(trees){
  if(!map){ map = L.map('map'); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'© OpenStreetMap'}).addTo(map); }
  markers.forEach(m => m.remove()); markers.clear(); const bounds=[];
  trees.forEach(t => { const p=t.priority||{}, c=color(p.level); const m=L.circleMarker([t.lat,t.lon], {radius:13, color:c, fillColor:c, fillOpacity:.78, weight:3}).addTo(map); m.bindTooltip(`${t.origin}: ${t.vwc}% VWC · ${p.label}`); m.on('mouseover',()=>renderDetail(t)); m.on('click',()=>renderDetail(t)); markers.set(t.serial,m); bounds.push([t.lat,t.lon]); });
  if(bounds.length) map.fitBounds(bounds, {padding:[40,40], maxZoom:16});
}
async function load(){ const res=await fetch('/api/trees'); const data=await res.json(); if(!res.ok) throw new Error(data.error||'snapshot failed'); snapshot=data; treeCount.textContent=`${data.treeCount} trees`; generatedAt.textContent=`Generated ${data.generatedAt} · ${data.dryOrWatchCount} dry/watch`; cards.innerHTML=data.trees.map(card).join(''); cards.querySelectorAll('.treeCard').forEach(el => el.addEventListener('mouseover',()=>renderDetail(data.trees.find(t=>t.serial===el.dataset.serial)))); initMap(data.trees); if(data.trees[0]) renderDetail(data.trees[0]); }
function msg(role,text){ const div=document.createElement('div'); div.className=`msg ${role||''}`; div.textContent=text; chatLog.appendChild(div); chatLog.scrollTop=chatLog.scrollHeight; return div; }
async function refreshAi(){ const res=await fetch('/api/ai-status'); const data=await res.json(); aiStatus.textContent=data.connected?`AI connected · ${data.source} · ${data.model}`:'AI not connected'; modelInput.value=data.model||modelInput.value; }
async function connectAi(apiKey, model){ const res=await fetch('/api/connect-ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({apiKey,baseUrl:'https://ollama.com/v1',model})}); const data=await res.json(); if(!res.ok) throw new Error(data.error||'connect failed'); aiStatus.textContent=`AI connected · ${data.source} · ${data.model}`; apiKeyInput.value=''; msg('',`AI connected for this localhost session using ${data.model}.`); }
async function ask(q){ msg('user', q); const pending=msg('', 'Thinking against the current tree snapshot…'); const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,snapshot})}); const data=await res.json(); if(!res.ok) throw new Error(data.error||'chat failed'); pending.textContent=`${data.answer}\n\n— ${data.model}, context ${data.contextGeneratedAt}`; }
document.getElementById('connectForm').addEventListener('submit', async e => { e.preventDefault(); try { await connectAi(apiKeyInput.value.trim(), modelInput.value.trim() || 'gpt-oss:20b'); } catch(err){ msg('error', err.message || String(err)); } });
document.getElementById('chatForm').addEventListener('submit', async e => { e.preventDefault(); const q=chatInput.value.trim(); if(!q) return; chatInput.value=''; try { if(!snapshot) await load(); await ask(q); } catch(err){ msg('error', err.message || String(err)); } });
refreshAi().catch(()=>{}); load().catch(err => { cards.innerHTML=`<article class="treeCard"><b>Dashboard error</b><pre>${esc(err.stack||err)}</pre></article>`; });
</script>
</body>
</html>
'''


def build_static_html(snapshot: dict[str, Any] | None = None) -> str:
    if snapshot is None:
        return DASHBOARD_HTML
    literal = json.dumps(snapshot, ensure_ascii=False)
    return DASHBOARD_HTML.replace(
        "async function load(){ const res=await fetch('/api/trees');",
        f"window.__STATIC_SNAPSHOT__ = {literal};\nasync function load(){{ const res = {{ok:true, json: async () => window.__STATIC_SNAPSHOT__}};",
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_body(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        self.send_body(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path in {"/", "/index.html"}:
                self.send_body(200, DASHBOARD_HTML.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/trees":
                self.send_json(200, build_snapshot(limit=1000))
                return
            if parsed.path == "/api/ai-status":
                self.send_json(200, ai_status())
                return
            self.send_body(404, b"not found", "text/plain; charset=utf-8")
        except Exception as exc:
            self.send_json(500, {"error": str(exc), "traceback": traceback.format_exc(limit=4)})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in {"/api/connect-ai", "/api/chat"}:
            self.send_body(404, b"not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(min(length, 65536)).decode("utf-8"))
            if parsed.path == "/api/connect-ai":
                self.send_json(200, connect_ai(request))
                return
            question = str(request.get("question") or "").strip()
            if not question:
                self.send_json(400, {"error": "question is required"})
                return
            snapshot = request.get("snapshot") if isinstance(request.get("snapshot"), dict) else build_snapshot(limit=1000)
            self.send_json(200, ask_ai(question[:1000], snapshot))
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Würzburg Gardener Map running at http://{host}:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Würzburg gardener tree map dashboard.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
