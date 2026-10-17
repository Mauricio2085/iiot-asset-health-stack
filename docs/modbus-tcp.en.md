# Modbus TCP

[Español](modbus-tcp.md)

`modbus-slave` is the second OT source in this lab. It is a Modbus TCP server that exposes three holding registers for `critical-motor-01`. `node-red-ingestion` polls them every 5 seconds, scales the values, and publishes the same telemetry JSON contract used by the MQTT simulator.

The asset is a motor, not a "Modbus pump". The `asset_id` names the equipment; Modbus is only how its readings reach the edge.

## Register map

| Register | Signal | Scaling | Example |
| --- | --- | --- | --- |
| HR0 | temperature | value / 10 | `550` → `55.0` °C |
| HR1 | pressure | value / 100 | `100` → `1.00` bar |
| HR2 | vibration | value / 100 | `80` → `0.80` mm/s RMS |

- Unit id: `1`
- Container port: `502`
- Host port: `1502` (`localhost:1502` from the host)
- Nominal point: ~55 °C, ~1.0 bar, ~0.8 mm/s
- Soft noise matches `mqtt-simulator` (slow sine drift plus small jitter)

## Unbalance scenario

The motor repeats a 13-minute cycle that simulates a progressive rotor unbalance:

| Minutes | Phase in the log | Vibration |
| --- | --- | --- |
| 0–3 | `normal` | ~0.8 mm/s |
| 3–10 | `unbalance-ramp` | rises on a curve; crosses 2.8 near minute 7.8 and 4.5 near minute 9.6 |
| 10–13 | `alarm-hold` | ~5.0 mm/s, sustained |
| 13 | maintenance | the rotor is balanced, vibration returns to ~0.8 and the cycle repeats |

The ramp is quadratic: it starts slow and accelerates, like the P-F curve of a real failure. Temperature rises by at most 1.5 °C and pressure does not change. Only vibration moving points to a mechanical cause rather than a process one. With overall vibration alone, the pattern is *consistent with* unbalance; confirming it would take a vibration spectrum.

Reference thresholds, based on ISO 10816-3 for medium machines on rigid foundations: **warning at 2.8 mm/s** (zone B/C limit) and **alarm at 4.5 mm/s** (zone C/D limit). Exact limits depend on each machine's size and mounting.

To start the cycle from minute 0, for example at the beginning of a demo:

```bash
docker compose restart modbus-slave
```

## MQTT contract

Topic: `plant-01/area-01/critical-motor-01/telemetry` (QoS 1)

```json
{
  "asset_id": "critical-motor-01",
  "ts": "2026-10-16T15:00:00.000Z",
  "temperature": 55.0,
  "pressure": 1.0,
  "vibration": 0.8,
  "quality": "good"
}
```

The `asset_id` in the payload must match the asset segment of the topic, or the ETL rejects the message.

## Check

1. `docker compose up -d --build`
2. From the host, a Modbus TCP client against `localhost:1502`, unit `1`, can read holding registers 0–2.
3. In the ingestion editor (`http://localhost:1881`), the **Modbus TCP Ingestion** tab is enabled and the getter shows activity every 5 seconds.
4. An MQTT read of `plant-01/area-01/critical-motor-01/telemetry` returns the JSON above.
5. Grafana **Asset Health** lists `critical-motor-01` next to `critical-pump-01` and `critical-compressor-01`.

If step 3 fails, confirm `modbus-slave` is healthy and that Node-RED finished installing `node-red-contrib-modbus` (first start can take a minute).

## RTU (horizon)

The same register map and scaling would apply over Modbus RTU (`/dev/ttyUSB0`, baud, parity, stop bits). This stack does not implement RTU yet: no serial device is mounted into Compose, and there is no RTU client tab in Node-RED. When a USB adapter is available, the ingestion client type would switch from TCP to serial; the MQTT contract would stay the same.
