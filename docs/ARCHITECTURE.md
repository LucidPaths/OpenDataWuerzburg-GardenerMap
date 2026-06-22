# Architecture

```text
Browser dashboard
  -> local Python server
    -> Würzburg OpenData API (`sls-klimabaeume`)
    -> optional Ollama/Ollama Cloud chat endpoint
```

## Deterministic boundary

`wuerzburg_gardener_map.opendata` fetches and normalizes public data. It decides:

- latest record per tree sensor
- watering priority
- history samples
- map coordinates

The model does not fetch data. It receives only the snapshot already shown on the dashboard.

## Credential boundary

The optional browser key flow posts the key to `/api/connect-ai`. The key is stored in the Python process only and is never returned by `/api/ai-status` or committed to files.

## Frontend

The dashboard uses Leaflet from CDN for the map. If CDN access is unavailable, the JSON endpoints and data cards still prove the live data path.
