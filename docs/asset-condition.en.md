# Asset condition

[Español](asset-condition.md)

TimescaleDB classifies each critical asset as `normal`, `warning`, `alarm`, or `stale`. Everything lives in `timescaledb/init/002_asset_condition.sql`: a table with the engineering limits and a view that compares recent readings against them.

## Limits: `asset_limits`

One row per asset and signal. An empty limit (`NULL`) means it does not apply.

| Asset | Signal | Unit | Alarm low | Warning low | Warning high | Alarm high | Reference |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `critical-pump-01` | temperature | °C | — | — | 80 | 90 | lab default |
| `critical-pump-01` | pressure | bar | 1.5 | 2.0 | 3.0 | 3.5 | lab default |
| `critical-pump-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-compressor-01` | temperature | °C | — | — | 95 | 105 | lab default |
| `critical-compressor-01` | pressure | bar | 4.5 | 5.0 | 7.0 | 7.5 | lab default |
| `critical-compressor-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-motor-01` | temperature | °C | — | — | 80 | 90 | lab default |
| `critical-motor-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |

- Only pressure has low limits: falling pressure points to loss of prime or cavitation in the pump, or a leak in the compressor.
- `critical-motor-01` has no pressure row on purpose. A motor has no process pressure; the signal is stored but not evaluated.
- Vibration uses the ISO 10816-3 limits for medium machines on rigid foundations. The rest are lab values; in a plant they would come from the manufacturer's datasheet and the machine's own history.

The database rejects a row when the signal is not `temperature`, `pressure`, or `vibration`, when it has no limit at all, or when the limits are out of order (for example, a high warning above the high alarm).

## View: `asset_condition`

Returns one row for every asset that has limits, so an asset with no data still shows up instead of disappearing.

Rules:

1. Each signal is judged on its **1-minute average**, not on the latest reading, so noise near a threshold does not make the state flap.
2. `alarm` when the average reaches an alarm limit, high or low; `warning` when it reaches a warning limit; otherwise `normal`. Limits are inclusive: exactly 2.8 is already `warning`.
3. A signal without a limits row is not evaluated and its state stays empty.
4. `condition` is the worst state among the asset's signals.
5. When the asset has no readings in the last minute, `condition` is `stale` and `last_seen` shows when its latest reading arrived.

| Column | Content |
| --- | --- |
| `asset_id` | Asset |
| `condition` | `normal`, `warning`, `alarm`, or `stale` |
| `temperature_avg`, `pressure_avg`, `vibration_avg` | 1-minute average |
| `temperature_state`, `pressure_state`, `vibration_state` | State of each signal |
| `samples_1m` | Readings in the last minute (about 12 at one every 5 s) |
| `last_seen` | Time of the latest reading, however old |
| `evaluated_at` | When the row was computed; the view stores nothing and recomputes on every query |

## Query

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, condition, vibration_avg, vibration_state, samples_1m, last_seen FROM asset_condition;"'
```

The single quotes make `$POSTGRES_USER` and `$POSTGRES_DB` expand inside the container, which already defines them.

## Applying the script to an existing database

Scripts in `/docker-entrypoint-initdb.d/` only run when the database is empty. On a database that already exists, apply the script by hand:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/020_asset_condition.sql'
```

The script is idempotent: it can run several times and always leaves the same result, with no duplicate rows. It has two limits:

- `CREATE TABLE IF NOT EXISTS` does not change a table that already exists. A new column or rule in `asset_limits` needs an `ALTER TABLE`.
- `CREATE OR REPLACE VIEW` can only append columns. Renaming or reordering columns needs `DROP VIEW asset_condition` first.

## Changing a threshold

Edit the value in the `INSERT` of `002_asset_condition.sql` and apply the script again. `ON CONFLICT ... DO UPDATE` updates the existing row.

A direct `UPDATE` in the database also works, but leaves the file and the database with different values. The file is the source of truth: a fresh install takes whatever the file says.

## Check

1. The query returns three rows.
2. Restart the motor cycle with `docker compose restart modbus-slave` and query again at these points:

   | Cycle minute | `condition` of `critical-motor-01` |
   | --- | --- |
   | 0–8 | `normal` |
   | ~8.3 | `warning` |
   | ~10 | `alarm` |
   | ~13.1 | `warning`, for about 25 s |
   | ~13.5 | `normal` |

   Each change arrives about 30 s after the reading crosses the threshold, because of the 1-minute average. For the same reason, the motor briefly passes through `warning` on the way down after maintenance.

3. The pump and the compressor stay `normal` for the whole cycle.
4. Stop the slave with `docker compose stop modbus-slave`. A minute later the motor is `stale` with `samples_1m = 0`. To recover, run `docker compose start modbus-slave` and then `docker compose restart node-red-ingestion`. See the reconnect note in [modbus-tcp.en.md](modbus-tcp.en.md).
