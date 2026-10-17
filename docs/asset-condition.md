# Condición de activos

[English](asset-condition.en.md)

TimescaleDB clasifica cada activo crítico como `normal`, `warning`, `alarm` o `stale`. Todo vive en `timescaledb/init/002_asset_condition.sql`: una tabla con los límites de ingeniería y una vista que compara las lecturas recientes con esos límites.

## Límites: `asset_limits`

Una fila por activo y señal. Un límite vacío (`NULL`) significa que no aplica.

| Activo | Señal | Unidad | Alarm bajo | Warning bajo | Warning alto | Alarm alto | Referencia |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `critical-pump-01` | temperature | °C | — | — | 80 | 90 | lab default |
| `critical-pump-01` | pressure | bar | 1.5 | 2.0 | 3.0 | 3.5 | lab default |
| `critical-pump-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-compressor-01` | temperature | °C | — | — | 95 | 105 | lab default |
| `critical-compressor-01` | pressure | bar | 4.5 | 5.0 | 7.0 | 7.5 | lab default |
| `critical-compressor-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |
| `critical-motor-01` | temperature | °C | — | — | 80 | 90 | lab default |
| `critical-motor-01` | vibration | mm/s | — | — | 2.8 | 4.5 | ISO 10816-3 |

- Solo la presión tiene límites bajos: una presión que cae indica pérdida de cebado o cavitación en la bomba, o una fuga en el compresor.
- `critical-motor-01` no tiene fila de presión a propósito. Un motor no tiene presión de proceso; la señal se guarda, pero no se evalúa.
- La vibración usa los límites de ISO 10816-3 para máquinas medianas sobre base rígida. Los demás son valores de laboratorio; en planta saldrían de la hoja de datos del fabricante y del historial de la máquina.

La base rechaza una fila si la señal no es `temperature`, `pressure` o `vibration`, si no tiene ningún límite, o si los límites están desordenados (por ejemplo, un warning alto mayor que el alarm alto).

## Vista: `asset_condition`

Devuelve una fila por cada activo que tiene límites. Así un activo sin datos sigue apareciendo, en lugar de desaparecer.

Reglas:

1. Cada señal se evalúa con el **promedio del último minuto**, no con la última lectura, para que el ruido cerca de un umbral no haga saltar el estado (flapping).
2. `alarm` si el promedio llega a un límite de alarma, alto o bajo; `warning` si llega a uno de warning; si no, `normal`. Los límites son inclusivos: llegar exactamente a 2.8 ya es `warning`.
3. Una señal sin fila de límites no se evalúa y su estado queda vacío.
4. `condition` es el peor estado entre las señales del activo.
5. Si el activo no tiene lecturas en el último minuto, `condition` es `stale` y `last_seen` muestra cuándo llegó su último dato.

| Columna | Contenido |
| --- | --- |
| `asset_id` | Activo |
| `condition` | `normal`, `warning`, `alarm` o `stale` |
| `temperature_avg`, `pressure_avg`, `vibration_avg` | Promedio del último minuto |
| `temperature_state`, `pressure_state`, `vibration_state` | Estado de cada señal |
| `samples_1m` | Lecturas en el último minuto (unas 12 con un envío cada 5 s) |
| `last_seen` | Hora de la última lectura, sin importar su antigüedad |
| `evaluated_at` | Momento del cálculo; la vista no guarda nada y recalcula en cada consulta |

## Consultar

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, condition, vibration_avg, vibration_state, samples_1m, last_seen FROM asset_condition;"'
```

Las comillas simples hacen que `$POSTGRES_USER` y `$POSTGRES_DB` se lean dentro del contenedor, que ya los tiene definidos.

## Aplicar el script en una base existente

Los scripts de `/docker-entrypoint-initdb.d/` solo se ejecutan cuando la base está vacía. En una base que ya existe, el script se aplica a mano:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/020_asset_condition.sql'
```

El script es idempotente: se puede ejecutar varias veces y siempre deja el mismo resultado, sin filas duplicadas. Tiene dos límites:

- `CREATE TABLE IF NOT EXISTS` no modifica una tabla que ya existe. Una columna o regla nueva en `asset_limits` necesita un `ALTER TABLE`.
- `CREATE OR REPLACE VIEW` solo puede agregar columnas al final. Para renombrar o reordenar columnas hay que ejecutar `DROP VIEW asset_condition` antes.

## Cambiar un umbral

Edita el valor en el `INSERT` de `002_asset_condition.sql` y vuelve a aplicar el script. `ON CONFLICT ... DO UPDATE` actualiza la fila existente.

Un `UPDATE` directo en la base también funciona, pero deja el archivo y la base con valores distintos. El archivo es la fuente de verdad: una instalación nueva tomará lo que diga el archivo.

## Comprobación

1. La consulta devuelve tres filas.
2. Reinicia el ciclo del motor con `docker compose restart modbus-slave` y consulta de nuevo en estos momentos:

   | Minuto del ciclo | `condition` de `critical-motor-01` |
   | --- | --- |
   | 0–8 | `normal` |
   | ~8.3 | `warning` |
   | ~10 | `alarm` |
   | ~13.1 | `warning`, durante unos 25 s |
   | ~13.5 | `normal` |

   Cada cambio llega unos 30 s después de que la lectura cruza el umbral, por el promedio de un minuto. Por la misma razón, al bajar después del mantenimiento el motor pasa brevemente por `warning`.

3. La bomba y el compresor siguen en `normal` durante todo el ciclo.
4. Detén el slave con `docker compose stop modbus-slave`. Un minuto después, el motor queda en `stale` con `samples_1m = 0`. Para volver, ejecuta `docker compose start modbus-slave` y después `docker compose restart node-red-ingestion`. Ver la nota de reconexión en [modbus-tcp.md](modbus-tcp.md).
