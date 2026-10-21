-- Safe to run more than once: init applies it to new databases, and existing
-- databases get it by hand with psql.
--
-- The asset registry is the hierarchy. Plant and area on a reading are still
-- taken from the MQTT topic, and the ETL rejects the message when they
-- disagree with this table.

CREATE TABLE IF NOT EXISTS assets (
    asset_id    TEXT NOT NULL PRIMARY KEY,
    plant       TEXT NOT NULL,
    area        TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    criticality TEXT NOT NULL,
    CONSTRAINT assets_type_check
        CHECK (asset_type IN ('pump', 'compressor', 'motor')),
    CONSTRAINT assets_criticality_check
        CHECK (criticality IN ('critical', 'standard'))
);

INSERT INTO assets (asset_id, plant, area, asset_type, criticality)
VALUES
    ('critical-pump-01',       'plant-01', 'area-01', 'pump',       'critical'),
    ('critical-compressor-01', 'plant-01', 'area-01', 'compressor', 'critical'),
    ('critical-motor-01',      'plant-01', 'area-01', 'motor',      'critical')
ON CONFLICT (asset_id) DO UPDATE SET
    plant       = EXCLUDED.plant,
    area        = EXCLUDED.area,
    asset_type  = EXCLUDED.asset_type,
    criticality = EXCLUDED.criticality;

-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS.
-- ON DELETE RESTRICT keeps history when someone removes a registry row.
-- ON UPDATE RESTRICT keeps the asset id stable for that same history.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sensor_readings_asset_id_fkey'
    ) THEN
        ALTER TABLE sensor_readings
            ADD CONSTRAINT sensor_readings_asset_id_fkey
            FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'asset_limits_asset_id_fkey'
    ) THEN
        ALTER TABLE asset_limits
            ADD CONSTRAINT asset_limits_asset_id_fkey
            FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
            ON DELETE RESTRICT
            ON UPDATE RESTRICT;
    END IF;
END
$$;
