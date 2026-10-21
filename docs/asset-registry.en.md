# Asset registry

[Español](asset-registry.md)

The plant hierarchy lives in the `assets` table: one row per asset, with plant, area, type, and criticality. The MQTT topic is still the address of the message. The registry confirms that the address exists.

The script is `timescaledb/init/004_assets.sql`.

## Table: `assets`

| Asset                    | Plant     | Area     | Type         | Criticality |
| ------------------------ | --------- | -------- | ------------ | ----------- |
| `critical-pump-01`       | `plant-01` | `area-01` | `pump`       | `critical`  |
| `critical-compressor-01` | `plant-01` | `area-01` | `compressor` | `critical`  |
| `critical-motor-01`      | `plant-01` | `area-01` | `motor`      | `critical`  |

Plant and area are free text: a new site is a new row. Type and criticality are closed lists.

- `asset_type`: `pump`, `compressor`, `motor`.
- `criticality`: `critical`, `standard`. The three lab assets are `critical`. `standard` is there for an asset whose failure does not stop the plant.

`sensor_readings` and `asset_limits` reference `assets`. `ON DELETE RESTRICT` and `ON UPDATE RESTRICT` refuse a delete or a rename of an asset that already has readings or limits.

## What the ETL checks

After the payload rules (topic, signals, `ts`, and `quality`), the ETL looks up `asset_id` in `assets`.

| Case | Rejection reason |
| --- | --- |
| The asset is not in the registry | `asset_id is not in the asset registry` |
| The topic plant or area differs from the row | `plant or area does not match the asset registry` |

When they match, the reading is stored with the plant and area from the topic. Those `sensor_readings` columns keep the same source: they are written only when the registry agrees.

The foreign key covers a direct insert of an unknown `asset_id`. A direct insert of a known asset can still store a different plant: that comparison lives in the ETL, not in the database.

## Query

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, plant, area, asset_type, criticality FROM assets ORDER BY asset_id;"'
```

## Applying the script to an existing database

Scripts in `/docker-entrypoint-initdb.d/` run only when the database is empty. On a database that already exists:

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/040_assets.sql'
```

`docker compose up -d timescaledb` is required so the container sees a newly mounted script. The script can be run more than once: it updates the three rows and does not create the keys again when they already exist.

A new asset is added in the script's `INSERT` and the script is applied again. Until that row exists, the ETL rejects its messages.

## Check

1. The query returns the three rows in the table above.
2. A message with an unknown `asset_id` does not show up in `sensor_readings`.
3. A `critical-pump-01` message published on `plant-99/area-01/...` does not show up either.
4. `DELETE FROM assets WHERE asset_id = 'critical-pump-01'` fails on the foreign key.
5. Readings from the three assets keep arriving.
