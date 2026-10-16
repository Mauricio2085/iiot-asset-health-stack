## Overview

End-to-end industrial telemetry pipeline for critical asset health monitoring. One simulated pump publishes temperature, pressure, and vibration. The stack ingests those signals, checks the payload, stores them as a time series, and charts them.

Prosys OPC UA Simulation Server runs on the Windows host and is not part of Compose. The lab setup is described in [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md) ([español](docs/opcua-prosys.md)).

### Pipeline

```text
Prosys OPC UA (Windows host)
        │  poll every 5 s
        ▼
Node-RED ingestion  ──MQTT──►  Mosquitto
                                    │  plant-01/area-01/critical-pump-01/telemetry
                                    ▼
                              Node-RED ETL
                                    │  validate, then insert
                                    ▼
                               TimescaleDB
                                    │
                                    ▼
                                 Grafana
```

### Services

| Service | Image | Host port |
| --- | --- | --- |
| Mosquitto | `eclipse-mosquitto:2.0.22` | 1883 |
| Node-RED ingestion | `nodered/node-red:4.0.9` | 1881 |
| Node-RED ETL | `nodered/node-red:4.0.9` | 1882 |
| TimescaleDB | `timescale/timescaledb:2.30.2-pg17` | 5435 |
| Grafana | `grafana/grafana-oss:12.0.4` | 3001 |

Grafana login comes from `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD`. The dashboard is in the **IIoT** folder.

### Quick start

Docker is required. Prosys must already be running and reachable before any points show up in Grafana.

```bash
cp .env.example .env
docker compose up -d
```

Change the passwords in `.env` before using the stack outside this machine. `OPCUA_ENDPOINT` must match the Prosys endpoint from the container network. See [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md).

Open Grafana at `http://localhost:3001` and select **Asset Health**. The charts stay empty until the ingestion flow publishes a valid reading.

### What the payload looks like

The ingestion flow publishes QoS 1 JSON to `plant-01/area-01/critical-pump-01/telemetry`:

```json
{
  "asset_id": "critical-pump-01",
  "ts": "2026-10-15T21:00:00.000Z",
  "temperature": 70.2,
  "pressure": 2.4,
  "vibration": 1.1,
  "quality": "good"
}
```

The ETL flow accepts the message only when `asset_id` matches the topic, the three signals are finite numbers, and `ts` is a timestamp. Valid rows go into `sensor_readings`.

### Current limits

- One asset, `critical-pump-01`, with `quality` fixed to `good`.
- No readings are produced if Prosys is down or the three NodeIds are missing.
- Mosquitto still allows anonymous clients. `MQTT_USER` and `MQTT_PASSWORD` are reserved and unused.
- OPC UA security mode is `None`. That matches this lab simulator and is not a plant connection.
