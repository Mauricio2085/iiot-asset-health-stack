CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS sensor_readings (
    time        TIMESTAMPTZ      NOT NULL,
    plant       TEXT             NOT NULL,
    area        TEXT             NOT NULL,
    asset_id    TEXT             NOT NULL,
    temperature DOUBLE PRECISION,
    pressure    DOUBLE PRECISION,
    vibration   DOUBLE PRECISION,
    quality     TEXT             NOT NULL DEFAULT 'unknown'
);

SELECT create_hypertable(
    'sensor_readings',
    by_range('time', INTERVAL '1 day'),
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS sensor_readings_asset_time_idx
    ON sensor_readings (asset_id, time DESC);