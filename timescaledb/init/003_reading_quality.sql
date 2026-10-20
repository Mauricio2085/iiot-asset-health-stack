-- Safe to run more than once: init applies it to new databases, and existing
-- databases get it by hand with psql.

-- Quality follows the OPC UA levels. The ETL already rejects anything else;
-- this keeps direct inserts to the same vocabulary.
-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sensor_readings_quality_check'
    ) THEN
        ALTER TABLE sensor_readings ADD CONSTRAINT sensor_readings_quality_check
            CHECK (quality IN ('good', 'uncertain', 'bad'));
    END IF;
END
$$;

-- 'unknown' is outside the vocabulary, so it can no longer be the default:
-- every reading has to state its quality.
ALTER TABLE sensor_readings ALTER COLUMN quality DROP DEFAULT;
