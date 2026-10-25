# OT/IT boundary and MQTT taxonomy

[Español](adr-ot-it.md)

Status: accepted. 2026-10-24.

## Context

The lab splits the edge into two networks. A reading from the pump, the compressor, or the motor has to reach TimescaleDB, and the process that speaks Modbus or OPC UA does not open the database.

| Network | Who is there |
| --- | --- |
| `ot-net` | `mqtt-simulator`, `modbus-slave`, `node-red-ingestion` |
| `it-net` | `node-red-etl`, TimescaleDB, Grafana |
| both | Mosquitto |

Mosquitto is the only name both networks resolve. The ETL does not resolve the Modbus slave. Ingestion does not resolve `timescaledb`, and that container is not given `POSTGRES_PASSWORD`. Grafana and the ETL use the name `timescaledb` on `it-net`.

Each Node-RED adds a `prohibit` route for `172.16.0.0/12`, the range of this Docker's bridge networks. The connected route of its own network is more specific, so the broker on that network still answers. An address on the other subnet, inside that range, matches the prohibit route and is refused. TimescaleDB is published only on `127.0.0.1:5435`.

The message crosses at QoS 1 on `plant-01/area-01/<asset_id>/telemetry`. The ETL subscribes to `+/+/+/telemetry`.

| Level | Example | What it is |
| --- | --- | --- |
| 1 | `plant-01` | `assets.plant` |
| 2 | `area-01` | `assets.area` |
| 3 | `critical-pump-01` | `assets.asset_id`. The body carries the same `asset_id` |
| 4 | `telemetry` | Message class |

The topic's plant and area have to match the `assets` row. A message that breaks the contract is published on the topic `rejected` and stored in `rejected_messages`.

## Decision

The accepted boundary is this one: OT and IT meet only at the broker. The accepted topic is a short namespace of three equipment levels and a message class.

`plant` and `area` are the `assets` columns. The third level is the asset. `telemetry` does not name a piece of equipment: it names the class. `rejected` does not end in `/telemetry`, so the ETL does not read its own rejection again.

ISA-95 is the reference for putting the hierarchy in the name. The enterprise would sit above the plant. The registry and the topic start at the plant.

Sparkplug B is a different namespace, `spBv1.0/group/message_type/edge_node/device`, with birth and death messages. This lab publishes contract v1 JSON. With no death message, an asset with no usable readings in the last minute is `stale` in `asset_condition`.

These limits stay lab limits:

- There is one MQTT account. `allow_anonymous false`, and there is no ACL. Whoever has `MQTT_USER` and `MQTT_PASSWORD` can publish and subscribe to any topic.
- Port `1883` is published on the host. TimescaleDB listens on `127.0.0.1:5435`.
- `rejected` is a flat topic.
- The optional OPC UA path uses security mode `None`, the mode of the lab simulator.

The compose file, the flows, and the topics stay as they are.

## Consequences

- An open ingestion editor cannot reach TimescaleDB by the name `timescaledb` or by an `it-net` address inside `172.16.0.0/12`. With the MQTT account it can publish to any topic.
- A device that stops publishing becomes `stale` when the last minute has no usable readings.
- A new plant or area is a row in `assets` and two segments of the topic. A fifth level changes the `+/+/+/telemetry` subscription and the topic split in the ETL.
- Sparkplug B is named and not implemented.
