-- Safe to run more than once: init applies it to new databases, and existing
-- databases get it by hand with psql.
--
-- One row per message the ETL refused. The same message is published to the
-- MQTT topic "rejected". This is a normal table: rejects are rare, and the
-- count is a plain SELECT.

CREATE TABLE IF NOT EXISTS rejected_messages (
    rejected_at TIMESTAMPTZ NOT NULL,
    topic       TEXT        NOT NULL,
    errors      TEXT[]      NOT NULL,
    payload     JSONB       NOT NULL,
    CONSTRAINT rejected_messages_topic_check
        CHECK (topic <> ''),
    CONSTRAINT rejected_messages_errors_check
        CHECK (cardinality(errors) > 0)
);

CREATE INDEX IF NOT EXISTS rejected_messages_rejected_at_idx
    ON rejected_messages (rejected_at DESC);
