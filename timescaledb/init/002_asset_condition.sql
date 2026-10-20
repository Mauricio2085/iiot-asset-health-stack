-- Safe to run more than once: init applies it to new databases, and existing
-- databases get it by hand with psql.

CREATE TABLE IF NOT EXISTS asset_limits (
    asset_id     TEXT             NOT NULL,
    signal       TEXT             NOT NULL,
    unit         TEXT             NOT NULL,
    alarm_low    DOUBLE PRECISION,
    warning_low  DOUBLE PRECISION,
    warning_high DOUBLE PRECISION,
    alarm_high   DOUBLE PRECISION,
    reference    TEXT             NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (asset_id, signal),
    CONSTRAINT asset_limits_signal_check
        CHECK (signal IN ('temperature', 'pressure', 'vibration')),
    CONSTRAINT asset_limits_has_limit_check
        CHECK (num_nonnulls(alarm_low, warning_low, warning_high, alarm_high) > 0),
    CONSTRAINT asset_limits_low_order_check
        CHECK (alarm_low <= warning_low),
    CONSTRAINT asset_limits_high_order_check
        CHECK (warning_high <= alarm_high),
    CONSTRAINT asset_limits_band_check
        CHECK (warning_low < warning_high)
);

-- Columns added after the table first shipped go through ALTER TABLE, because
-- CREATE TABLE IF NOT EXISTS leaves an existing table untouched.
ALTER TABLE asset_limits ADD COLUMN IF NOT EXISTS nominal DOUBLE PRECISION;

-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'asset_limits_nominal_check'
    ) THEN
        ALTER TABLE asset_limits ADD CONSTRAINT asset_limits_nominal_check
            CHECK (nominal > warning_low AND nominal < warning_high);
    END IF;
END
$$;

-- critical-motor-01 has no pressure row on purpose: a motor has no process
-- pressure, so that signal is stored but never evaluated.
INSERT INTO asset_limits
    (asset_id, signal, unit, nominal, alarm_low, warning_low, warning_high, alarm_high, reference)
VALUES
    ('critical-pump-01',       'temperature', '°C',   70.0, NULL, NULL,  80.0,  90.0,  'lab default'),
    ('critical-pump-01',       'pressure',    'bar',  2.5,  1.5,  2.0,   3.0,   3.5,   'lab default'),
    ('critical-pump-01',       'vibration',   'mm/s', 1.0,  NULL, NULL,  2.8,   4.5,   'ISO 10816-3'),
    ('critical-compressor-01', 'temperature', '°C',   85.0, NULL, NULL,  95.0,  105.0, 'lab default'),
    ('critical-compressor-01', 'pressure',    'bar',  6.0,  4.5,  5.0,   7.0,   7.5,   'lab default'),
    ('critical-compressor-01', 'vibration',   'mm/s', 1.5,  NULL, NULL,  2.8,   4.5,   'ISO 10816-3'),
    ('critical-motor-01',      'temperature', '°C',   55.0, NULL, NULL,  80.0,  90.0,  'lab default'),
    ('critical-motor-01',      'vibration',   'mm/s', 0.8,  NULL, NULL,  2.8,   4.5,   'ISO 10816-3')
ON CONFLICT (asset_id, signal) DO UPDATE SET
    unit         = EXCLUDED.unit,
    nominal      = EXCLUDED.nominal,
    alarm_low    = EXCLUDED.alarm_low,
    warning_low  = EXCLUDED.warning_low,
    warning_high = EXCLUDED.warning_high,
    alarm_high   = EXCLUDED.alarm_high,
    reference    = EXCLUDED.reference;

