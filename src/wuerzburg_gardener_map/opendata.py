from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
import argparse
import collections
import json
import urllib.parse
import urllib.request

TREE_CADASTRE_DATASET = "baumkataster_stadt_wuerzburg"
SENSOR_DATASET = "sls-klimabaeume"
API_BASE = "https://opendata.wuerzburg.de/api/explore/v2.1/catalog/datasets"
TREE_EXPORT_URL = f"{API_BASE}/{TREE_CADASTRE_DATASET}/exports/json"
SENSOR_RECORDS_URL = f"{API_BASE}/{SENSOR_DATASET}/records"


@dataclass(frozen=True)
class TreeInventoryItem:
    tree_id: str
    species: str
    species_latin: str
    tree_type: str
    crown_width_m: float | None
    height_m: float | None
    trunk_circumference_cm: float | None
    lat: float
    lon: float
    source: str = TREE_CADASTRE_DATASET


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


def fetch_json(url: str, *, timeout: int = 90) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "wuerzburg-gardener-map/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_tree_inventory() -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"lang": "de", "timezone": "Europe/Berlin"})
    payload = fetch_json(f"{TREE_EXPORT_URL}?{params}", timeout=120)
    return list(payload if isinstance(payload, list) else [])


def fetch_sensor_records(*, limit: int = 1500, offset: int = 0) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"limit": limit, "offset": offset})
    payload = fetch_json(f"{SENSOR_RECORDS_URL}?{params}", timeout=45)
    return list(payload.get("results", []))


def fetch_all_sensor_records(*, limit: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_size = min(100, max(1, limit))
    for offset in range(0, limit, page_size):
        page = fetch_sensor_records(limit=page_size, offset=offset)
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


def parse_inventory_item(record: dict[str, Any]) -> TreeInventoryItem | None:
    point = record.get("geo_punkt") or {}
    lat = as_float(point.get("lat"))
    lon = as_float(point.get("lon"))
    tree_id = str(record.get("source_id") or "").strip()
    if not tree_id or lat is None or lon is None:
        return None
    return TreeInventoryItem(
        tree_id=tree_id,
        species=str(record.get("baumart") or "Unbekannte Baumart"),
        species_latin=str(record.get("baumart_la") or ""),
        tree_type=str(record.get("baumtyp") or "Unbekannter Baumtyp"),
        crown_width_m=as_float(record.get("kronenbrei")),
        height_m=as_float(record.get("baumhoehe")),
        trunk_circumference_cm=as_float(record.get("stammumfan")),
        lat=lat,
        lon=lon,
    )


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


def priority_for_sample(sample: TreeSample) -> dict[str, Any]:
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


def priority_for(sample: TreeSample) -> dict[str, Any]:
    """Backward-compatible alias used by tests and older imports."""
    return priority_for_sample(sample)


def inventory_priority() -> dict[str, Any]:
    return {
        "level": "inventory",
        "score": 5,
        "label": "Inventory tree",
        "action": "No live moisture sensor; use map position/species for route planning or manual inspection.",
    }


def sensor_trees(*, sensor_limit: int = 2000, history_points: int = 24) -> list[dict[str, Any]]:
    samples = [s for s in (parse_sample(row) for row in fetch_all_sensor_records(limit=sensor_limit)) if s]
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
            "id": f"sensor:{serial}",
            "tree_id": serial,
            "displayName": latest.origin,
            "priority": priority_for_sample(latest),
            "history": [asdict(sample) for sample in recent],
            "historyCount": len(ordered),
            "vwcTrend": trend,
            "hasSensor": True,
            "source": SENSOR_DATASET,
        })
        trees.append(tree)
    return trees


