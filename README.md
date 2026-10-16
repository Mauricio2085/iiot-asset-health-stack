## Overview

End-to-end industrial telemetry pipeline for critical asset health monitoring. One simulated pump publishes temperature, pressure, and vibration. The stack ingests those signals, checks the payload, stores them as a time series, and charts them.

By default, `mqtt-simulator` publishes that telemetry over MQTT. No Windows host tools are required for the demo. Prosys OPC UA remains an optional path; see [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md) ([español](docs/opcua-prosys.md)).

### Pipeline

```text
mqtt-simulator
        │  publish every 5 s (QoS 1)
        ▼
   Mosquitto  ◄──  Node-RED ingestion (OPC UA optional, off by default)
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

| Service | Image / build | Host port |
| --- | --- | --- |
| Mosquitto | `eclipse-mosquitto:2.0.22` | 1883 |
| mqtt-simulator | `./mqtt-simulator` | — |
| Node-RED ingestion | `nodered/node-red:4.0.9` | 1881 |
| Node-RED ETL | `nodered/node-red:4.0.9` | 1882 |
| TimescaleDB | `timescale/timescaledb:2.30.2-pg17` | 5435 |
| Grafana | `grafana/grafana-oss:12.0.4` | 3001 |

Grafana login comes from `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD`. The dashboard is in the **IIoT** folder.

### Quick start

Docker is required. The MQTT simulator starts with the stack and fills Grafana without Prosys.

```bash
cp .env.example .env
docker compose up -d --build
```

Change the passwords in `.env` before using the stack outside this machine.

Open Grafana at `http://localhost:3001` and select **Asset Health**. Charts should show `critical-pump-01` within about a minute after the first publish.

### Optional OT source: Prosys OPC UA

The OPC UA ingestion tab is disabled by default so it does not compete with `mqtt-simulator` on the same topic. To use Prosys instead:

1. Stop or remove the simulator: `docker compose stop mqtt-simulator` (or scale it to 0).
2. Run Prosys on the Windows host and set `OPCUA_ENDPOINT` in `.env`.
3. Enable the **OPC UA Ingestion** tab in the ingestion editor at `http://localhost:1881`.

Full setup: [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md).

### What the payload looks like

The simulator (and the optional OPC UA flow) publishes QoS 1 JSON to `plant-01/area-01/critical-pump-01/telemetry`:

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
- Mosquitto still allows anonymous clients. `MQTT_USER` and `MQTT_PASSWORD` are reserved and unused.
- OPC UA security mode is `None` when that optional path is enabled. That matches the lab simulator and is not a plant connection.
