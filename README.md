## Overview

End-to-end industrial telemetry pipeline for critical asset health monitoring. Three simulated critical assets (a pump, a compressor, and a motor) publish temperature, pressure, and vibration. The stack ingests those signals, checks the payload, stores them as a time series, and charts them.

### OT sources

| Source | Role | Assets | Default |
| --- | --- | --- | --- |
| `mqtt-simulator` | Publishes the telemetry JSON straight to Mosquitto | `critical-pump-01`, `critical-compressor-01` | On |
| `modbus-slave` + Node-RED Modbus tab | Modbus TCP holding registers → scaled JSON → MQTT | `critical-motor-01` | On |
| Prosys OPC UA | Optional Windows-host simulator → Node-RED OPC UA tab | `critical-pump-01` | Off |

Each `asset_id` names the equipment. The source column only says how its readings reach the edge.

| Asset | Nominal temperature | Nominal pressure | Nominal vibration |
| --- | --- | --- | --- |
| `critical-pump-01` | ~70 °C | ~2.5 bar | ~1.0 |
| `critical-compressor-01` | ~85 °C | ~6.0 bar | ~1.5 |
| `critical-motor-01` | ~55 °C | ~1.0 bar | ~0.8 |

Lab notes: [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md) ([español](docs/modbus-tcp.md)), [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md) ([español](docs/opcua-prosys.md)).

### Pipeline

```text
mqtt-simulator ──────────────────────────────┐
                                             │  QoS 1
modbus-slave ──► Node-RED (Modbus TCP) ──────┼──► Mosquitto
                                             │      │  +/+/+/telemetry
Prosys OPC UA ─► Node-RED (OPC UA, off) ─────┘      ▼
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
| modbus-slave | `./modbus-slave` | 1502 |
| Node-RED ingestion | `nodered/node-red:4.0.9` | 1881 |
| Node-RED ETL | `nodered/node-red:4.0.9` | 1882 |
| TimescaleDB | `timescale/timescaledb:2.30.2-pg17` | 5435 |
| Grafana | `grafana/grafana-oss:12.0.4` | 3001 |

Grafana login comes from `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD`. The dashboard is in the **IIoT** folder.

### Quick start

Docker is required. The MQTT simulator and the Modbus TCP path start with the stack. No Windows host tools are required for the demo.

```bash
cp .env.example .env
docker compose up -d --build
```

Change the passwords in `.env` before using the stack outside this machine. First start of `node-red-ingestion` may take a minute while it installs Modbus nodes.

Open Grafana at `http://localhost:3001` and select **Asset Health**. Within about a minute you should see `critical-pump-01`, `critical-compressor-01`, and `critical-motor-01`.

### Optional OT source: Prosys OPC UA

The OPC UA ingestion tab is disabled by default so it does not compete with `mqtt-simulator` on the same topic. To use Prosys instead:

1. Stop or remove the simulator: `docker compose stop mqtt-simulator` (or scale it to 0). This also stops `critical-compressor-01`, which only comes from the simulator.
2. Run Prosys on the Windows host and set `OPCUA_ENDPOINT` in `.env`.
3. Enable the **OPC UA Ingestion** tab in the ingestion editor at `http://localhost:1881`.

Full setup: [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md).

### What the payload looks like

Every OT path publishes QoS 1 JSON to `plant-01/area-01/<asset_id>/telemetry`:

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

Modbus values arrive as integers in holding registers and are scaled in Node-RED (`HR0 / 10`, `HR1 / 100`, `HR2 / 100`). See [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md).

### Current limits

- Three lab assets in one plant and area; `quality` is fixed to `good`.
- Mosquitto still allows anonymous clients. `MQTT_USER` and `MQTT_PASSWORD` are reserved and unused.
- OPC UA security mode is `None` when that optional path is enabled. That matches the lab simulator and is not a plant connection.
- Modbus RTU is not implemented (serial / USB horizon only).
