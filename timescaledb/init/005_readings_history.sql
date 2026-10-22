-- Historian policies for sensor_readings.
-- Safe to run more than once with psql -f. The \if commands are psql syntax,
-- so this file is not meant to be pasted into a query window.
--
-- The 1-minute aggregate keeps a clock minute per asset after the raw point
-- is gone. Refresh only the span that still has raw rows: refreshing a window
-- whose raw chunks were already dropped would erase those minutes.
-- asset_condition and the live dashboard keep reading sensor_readings.

SELECT EXISTS (
    SELECT 1
    FROM timescaledb_information.continuous_aggregates
    WHERE view_schema = 'public'
      AND view_name = 'sensor_readings_1m'
) AS cagg_exists \gset

\if :cagg_exists
\else
CREATE MATERIALIZED VIEW sensor_readings_1m
WITH (timescaledb.continuous, timescaledb.materialized_only = true) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    asset_id,
    plant,
    area,
    avg(temperature) FILTER (WHERE quality <> 'bad') AS temperature_avg,
    avg(pressure)    FILTER (WHERE quality <> 'bad') AS pressure_avg,
    avg(vibration)   FILTER (WHERE quality <> 'bad') AS vibration_avg,
    count(*)                                     AS samples,
    count(*) FILTER (WHERE quality = 'uncertain') AS uncertain,
    count(*) FILTER (WHERE quality = 'bad')       AS bad
FROM sensor_readings
GROUP BY time_bucket('1 minute', time), asset_id, plant, area
WITH NO DATA;
\endif

SELECT min(time) AS refresh_start FROM sensor_readings \gset

\if :{?refresh_start}
CALL refresh_continuous_aggregate(
    'sensor_readings_1m',
    :'refresh_start'::timestamptz,
    now() - INTERVAL '1 minute'
);
\endif

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.hypertables
        WHERE hypertable_schema = 'public'
          AND hypertable_name = 'sensor_readings'
          AND compression_enabled
    ) THEN
        ALTER TABLE sensor_readings SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'asset_id',
            timescaledb.compress_orderby = 'time DESC'
        );
    END IF;
END
$$;

-- Closed daily chunks only. The chunk still receiving inserts stays as rows.
SELECT compress_chunk(format('%I.%I', chunk_schema, chunk_name)::regclass)
FROM timescaledb_information.chunks
WHERE hypertable_name = 'sensor_readings'
  AND NOT is_compressed
  AND range_end < now() - INTERVAL '1 day';

SELECT add_compression_policy(
    'sensor_readings',
    compress_after => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

SELECT add_retention_policy(
    'sensor_readings',
    drop_after => INTERVAL '7 days',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- The open minute stays out of the aggregate until it is a minute old.
SELECT add_continuous_aggregate_policy(
    'sensor_readings_1m',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);
