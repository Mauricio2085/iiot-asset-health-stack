# Mensajes rechazados

[English](rejected-messages.en.md)

Un mensaje que no cumple el contrato no entra en `sensor_readings`. El ETL lo publica en el tópico MQTT `rejected` y guarda una fila en `rejected_messages`. El tópico es la cola para verlo en vivo. La tabla es el conteo y el historial.

El script está en `timescaledb/init/006_rejected_messages.sql`.

## Qué se rechaza

| Razón | Cuándo |
| --- | --- |
| `payload is not a JSON object` | El cuerpo no es un objeto |
| `asset_id does not match topic` | El `asset_id` no es el tercer segmento del tópico |
| `temperature is not a number`, y lo mismo para `pressure` y `vibration` | La señal no es un número finito |
| `ts is not a valid timestamp` | `ts` no es una fecha |
| `quality is not good, uncertain or bad` | Falta `quality` o trae otro valor |
| `asset_id is not in the asset registry` | El activo no está en `assets` |
| `plant or area does not match the asset registry` | La planta o el área del tópico no son las de esa fila |

Una fila es un mensaje. Si falla por tres razones, `errors` tiene tres textos y el conteo de mensajes sube en uno.

`rejected` no termina en `/telemetry`, así que el ETL no vuelve a leer su propio rechazo. Una caída de Timescale sigue viéndose solo en el debug del editor: esta tabla guarda violaciones del contrato.

## Tabla: `rejected_messages`

| Columna | Contenido |
| --- | --- |
| `rejected_at` | Hora en que el ETL lo descartó |
| `topic` | Tópico original |
| `errors` | Lista de razones |
| `payload` | Cuerpo original. Si no era un objeto, queda en `payload.unparsed` |

## Consultar

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) AS messages FROM rejected_messages;"'
```

El conteo por razón:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT reason, count(*) FROM rejected_messages, unnest(errors) AS reason GROUP BY reason ORDER BY count(*) DESC;"'
```

Para verlos llegar:

```bash
docker compose exec mosquitto sh -c 'mosquitto_sub -h localhost -u "$MQTT_USER" -P "$MQTT_PASSWORD" -t rejected -v'
```

## Aplicar el script en una base existente

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/060_rejected_messages.sql'
```

`docker compose up -d timescaledb` hace falta para que el contenedor vea un script recién montado. El script se puede ejecutar varias veces. Después hay que reiniciar el ETL para que tome el flujo nuevo: `docker compose restart node-red-etl`.

## Comprobación

1. Un mensaje con `quality` fuera de la lista no aparece en `sensor_readings`.
2. Ese mensaje aparece una vez en `rejected_messages`, con todas sus razones en `errors`, y también llega a `mosquitto_sub -t rejected` con `MQTT_USER`.
3. Un `asset_id` que no está en `assets` hace lo mismo.
4. Una lectura válida de los tres activos no agrega fila en `rejected_messages`.
