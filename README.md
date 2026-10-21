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
| `critical-pump-01` | ~70 °C | ~2.5 bar | ~1.0 mm/s |
| `critical-compressor-01` | ~85 °C | ~6.0 bar | ~1.5 mm/s |
| `critical-motor-01` | ~55 °C | ~1.0 bar | ~0.8 mm/s |

Vibration is velocity in mm/s RMS. Reference thresholds follow ISO 10816-3 for medium machines on rigid foundations: warning at 2.8 mm/s, alarm at 4.5 mm/s.

### Demo scenario: motor unbalance

`critical-motor-01` repeats a 13-minute cycle: 3 minutes of normal operation, a progressive unbalance that crosses warning near minute 7.8 and alarm near minute 9.6, 3 minutes of sustained alarm, then a simulated rotor balancing that brings it back to normal. Temperature and pressure barely move, which points to a mechanical cause rather than a process one. The pump and the compressor stay healthy as a contrast.

Run `docker compose restart modbus-slave` to start the cycle from minute 0. Details: [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md#unbalance-scenario).

Two data-quality episodes run alongside it:

- **Instrument failure, not machine failure.** At minute 1 of each motor cycle the vibration transmitter fails for 30 seconds: the reading saturates at 25 mm/s and the device flags it as `bad`. The stack keeps those readings in history but leaves them out of the condition, so the motor stays `normal` instead of raising a false alarm.
- **Doubtful data.** For 2 minutes in every 10, the pump temperature sensor reads 3 °C high and the simulator flags the readings as `uncertain`. They are used, and the dashboard marks them.

For a five-minute walkthrough, `scripts/demo-prep.sh` lines these episodes up so that warning, uncertain data, and alarm happen while you watch. Timings and what to look at: [docs/demo.en.md](docs/demo.en.md).

### Asset condition

TimescaleDB holds the engineering limits of each asset in `asset_limits` and exposes the `asset_condition` view: one row per asset with `normal`, `warning`, `alarm`, or `stale`. Each signal is judged on its 1-minute average, the asset takes the worst state of its signals, and an asset with no usable readings in the last minute is `stale`. Readings with `quality = bad` are left out of the averages; `uncertain` ones are used and counted.

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, condition, vibration_avg, data_quality, bad_1m, last_seen FROM asset_condition;"'
```

During the motor scenario, `critical-motor-01` moves from `normal` to `warning` and `alarm`, then back after maintenance. Limits, rules, margin used, and how to change a threshold: [docs/asset-condition.en.md](docs/asset-condition.en.md).

### Dashboard

**Asset Health** in Grafana reads top to bottom, one question per band:

1. **What needs attention?** Counters of assets in alarm, in warning, and without data, then one tile per asset with its condition, the margin used, and the signal behind it ("87 % of margin used · vibration"). When readings are doubtful or discarded, the tile adds a note such as "6 bad readings discarded".
2. **Why, and where is it heading?** One row per asset with vibration, temperature, and pressure trends. Warning (amber) and alarm (red) limits are dashed lines read from `asset_limits`, so changing a limit in the database moves the line. Trends leave out `bad` readings and break the line when readings are missing for more than 15 seconds.
3. **Detail.** A table of `asset_condition`: 1-minute averages, the state of each signal, data availability, data quality with the uncertain and discarded readings, and the time of the last reading.

Colors follow ISA-101 for high-performance HMIs: `normal` is gray, and color is kept for abnormal states (amber warning, red alarm, purple no data or doubtful data). With every asset healthy the screen has no color at all.

The dashboard is provisioned from `grafana/dashboards/asset-health.json` and cannot be saved from the Grafana UI. Edit the file instead; Grafana reloads it within about 10 seconds, and the browser shows the change after a page refresh. Rows and tiles repeat over the assets in `asset_limits`, so a new asset shows up without editing the JSON.

Lab notes: [docs/demo.en.md](docs/demo.en.md) ([español](docs/demo.md)), [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md) ([español](docs/modbus-tcp.md)), [docs/asset-condition.en.md](docs/asset-condition.en.md) ([español](docs/asset-condition.md)), [docs/asset-registry.en.md](docs/asset-registry.en.md) ([español](docs/asset-registry.md)), [docs/opcua-prosys.en.md](docs/opcua-prosys.en.md) ([español](docs/opcua-prosys.md)).

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

Services use `restart: on-failure`: Docker restarts a container that crashes, but does not start the stack when Docker itself starts. After a reboot, run `docker compose up -d` again. On Docker Desktop with WSL, containers started by Docker at boot can come up before the WSL files exist, with empty bind mounts: TimescaleDB fails to start and Grafana loads no dashboard.

Open Grafana at `http://localhost:3001` and select **Asset Health**. Within about a minute you should see tiles and trend rows for `critical-pump-01`, `critical-compressor-01`, and `critical-motor-01`.

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

`quality` uses the OPC UA levels `good`, `uncertain`, and `bad`. The source decides it, the edge translates device codes into this vocabulary, and IT validates it. See [docs/asset-condition.en.md](docs/asset-condition.en.md#data-quality).

The ETL flow accepts the message only when `asset_id` matches the topic, the three signals are finite numbers, `ts` is a timestamp, `quality` is one of the three levels, and the asset is in the registry with the same plant and area as the topic. Valid rows go into `sensor_readings`, whose quality column has the same rule. Plant, area, type, and criticality live in `assets`: [docs/asset-registry.en.md](docs/asset-registry.en.md).

Modbus values arrive as integers in holding registers and are scaled in Node-RED (`HR0 / 10`, `HR1 / 100`, `HR2 / 100`); HR3 carries the device status that becomes `quality`. See [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md).

### Current limits

- Three lab assets in one plant and area, all with the same three signals.
- Quality is one value per message: a failing sensor marks the other two signals of that reading too. Per-signal quality needs a narrow, one-row-per-signal model.
- Messages the ETL rejects only show in the debug sidebar of the ETL editor; they are not stored anywhere.
- Nothing sends notifications: a warning or alarm is only visible on the dashboard.
- Grafana 12.0.4 picks the Y-axis tick step on its own; there is no fixed step per panel.
- Database changes after the first start are applied by hand with `psql`; there is no migration tool.
- Mosquitto still allows anonymous clients. `MQTT_USER` and `MQTT_PASSWORD` are reserved and unused.
- OPC UA security mode is `None` when that optional path is enabled. That matches the lab simulator and is not a plant connection.
- Modbus RTU is not implemented (serial / USB horizon only).
- After `docker compose stop modbus-slave`, the Node-RED Modbus client does not reconnect on its own; run `docker compose restart node-red-ingestion`. See [docs/modbus-tcp.en.md](docs/modbus-tcp.en.md#reconnecting-after-the-slave-stops).

### Lessons learned

Building the MVP with three fixed signals for every asset kept the ETL, the SQL, and the dashboard simple, and every concept (condition, margin used, quality, `stale`) could be built without pivoting data. It also showed where that model stops working:

- **Signals should follow failure modes.** Reliability work starts from an FMEA per asset type, and ISO 17359 maps each failure mode to the parameters that detect it. Starting from three fixed signals gave the motor a "pressure" that is never evaluated.
- **Narrow measurements fit better than fixed columns.** One row per asset, signal, and time gives each signal its own quality, lets a new signal arrive without a schema change, and joins directly with the narrow `asset_limits` table.
- **Metadata belongs in an asset registry, not in the message.** Plant, area, type, and criticality now live in `assets`. Units and limits stay on `asset_limits`. A template of limits per asset type is still ahead.
- **Standards beat a custom contract.** Sparkplug B already defines typed metrics with quality, plus birth and death messages that report a disconnected device without waiting for a one-minute window. ISA-95 and a Unified Namespace give the topic hierarchy a shared meaning.
- **Rejected messages need somewhere to go.** A dead-letter table or topic, holding each message with its rejection reason, keeps contract violations visible after they happen.

Still ahead in this phase: continuous aggregates, a place for rejected messages, an ADR on wide versus narrow measurements, and a versioned contract that accepts the current payload during that migration.
