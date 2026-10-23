# Rejected messages

[Español](rejected-messages.md)

A message that breaks the contract does not enter `sensor_readings`. The ETL publishes it on the MQTT topic `rejected` and stores one row in `rejected_messages`. The topic is the live queue. The table is the count and the history.

The script is `timescaledb/init/006_rejected_messages.sql`.

## What gets rejected

| Reason | When |
| --- | --- |
| `payload is not a JSON object` | The body is not an object |
| `asset_id does not match topic` | `asset_id` is not the third topic segment |
| `temperature is not a number`, and the same for `pressure` and `vibration` | The signal is not a finite number |
| `ts is not a valid timestamp` | `ts` is not a timestamp |
| `quality is not good, uncertain or bad` | `quality` is missing or has another value |
| `asset_id is not in the asset registry` | The asset is not in `assets` |
| `plant or area does not match the asset registry` | The topic plant or area differs from that row |

One row is one message. Three reasons leave three texts in `errors` and increase the message count by one.

`rejected` does not end in `/telemetry`, so the ETL does not read its own rejection again. A Timescale outage still shows only in the editor debug sidebar: this table holds contract violations.

## Table: `rejected_messages`

| Column | Contents |
| --- | --- |
| `rejected_at` | When the ETL refused it |
| `topic` | Original topic |
| `errors` | List of reasons |
| `payload` | Original body. When it was not an object, it is kept in `payload.unparsed` |

## Query

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) AS messages FROM rejected_messages;"'
```

Count by reason:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT reason, count(*) FROM rejected_messages, unnest(errors) AS reason GROUP BY reason ORDER BY count(*) DESC;"'
```

To watch them arrive:

```bash
docker compose exec mosquitto sh -c 'mosquitto_sub -h localhost -u "$MQTT_USER" -P "$MQTT_PASSWORD" -t rejected -v'
```

## Applying the script to an existing database

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/060_rejected_messages.sql'
```

`docker compose up -d timescaledb` is required so the container sees a newly mounted script. The script can be run more than once. Then restart the ETL so it loads the new flow: `docker compose restart node-red-etl`.

## Check

1. A message whose `quality` is outside the list does not show up in `sensor_readings`.
2. That message shows up once in `rejected_messages`, with every reason in `errors`, and it also arrives on `mosquitto_sub -t rejected` authenticated as `MQTT_USER`.
3. An `asset_id` that is not in `assets` does the same.
4. A valid reading from the three assets adds no row to `rejected_messages`.
