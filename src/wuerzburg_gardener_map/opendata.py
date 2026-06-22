from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import argparse
import json
import urllib.parse
import urllib.request

DATASET_ID = "sls-klimabaeume"
API_BASE = "https://opendata.wuerzburg.de/api/explore/v2.1/catalog/datasets"
RECORDS_URL = f"{API_BASE}/{DATASET_ID}/records"


@dataclass(frozen=True)
class TreeSample:
    serial: str
    tree_number: str
    species: str
    origin: str
    lat: float
    lon: float
    timestamp: str
    vwc: float | None
    temperature: float | None
    battery: float | None
    moisture_category: int | None
    field_capacity_30: float | None


def utc_now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fetch_records(*, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"limit": limit, "offset": offset})
    with urllib.request.urlopen(f"{RECORDS_URL}?{params}", timeout=45) as response:
        payload = json.load(response)
    return list(payload.get("results", []))


def fetch_all_records(*, limit: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_size = min(100, max(1, limit))
    for offset in range(0, limit, page_size):
        page = fetch_records(limit=page_size, offset=offset)
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
    return rows[:limit]


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_sample(record: dict[str, Any]) -> TreeSample | None:
    lat = as_float(record.get("ss_latitude") or (record.get("koordinaten") or {}).get("lat"))
    lon = as_float(record.get("ss_longitude") or (record.get("koordinaten") or {}).get("lon"))
    serial = str(record.get("ss_serialnumber") or "").strip()
    timestamp = str(record.get("timestamp") or "").strip()
    if not serial or lat is None or lon is None or not timestamp:
        return None
    return TreeSample(
        serial=serial,
        tree_number=str(record.get("ss_baumnummer") or "Unbekannt"),
        species=str(record.get("ss_baumart") or "Unbekannte Baumart"),
        origin=str(record.get("originatorname") or "Unbekannter Standort"),
        lat=lat,
        lon=lon,
        timestamp=timestamp,
        vwc=as_float(record.get("vwc")),
        temperature=as_float(record.get("temp")),
        battery=as_float(record.get("bat")),
        moisture_category=as_int(record.get("moisturecategory")),
        field_capacity_30=as_float(record.get("fieldcapacity30")),
    )


def parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def priority_for(sample: TreeSample) -> dict[str, Any]:
    vwc = sample.vwc
    category = sample.moisture_category
    if vwc is None:
        return {"level": "unknown", "score": 0, "label": "No moisture reading", "action": "Inspect sensor/data feed."}
    if vwc < 18 or category == 0:
        return {"level": "critical", "score": 95, "label": "Very dry", "action": "Water first; verify soil and sensor condition."}
    if vwc < 30 or category == 1:
        return {"level": "watch", "score": 65, "label": "Getting dry", "action": "Put on next watering route."}
    if vwc < 45 or category == 2:
        return {"level": "ok", "score": 35, "label": "Moisture acceptable", "action": "Monitor; no immediate watering signal."}
    return {"level": "good", "score": 15, "label": "Moist", "action": "No watering priority from current reading."}


def build_snapshot(*, limit: int = 1000, history_points: int = 24) -> dict[str, Any]:
    samples = [s for s in (parse_sample(row) for row in fetch_all_records(limit=limit)) if s]
    by_serial: dict[str, list[TreeSample]] = {}
    for sample in samples:
        by_serial.setdefault(sample.serial, []).append(sample)

    trees: list[dict[str, Any]] = []
    for serial, history in by_serial.items():
        ordered = sorted(history, key=lambda s: parse_timestamp(s.timestamp), reverse=True)
        latest = ordered[0]
        oldest = ordered[-1]
        recent = list(reversed(ordered[:history_points]))
        trend = None
        if latest.vwc is not None and oldest.vwc is not None:
            trend = round(latest.vwc - oldest.vwc, 2)
        tree = asdict(latest)
        tree.update({
            "priority": priority_for(latest),
            "history": [asdict(sample) for sample in recent],
            "historyCount": len(ordered),
            "vwcTrend": trend,
        })
        trees.append(tree)

    trees.sort(key=lambda t: (-(t["priority"]["score"]), t["origin"]))
    dry = sum(1 for t in trees if t["priority"]["level"] in {"critical", "watch"})
    avg_vwc_values = [t["vwc"] for t in trees if t.get("vwc") is not None]
    avg_vwc = round(sum(avg_vwc_values) / len(avg_vwc_values), 1) if avg_vwc_values else None
    return {
        "generatedAt": utc_now_label(),
        "source": "https://opendata.wuerzburg.de/",
        "dataset": DATASET_ID,
        "totalRecordsLoaded": len(samples),
        "treeCount": len(trees),
        "dryOrWatchCount": dry,
        "averageVwc": avg_vwc,
        "trees": trees,
    }


def snapshot_context(snapshot: dict[str, Any]) -> str:
    lines = [
        f"Generated: {snapshot.get('generatedAt')}",
        f"Dataset: {snapshot.get('dataset')} from {snapshot.get('source')}",
        f"Trees: {snapshot.get('treeCount')} | dry/watch: {snapshot.get('dryOrWatchCount')} | average VWC: {snapshot.get('averageVwc')}",
    ]
    for tree in snapshot.get("trees", []):
        priority = tree.get("priority") or {}
        lines.append(
            f"- {tree.get('origin')} ({tree.get('species')}, serial {tree.get('serial')}): "
            f"VWC {tree.get('vwc')}%, temp {tree.get('temperature')}°C, battery {tree.get('battery')}%, "
            f"priority {priority.get('level')} / {priority.get('label')}, action: {priority.get('action')}, "
            f"latest {tree.get('timestamp')}, trend {tree.get('vwcTrend')} over loaded history."
        )
    return "\n".join(lines)[:12000]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Würzburg climate tree snapshot for gardeners.")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    print(json.dumps(build_snapshot(limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
