# Wide and narrow measurements

[Español](adr-measurements.md)

Status: accepted. 2026-10-22.

## Context

Each reading is one row of `sensor_readings`. The three signals live in columns because the lab started from a single MQTT message: three numbers and one quality. Condition, margin used, quality, and `stale` were calculated by naming columns, and each Grafana trend is one query per signal. The ETL, the SQL, and the dashboard do not pivot data.

| Column | Contents |
| --- | --- |
| `time` | Message `ts` |
| `plant`, `area` | Topic plant and area, after they match `assets` |
| `asset_id` | Asset |
| `temperature`, `pressure`, `vibration` | Three fixed signals |
| `quality` | One value for all three |

`asset_limits` is already narrow: one row per `asset_id` and `signal`, with its unit and limits. `assets` holds plant, area, type, and criticality.

The wide model stops short in four places:

- `critical-motor-01` stores `pressure` and has no limits row for that signal. A fixed column does not follow the failure mode: a motor has no process pressure to evaluate.
- `quality` is one value per message. When the motor's vibration transmitter reports `bad`, the temperature and pressure of that reading are `bad` too.
- A new signal means changing `sensor_readings`, `sensor_readings_1m`, `asset_condition`, and the panels.
- The join to `asset_limits` has to name the column (`vibration`, `temperature`, or `pressure`).

## Decision

The target is one row per asset, signal, and time.

| Column | Contents |
| --- | --- |
| `time` | Instant of the measurement |
| `asset_id` | Asset |
| `signal` | Signal name, the same value as `asset_limits.signal` |
| `value` | The number |
| `quality` | Quality of that signal |

Plant and area stay in `assets`. Units and limits stay in `asset_limits`.

`sensor_readings` stays the store. Tables, flows, and the dashboard stay as they are.

Today's JSON is contract v1. It has no version field:

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

v1 stays accepted during the migration. A later ETL splits one message into three rows and copies that single quality onto all three. Contract v2 is the one that can carry a quality per signal. The simulator and the flow keep publishing v1.

## Consequences

- The demo, `sensor_readings_1m`, `asset_condition`, and the Grafana trends keep reading the three columns.
- A `bad` sensor still marks the other two signals of that reading.
- A new signal still needs a schema change while the wide table is the store. On the target, the new measurement is a row. `asset_limits` still closes `signal` to `temperature`, `pressure`, and `vibration`, so a fourth name opens that `CHECK` and adds its limits row.
- The migration —a new table, history backfill, the minute aggregate, and the panels— stays outside this text.
- v2 is named and not implemented.
