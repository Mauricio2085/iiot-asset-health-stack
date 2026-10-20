# Modbus TCP

[Español](modbus-tcp.md)

`modbus-slave` is the second OT source in this lab. It is a Modbus TCP server that exposes four holding registers for `critical-motor-01`: three readings and a device status. `node-red-ingestion` polls them every 5 seconds, scales the readings, translates the status into the contract quality, and publishes the same telemetry JSON contract used by the MQTT simulator.

The asset is a motor, not a "Modbus pump". The `asset_id` names the equipment; Modbus is only how its readings reach the edge.

## Register map

| Register | Signal | Scaling | Example |
| --- | --- | --- | --- |
| HR0 | temperature | value / 10 | `550` → `55.0` °C |
| HR1 | pressure | value / 100 | `100` → `1.00` bar |
| HR2 | vibration | value / 100 | `80` → `0.80` mm/s RMS |
| HR3 | device status | `0` good, `1` uncertain, `2` bad | `0` → `good` |

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
| 1:00–1:30 | `sensor-fault` | the transmitter fails: HR2 saturates at 25.00 mm/s and HR3 is `2` (bad) |
| 3–10 | `unbalance-ramp` | rises on a curve; crosses 2.8 near minute 7.8 and 4.5 near minute 9.6 |
| 10–13 | `alarm-hold` | ~5.0 mm/s, sustained |
| 13 | maintenance | the rotor is balanced, vibration returns to ~0.8 and the cycle repeats |

The ramp is quadratic: it starts slow and accelerates, like the P-F curve of a real failure. Temperature rises by at most 1.5 °C and pressure does not change. Only vibration moving points to a mechanical cause rather than a process one. With overall vibration alone, the pattern is *consistent with* unbalance; confirming it would take a vibration spectrum.

Reference thresholds, based on ISO 10816-3 for medium machines on rigid foundations: **warning at 2.8 mm/s** (zone B/C limit) and **alarm at 4.5 mm/s** (zone C/D limit). Exact limits depend on each machine's size and mounting.

### Sensor fault

During the normal phase the vibration transmitter fails for 30 seconds. A broken 4–20 mA loop drives the reading to the top of the sensor range (NAMUR NE43 treats a current above 21 mA as a failure), so HR2 reads 25.00 mm/s, five times the alarm limit. The device flags it by setting HR3 to `2`. Temperature and pressure stay normal: the instrument failed, not the motor.

The readings are stored with `quality = bad`, but `asset_condition` leaves them out of the averages, so the motor stays `normal` instead of raising a false alarm. The dashboard shows a gap in the vibration trend and notes the discarded readings on the motor tile. See [asset-condition.en.md](asset-condition.en.md#data-quality).

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

`quality` comes from HR3. The device decides it, and Node-RED translates the device code into the contract vocabulary: `0` → `good`, `1` → `uncertain`, `2` → `bad`. Any other code becomes `bad`, because the edge cannot vouch for a reading whose status it does not understand.

## Check

1. `docker compose up -d --build`
2. From the host, a Modbus TCP client against `localhost:1502`, unit `1`, can read holding registers 0–3.
3. In the ingestion editor (`http://localhost:1881`), the **Modbus TCP Ingestion** tab is enabled and the getter shows activity every 5 seconds.
4. An MQTT read of `plant-01/area-01/critical-motor-01/telemetry` returns the JSON above.
5. Grafana **Asset Health** lists `critical-motor-01` next to `critical-pump-01` and `critical-compressor-01`.
6. One minute after `docker compose restart modbus-slave`, six motor readings arrive with `vibration = 25` and `quality = bad`, and the motor tile stays `NORMAL` with "6 bad readings discarded".

If step 3 fails, confirm `modbus-slave` is healthy and that Node-RED finished installing `node-red-contrib-modbus` (first start can take a minute).

### Reconnecting after the slave stops

If `modbus-slave` is stopped with `docker compose stop`, the Node-RED Modbus client does not reconnect on its own when the slave comes back. While the container is stopped, Docker DNS no longer resolves `modbus-slave` and the client gets `ENOTFOUND`. `node-red-contrib-modbus` 5.45.2 does not list that code among the errors that trigger a retry, so the client stays in its initial state and stops reading.

Meanwhile `critical-motor-01` shows as `stale` in `asset_condition`. To recover:

```bash
docker compose restart node-red-ingestion
```

In testing, `docker compose restart modbus-slave` recovered on its own because the slave is back within a couple of seconds; a longer stop leaves the client stuck. Automatic reconnection is pending for the OT boundary phase.

## RTU (horizon)

The same register map and scaling would apply over Modbus RTU (`/dev/ttyUSB0`, baud, parity, stop bits). This stack does not implement RTU yet: no serial device is mounted into Compose, and there is no RTU client tab in Node-RED. When a USB adapter is available, the ingestion client type would switch from TCP to serial; the MQTT contract would stay the same.
