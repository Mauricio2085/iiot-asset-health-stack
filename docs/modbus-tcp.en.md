# Modbus TCP

[Español](modbus-tcp.md)

`modbus-slave` is the second OT source in this lab. It is a Modbus TCP server that exposes three holding registers. `node-red-ingestion` polls them every 5 seconds, scales the values, and publishes the same telemetry JSON contract used by the MQTT simulator — on a separate asset so both sources can run together.

## Register map

| Register | Signal | Scaling | Example |
| --- | --- | --- | --- |
| HR0 | temperature | value / 10 | `702` → `70.2` °C |
| HR1 | pressure | value / 100 | `250` → `2.50` bar |
| HR2 | vibration | value / 100 | `100` → `1.00` |

- Unit id: `1`
- Container port: `502`
- Host port: `1502` (`localhost:1502` from the host)
- Soft noise matches `mqtt-simulator` (slow sine drift plus small jitter)

## MQTT contract

Topic: `plant-01/area-01/modbus-pump-01/telemetry` (QoS 1)

```json
{
  "asset_id": "modbus-pump-01",
  "ts": "2026-10-16T15:00:00.000Z",
  "temperature": 70.2,
  "pressure": 2.5,
  "vibration": 1.0,
  "quality": "good"
}
```

`asset_id` is `modbus-pump-01` on purpose. The default simulator keeps `critical-pump-01`, so Grafana can show both series at once.

## Check

1. `docker compose up -d --build`
2. From the host, a Modbus TCP client against `localhost:1502`, unit `1`, can read holding registers 0–2.
3. In the ingestion editor (`http://localhost:1881`), the **Modbus TCP Ingestion** tab is enabled and the getter shows activity every 5 seconds.
4. An MQTT read of `plant-01/area-01/modbus-pump-01/telemetry` returns the JSON above.
5. Grafana **Asset Health** lists `modbus-pump-01` next to `critical-pump-01`.

If step 3 fails, confirm `modbus-slave` is healthy and that Node-RED finished installing `node-red-contrib-modbus` (first start can take a minute).

## RTU (horizon)

The same register map and scaling would apply over Modbus RTU (`/dev/ttyUSB0`, baud, parity, stop bits). This stack does not implement RTU yet: no serial device is mounted into Compose, and there is no RTU client tab in Node-RED. When a USB adapter is available, the ingestion client type would switch from TCP to serial; the MQTT contract would stay the same.
