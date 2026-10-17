# Modbus TCP

[Español](modbus-tcp.md)

`modbus-slave` is the second OT source in this lab. It is a Modbus TCP server that exposes three holding registers for `critical-motor-01`. `node-red-ingestion` polls them every 5 seconds, scales the values, and publishes the same telemetry JSON contract used by the MQTT simulator.

The asset is a motor, not a "Modbus pump". The `asset_id` names the equipment; Modbus is only how its readings reach the edge.

## Register map

| Register | Signal | Scaling | Example |
| --- | --- | --- | --- |
| HR0 | temperature | value / 10 | `550` → `55.0` °C |
| HR1 | pressure | value / 100 | `100` → `1.00` bar |
| HR2 | vibration | value / 100 | `80` → `0.80` |

- Unit id: `1`
- Container port: `502`
- Host port: `1502` (`localhost:1502` from the host)
- Nominal point: ~55 °C, ~1.0 bar, ~0.8 vibration
- Soft noise matches `mqtt-simulator` (slow sine drift plus small jitter)

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