-- One row per asset that has limits. Each signal is judged on its 1-minute
-- average; the asset condition is the worst signal state, or 'stale' when no
-- usable reading arrived in that minute. Limits are inclusive.
-- Readings with quality 'bad' are kept in sensor_readings but left out of the
-- averages; 'uncertain' ones are used and counted.
-- Limit usage is the share of the margin between nominal and the alarm limit
-- that the average has consumed: 0 % at nominal, 100 % or more in alarm.
-- CREATE OR REPLACE VIEW can only append columns: renaming or reordering
-- existing ones needs DROP VIEW first.
CREATE OR REPLACE VIEW asset_condition AS
WITH expected AS (
    SELECT DISTINCT asset_id
    FROM asset_limits
),
recent AS (
    SELECT asset_id,
           count(*)                                       AS samples_1m,
           count(*) FILTER (WHERE quality = 'uncertain')  AS uncertain_1m,
           count(*) FILTER (WHERE quality = 'bad')        AS bad_1m,
           CASE
               WHEN bool_or(quality = 'bad')       THEN 'bad'
               WHEN bool_or(quality = 'uncertain') THEN 'uncertain'
               ELSE 'good'
           END                                            AS data_quality,
           avg(temperature) FILTER (WHERE quality <> 'bad') AS temperature,
           avg(pressure)    FILTER (WHERE quality <> 'bad') AS pressure,
           avg(vibration)   FILTER (WHERE quality <> 'bad') AS vibration
    FROM sensor_readings
    WHERE time > now() - INTERVAL '1 minute'
    GROUP BY asset_id
),
evaluated AS (
    SELECT r.asset_id,
           v.signal,
           CASE
               WHEN v.value >= l.alarm_high   OR v.value <= l.alarm_low   THEN 'alarm'
               WHEN v.value >= l.warning_high OR v.value <= l.warning_low THEN 'warning'
               WHEN v.value IS NOT NULL                                   THEN 'normal'
           END AS state,
           CASE WHEN l.nominal IS NOT NULL AND v.value IS NOT NULL THEN
               GREATEST(
                   0,
                   (v.value - l.nominal) / NULLIF(l.alarm_high - l.nominal, 0),
                   (l.nominal - v.value) / NULLIF(l.nominal - l.alarm_low, 0)
               )
           END AS usage
    FROM recent r
    CROSS JOIN LATERAL (VALUES
        ('temperature', r.temperature),
        ('pressure',    r.pressure),
        ('vibration',   r.vibration)
    ) AS v (signal, value)
    JOIN asset_limits l
        ON l.asset_id = r.asset_id AND l.signal = v.signal
),
per_asset AS (
    SELECT asset_id,
           max(CASE state WHEN 'alarm' THEN 2 WHEN 'warning' THEN 1 WHEN 'normal' THEN 0 END) AS worst,
           max(state) FILTER (WHERE signal = 'temperature') AS temperature_state,
           max(state) FILTER (WHERE signal = 'pressure')    AS pressure_state,
           max(state) FILTER (WHERE signal = 'vibration')   AS vibration_state,
           (array_agg(signal ORDER BY usage DESC NULLS LAST))[1] AS worst_signal,
           max(usage) AS usage
    FROM evaluated
    GROUP BY asset_id
)
SELECT e.asset_id,
       CASE p.worst
           WHEN 2 THEN 'alarm'
           WHEN 1 THEN 'warning'
           WHEN 0 THEN 'normal'
           ELSE 'stale'
       END                              AS condition,
       round(r.temperature::numeric, 2) AS temperature_avg,
       p.temperature_state,
       round(r.pressure::numeric, 2)    AS pressure_avg,
       p.pressure_state,
       round(r.vibration::numeric, 2)   AS vibration_avg,
       p.vibration_state,
       COALESCE(r.samples_1m, 0)        AS samples_1m,
       last_reading.time                AS last_seen,
       now()                            AS evaluated_at,
       p.worst_signal,
       round((p.usage * 100)::numeric, 1) AS limit_usage_pct,
       -- Sources publish every 5 s, so a 1-minute window catches 11 or 12
       -- readings depending on timing; 11 already counts as full availability.
       round(LEAST(COALESCE(r.samples_1m, 0) * 100.0 / 11, 100), 0) AS data_availability_pct,
       COALESCE(r.uncertain_1m, 0)      AS uncertain_1m,
       COALESCE(r.bad_1m, 0)            AS bad_1m,
       r.data_quality
FROM expected e
LEFT JOIN recent r
    ON r.asset_id = e.asset_id
LEFT JOIN per_asset p
    ON p.asset_id = e.asset_id
LEFT JOIN LATERAL (
    SELECT s.time
    FROM sensor_readings s
    WHERE s.asset_id = e.asset_id
    ORDER BY s.time DESC
    LIMIT 1
) AS last_reading ON TRUE;
