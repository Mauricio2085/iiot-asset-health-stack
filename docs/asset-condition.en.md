# Asset condition

[Español](asset-condition.md)

TimescaleDB classifies each critical asset as `normal`, `warning`, `alarm`, or `stale`. Everything lives in `timescaledb/init/002_asset_condition.sql`: a table with the engineering limits and a view that compares recent readings against them. The Grafana dashboard reads both; see [Dashboard](../README.md#dashboard).

## Limits: `asset_limits`

One row per asset and signal. An empty limit (`NULL`) means it does not apply.

| Asset | Signal | Unit | Nominal | Alarm low | Warning low | Warning high | Alarm high | Reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `critical-pump-01` | temperature | °C | 70 | — | — | 80 | 90 | lab default |
| `critical-pump-01` | pressure | bar | 2.5 | 1.5 | 2.0 | 3.0 | 3.5 | lab default |
| `critical-pump-01` | vibration | mm/s | 1.0 | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-compressor-01` | temperature | °C | 85 | — | — | 95 | 105 | lab default |
| `critical-compressor-01` | pressure | bar | 6.0 | 4.5 | 5.0 | 7.0 | 7.5 | lab default |
| `critical-compressor-01` | vibration | mm/s | 1.5 | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-motor-01` | temperature | °C | 55 | — | — | 80 | 90 | lab default |
| `critical-motor-01` | vibration | mm/s | 0.8 | — | — | 2.8 | 4.5 | ISO 10816-3 |

- `nominal` is the value of the signal on a healthy machine. It is the starting point of the margin used (see below).
- Only pressure has low limits: falling pressure points to loss of prime or cavitation in the pump, or a leak in the compressor.
- `critical-motor-01` has no pressure row on purpose. A motor has no process pressure; the signal is stored but not evaluated.
- Vibration uses the ISO 10816-3 limits for medium machines on rigid foundations. The rest are lab values; in a plant they would come from the manufacturer's datasheet and the machine's own history.

The database rejects a row when the signal is not `temperature`, `pressure`, or `vibration`, when it has no limit at all, when the limits are out of order (for example, a high warning above the high alarm), or when `nominal` falls outside the warning band.

## View: `asset_condition`

Returns one row for every asset that has limits, so an asset with no data still shows up instead of disappearing.

Rules:

1. Each signal is judged on its **1-minute average**, not on the latest reading, so noise near a threshold does not make the state flap.
2. `alarm` when the average reaches an alarm limit, high or low; `warning` when it reaches a warning limit; otherwise `normal`. Limits are inclusive: exactly 2.8 is already `warning`.
3. A signal without a limits row is not evaluated and its state stays empty.
4. `condition` is the worst state among the asset's signals.
5. When the asset has no usable reading in the last minute, `condition` is `stale` and `last_seen` shows when its latest reading arrived.
6. Readings with `quality = bad` stay in `sensor_readings` but are left out of the averages and the margin used. `uncertain` readings are used and counted. If every reading of the last minute is `bad`, nothing is left to judge and the asset is `stale`.

| Column | Content |
| --- | --- |
| `asset_id` | Asset |
| `condition` | `normal`, `warning`, `alarm`, or `stale` |
| `temperature_avg`, `pressure_avg`, `vibration_avg` | 1-minute average |
| `temperature_state`, `pressure_state`, `vibration_state` | State of each signal |
| `samples_1m` | Readings in the last minute (11 or 12 at one every 5 s, depending on timing) |
| `last_seen` | Time of the latest reading, however old |
| `evaluated_at` | When the row was computed; the view stores nothing and recomputes on every query |
| `worst_signal` | Signal with the highest margin used |
| `limit_usage_pct` | Margin used by `worst_signal` |
| `data_availability_pct` | Readings in the last minute against the 11 expected, capped at 100 % |
| `uncertain_1m` | `uncertain` readings in the last minute |
| `bad_1m` | `bad` readings left out in the last minute |
| `data_quality` | Worst quality of the last minute: `good`, `uncertain`, or `bad` |

### Margin used

`limit_usage_pct` answers "how close is this asset to an alarm?" with one number that means the same for any signal and unit. It is the share of the margin between `nominal` and the alarm limit that the 1-minute average has already consumed:

```text
high limit:  (average − nominal) / (alarm_high − nominal)
low limit:   (nominal − average) / (nominal − alarm_low)
```

The larger of the two is kept, and it never goes below 0.

| Case | Margin used |
| --- | --- |
| Pump at 70.1 °C (nominal 70, alarm 90) | 0.5 % |
| Motor vibration at 2.8 mm/s, the warning limit (nominal 0.8, alarm 4.5) | 54 % |
| Pump pressure at 1.65 bar (nominal 2.5, low alarm 1.5) | 85 % |
| Motor vibration at 5.0 mm/s (alarm 4.5) | 114 % |

Above 100 % the signal is past its alarm limit, and the number tells by how much. It is not capped, so two assets in alarm can still be told apart.

Measuring from `nominal` instead of from zero matters: a healthy pump at 70 °C against a 90 °C alarm is 78 % "of the limit" but has used almost none of its margin.

### Data availability

Sources publish every 5 s, so a 1-minute window catches 11 or 12 readings depending on the exact query time. Eleven already counts as 100 %, so a healthy source does not show 92 %. A real communication problem still shows: 6 readings is 55 % and none is 0 %.

Availability counts every reading that arrived, whatever its quality: it measures communication, not trust.

### Data quality

Three ideas answer different questions:

| Concept | Question | Who knows |
| --- | --- | --- |
| Condition | Is the machine healthy? | The database, against the limits |
| Availability | Did the readings arrive? | The database, counting readings |
| Quality | Can this number be trusted? | The source: the sensor, the device, or the driver |

Every reading carries `quality`, with the three OPC UA levels: `good`, `uncertain`, or `bad`. The source decides it, the edge translates it, and IT validates it:

- **Source.** The Modbus slave reports a status in HR3; the MQTT simulator plays both device and edge and sets the quality itself.
- **Edge.** Node-RED maps the HR3 code to the contract vocabulary, and turns an unknown code into `bad`.
- **IT.** The ETL rejects a message whose quality is missing or outside the vocabulary, and `sensor_readings_quality_check` in `003_reading_quality.sql` does the same for direct inserts.

The demo has one episode per abnormal level:

| Asset | When | Quality | What happens |
| --- | --- | --- | --- |
| `critical-motor-01` | Minute 1:00–1:30 of its 13-minute cycle | `bad` | The vibration transmitter saturates at 25 mm/s. The readings are left out, so there is no false alarm |
| `critical-pump-01` | 2 minutes in every 10, from minute 5 | `uncertain` | The temperature sensor reads 3 °C high. The readings are used, so the margin used rises a little, and they are flagged |

Quality is one value per message, so it covers the three signals at once: when one sensor fails, the source reports the worst quality and the other two signals carry it too. Per-signal quality is the accepted target in [adr-measurements.en.md](adr-measurements.en.md): one row per signal, with this wide table still in force.

## Query

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, condition, worst_signal, limit_usage_pct, data_availability_pct, last_seen FROM asset_condition;"'
```

The single quotes make `$POSTGRES_USER` and `$POSTGRES_DB` expand inside the container, which already defines them.

## Applying the script to an existing database

Scripts in `/docker-entrypoint-initdb.d/` only run when the database is empty. On a database that already exists, apply the script by hand:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/020_asset_condition.sql'
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/030_reading_quality.sql'
```

A script that is newly mounted in `docker-compose.yaml` needs `docker compose up -d timescaledb` first, so the container sees it.

Both scripts are idempotent: each can run several times and always leaves the same result, with no duplicate rows. Schema changes follow these rules so that both new and existing databases end up the same:

- `CREATE TABLE IF NOT EXISTS` does not change a table that already exists. Columns added later go through `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, as `nominal` does.
- PostgreSQL has no `ADD CONSTRAINT IF NOT EXISTS`. New constraints go inside a `DO` block that checks `pg_constraint` first, as `asset_limits_nominal_check` does.
- `CREATE OR REPLACE VIEW` can only append columns. Renaming or reordering columns needs `DROP VIEW asset_condition` first.

## Changing a threshold

Edit the value in the `INSERT` of `002_asset_condition.sql` and apply the script again. `ON CONFLICT ... DO UPDATE` updates the existing row, `nominal` included. The dashboard limit lines move on the next refresh.

A direct `UPDATE` in the database also works, but leaves the file and the database with different values. The file is the source of truth: a fresh install takes whatever the file says.

## Check

1. The query returns three rows, with `data_availability_pct` at 100 for every asset.
2. Restart the motor cycle with `docker compose restart modbus-slave` and query again at these points:

   | Cycle minute | `condition` of `critical-motor-01` |
   | --- | --- |
   | 0–8 | `normal` |
   | ~8.3 | `warning` |
   | ~10 | `alarm` |
   | ~13.1 | `warning`, for about 25 s |
   | ~13.5 | `normal` |

   Each change arrives about 30 s after the reading crosses the threshold, because of the 1-minute average. For the same reason, the motor briefly passes through `warning` on the way down after maintenance.

3. The pump and the compressor stay `normal` for the whole cycle, with margin used near 0 %, except while the pump temperature is `uncertain`.
4. About one minute after the restart, the motor has `bad_1m` above 0 and `data_quality = bad`, while `condition` stays `normal`.
5. During the pump calibration episode, the pump has `uncertain_1m` above 0 and `data_quality = uncertain`.
6. Stop the slave with `docker compose stop modbus-slave`. A minute later the motor is `stale` with `samples_1m = 0`. To recover, run `docker compose start modbus-slave` and then `docker compose restart node-red-ingestion`. See the reconnect note in [modbus-tcp.en.md](modbus-tcp.en.md).