def inventory_trees() -> list[dict[str, Any]]:
    trees: list[dict[str, Any]] = []
    for item in (parse_inventory_item(row) for row in fetch_tree_inventory()):
        if not item:
            continue
        tree = asdict(item)
        tree.update({
            "id": f"cadastre:{item.tree_id}",
            "serial": item.tree_id,
            "origin": f"Baumkataster #{item.tree_id}",
            "displayName": f"{item.species} #{item.tree_id}",
            "vwc": None,
            "temperature": None,
            "battery": None,
            "timestamp": None,
            "priority": inventory_priority(),
            "history": [],
            "historyCount": 0,
            "vwcTrend": None,
            "hasSensor": False,
        })
        trees.append(tree)
    return trees


def build_snapshot(*, limit: int | None = None, sensor_limit: int = 2000, history_points: int = 24) -> dict[str, Any]:
    inventory = inventory_trees()
    if limit:
        inventory = inventory[:limit]
    sensors = sensor_trees(sensor_limit=sensor_limit, history_points=history_points)
    trees = sensors + inventory
    trees.sort(key=lambda t: (-(t["priority"]["score"]), not t.get("hasSensor"), str(t.get("species") or ""), str(t.get("tree_id") or "")))

    dry = sum(1 for t in trees if t["priority"]["level"] in {"critical", "watch"})
    avg_vwc_values = [t["vwc"] for t in trees if t.get("vwc") is not None]
    avg_vwc = round(sum(avg_vwc_values) / len(avg_vwc_values), 1) if avg_vwc_values else None
    species_counts = collections.Counter(str(t.get("species") or "Unbekannt") for t in inventory)
    type_counts = collections.Counter(str(t.get("tree_type") or "Unbekannt") for t in inventory)
    return {
        "generatedAt": utc_now_label(),
        "source": "https://opendata.wuerzburg.de/",
        "dataset": f"{TREE_CADASTRE_DATASET} + {SENSOR_DATASET}",
        "treeCount": len(trees),
        "inventoryTreeCount": len(inventory),
        "sensorTreeCount": len(sensors),
        "totalRecordsLoaded": len(inventory) + sum(t.get("historyCount", 0) for t in sensors),
        "dryOrWatchCount": dry,
        "averageVwc": avg_vwc,
        "speciesTop": species_counts.most_common(10),
        "typeCounts": type_counts.most_common(10),
        "trees": trees,
    }


def snapshot_context(snapshot: dict[str, Any]) -> str:
    lines = [
        f"Generated: {snapshot.get('generatedAt')}",
        f"Datasets: {snapshot.get('dataset')} from {snapshot.get('source')}",
        f"All mapped trees: {snapshot.get('treeCount')} | cadastre inventory: {snapshot.get('inventoryTreeCount')} | live sensor trees: {snapshot.get('sensorTreeCount')}",
        f"Sensor dry/watch: {snapshot.get('dryOrWatchCount')} | average sensor VWC: {snapshot.get('averageVwc')}",
        f"Top species: {snapshot.get('speciesTop')}",
    ]
    sensor_rows = [t for t in snapshot.get("trees", []) if t.get("hasSensor")]
    for tree in sensor_rows:
        priority = tree.get("priority") or {}
        lines.append(
            f"- SENSOR {tree.get('origin')} ({tree.get('species')}, serial {tree.get('serial')}): "
            f"VWC {tree.get('vwc')}%, temp {tree.get('temperature')}°C, battery {tree.get('battery')}%, "
            f"priority {priority.get('level')} / {priority.get('label')}, action: {priority.get('action')}, "
            f"latest {tree.get('timestamp')}, trend {tree.get('vwcTrend')} over loaded history."
        )
    if not sensor_rows:
        lines.append("No live moisture sensor rows are present in the current snapshot.")
    lines.append("Cadastre trees have map position, species, height/crown/trunk fields where published, but no live moisture reading.")
    return "\n".join(lines)[:12000]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Würzburg tree cadastre + climate sensor snapshot for gardeners.")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap for cadastre inventory trees; default loads all.")
    args = parser.parse_args(argv)
    print(json.dumps(build_snapshot(limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
