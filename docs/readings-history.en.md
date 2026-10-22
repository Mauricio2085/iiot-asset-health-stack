# Reading history

[Español](readings-history.md)

Timescale keeps two layers. `sensor_readings` holds every 5-second point. `sensor_readings_1m` holds one clock minute per asset. The live condition and the 15-minute dashboard keep reading the raw table. The aggregate is what remains after that point ages out.

The script is `timescaledb/init/005_readings_history.sql`. It uses `psql` conditionals, so it is applied with `psql -f`.

## Aggregate: `sensor_readings_1m`

One row per asset, plant, area, and clock minute. The minute is the clock minute (16:14:00–16:15:00), not the rolling last 60 seconds that `asset_condition` uses.

| Column | Contents |
| --- | --- |
| `bucket` | Start of the minute |
| `asset_id`, `plant`, `area` | Asset and the hierarchy the topic carried |
| `temperature_avg`, `pressure_avg`, `vibration_avg` | Average of readings whose `quality` is not `bad` |
| `samples` | Readings that arrived in that minute, including `bad` ones |
| `uncertain` | How many were `uncertain` |
| `bad` | How many were `bad` |

A `bad` reading does not move the average, and it does increase `bad`. An `uncertain` reading is included in the average and counted. This is the same rule as the condition view.

The aggregate refreshes every minute, from one hour ago to one minute ago. The minute that is still receiving points stays out until it is a minute old. A query of the aggregate does not fill that gap from the raw table.

## Compression

`sensor_readings` chunks older than one day are compressed, segmented by `asset_id` and ordered by time. The chunk that is still taking inserts stays as rows. Queries stay the same: Timescale reads the compressed chunk and returns the same rows.

The job runs every hour. When the script is applied, chunks that are already a day old are compressed then.

## Retention

A raw chunk is dropped when its end is more than 7 days old. The job runs every hour, so the chunk goes on the first pass after it reaches that age. The aggregate has no horizon: those minutes stay in `sensor_readings_1m`.

The October 14 chunk ends at 19:00 Bogotá time and turns 7 days old on October 21 at that hour. The next pass is one hour after the previous one: the 18:51 pass was early, and the 19:51 pass drops it.

Applying the script again refreshes only the span that still has raw rows. A refresh of the whole history, after that drop, would clear the minutes whose raw point is already gone.

## Query

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT bucket, asset_id, vibration_avg, samples, uncertain, bad FROM sensor_readings_1m WHERE bucket > now() - make_interval(mins => 15) ORDER BY bucket DESC, asset_id;"'
```

## Applying the script to an existing database

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/050_readings_history.sql'
```

`docker compose up -d timescaledb` is required so the container sees a newly mounted script. The script can be run more than once.

## Check

1. `sensor_readings_1m` has rows for the three assets.
2. In a minute that contains `bad` readings, `bad` matches the raw table and the average leaves them out.
3. Chunks older than one day show `is_compressed = true`. The one that closed less than a day ago, and the one still open, stay `false`.
4. Three jobs exist: aggregate refresh, compression, and retention.
5. The raw row count does not fall when the script is applied. The first chunk to go is the October 14 one, on the 21st at the 19:51 pass.
