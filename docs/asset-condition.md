# Condición de activos

[English](asset-condition.en.md)

TimescaleDB clasifica cada activo crítico como `normal`, `warning`, `alarm` o `stale`. Todo vive en `timescaledb/init/002_asset_condition.sql`: una tabla con los límites de ingeniería y una vista que compara las lecturas recientes con esos límites. El dashboard de Grafana lee ambas; ver [Dashboard](../README.md#dashboard).

## Límites: `asset_limits`

Una fila por activo y señal. Un límite vacío (`NULL`) significa que no aplica.

| Activo                   | Señal       | Unidad | Nominal | Alarm bajo | Warning bajo | Warning alto | Alarm alto | Referencia  |
| ------------------------ | ----------- | ------ | ------- | ---------- | ------------ | ------------ | ---------- | ----------- |
| `critical-pump-01`       | temperature | °C     | 70      | —          | —            | 80           | 90         | lab default |
| `critical-pump-01`       | pressure    | bar    | 2.5     | 1.5        | 2.0          | 3.0          | 3.5        | lab default |
| `critical-pump-01`       | vibration   | mm/s   | 1.0     | —          | —            | 2.8          | 4.5        | ISO 10816-3 |
| `critical-compressor-01` | temperature | °C     | 85      | —          | —            | 95           | 105        | lab default |
| `critical-compressor-01` | pressure    | bar    | 6.0     | 4.5        | 5.0          | 7.0          | 7.5        | lab default |
| `critical-compressor-01` | vibration   | mm/s   | 1.5     | —          | —            | 2.8          | 4.5        | ISO 10816-3 |
| `critical-motor-01`      | temperature | °C     | 55      | —          | —            | 80           | 90         | lab default |
| `critical-motor-01`      | vibration   | mm/s   | 0.8     | —          | —            | 2.8          | 4.5        | ISO 10816-3 |

- `nominal` es el valor de la señal en una máquina sana. Es el punto de partida del margen consumido (ver más abajo).
- Solo la presión tiene límites bajos: una presión que cae indica pérdida de cebado o cavitación en la bomba, o una fuga en el compresor.
- `critical-motor-01` no tiene fila de presión a propósito. Un motor no tiene presión de proceso; la señal se guarda, pero no se evalúa.
- La vibración usa los límites de ISO 10816-3 para máquinas medianas sobre base rígida. Los demás son valores de laboratorio; en planta saldrían de la hoja de datos del fabricante y del historial de la máquina.

La base rechaza una fila si la señal no es `temperature`, `pressure` o `vibration`, si no tiene ningún límite, si los límites están desordenados (por ejemplo, un warning alto mayor que el alarm alto) o si `nominal` queda fuera de la banda de warning.

## Vista: `asset_condition`

Devuelve una fila por cada activo que tiene límites. Así un activo sin datos sigue apareciendo, en lugar de desaparecer.

Reglas:

1. Cada señal se evalúa con el **promedio del último minuto**, no con la última lectura, para que el ruido cerca de un umbral no haga saltar el estado (flapping).
2. `alarm` si el promedio llega a un límite de alarma, alto o bajo; `warning` si llega a uno de warning; si no, `normal`. Los límites son inclusivos: llegar exactamente a 2.8 ya es `warning`.
3. Una señal sin fila de límites no se evalúa y su estado queda vacío.
4. `condition` es el peor estado entre las señales del activo.
5. Si el activo no tiene lecturas utilizables en el último minuto, `condition` es `stale` y `last_seen` muestra cuándo llegó su último dato.
6. Las lecturas con `quality = bad` se quedan en `sensor_readings`, pero no entran en los promedios ni en el margen consumido. Las `uncertain` se usan y se cuentan. Si todas las lecturas del último minuto son `bad`, no queda nada que evaluar y el activo es `stale`.

| Columna                                                  | Contenido                                                                       |
| -------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `asset_id`                                               | Activo                                                                          |
| `condition`                                              | `normal`, `warning`, `alarm` o `stale`                                          |
| `temperature_avg`, `pressure_avg`, `vibration_avg`       | Promedio del último minuto                                                      |
| `temperature_state`, `pressure_state`, `vibration_state` | Estado de cada señal                                                            |
| `samples_1m`                                             | Lecturas en el último minuto (11 o 12 con un envío cada 5 s, según el instante) |
| `last_seen`                                              | Hora de la última lectura, sin importar su antigüedad                           |
| `evaluated_at`                                           | Momento del cálculo; la vista no guarda nada y recalcula en cada consulta       |
| `worst_signal`                                           | Señal con mayor margen consumido                                                |
| `limit_usage_pct`                                        | Margen consumido por `worst_signal`                                             |
| `data_availability_pct`                                  | Lecturas del último minuto frente a las 11 esperadas, con tope en 100 %         |
| `uncertain_1m`                                           | Lecturas `uncertain` del último minuto                                          |
| `bad_1m`                                                 | Lecturas `bad` que quedaron fuera en el último minuto                           |
| `data_quality`                                           | La peor calidad del último minuto: `good`, `uncertain` o `bad`                  |

### Margen consumido

`limit_usage_pct` responde "¿qué tan cerca está este activo de una alarma?" con un número que significa lo mismo para cualquier señal y unidad. Es la parte del margen entre `nominal` y el límite de alarma que el promedio del último minuto ya consumió:

```text
límite alto:  (promedio − nominal) / (alarm_high − nominal)
límite bajo:  (nominal − promedio) / (nominal − alarm_low)
```

Se queda el mayor de los dos, y nunca baja de 0.

| Caso                                                                            | Margen consumido |
| ------------------------------------------------------------------------------- | ---------------- |
| Bomba a 70.1 °C (nominal 70, alarma 90)                                         | 0.5 %            |
| Vibración del motor en 2.8 mm/s, el límite de warning (nominal 0.8, alarma 4.5) | 54 %             |
| Presión de la bomba en 1.65 bar (nominal 2.5, alarma baja 1.5)                  | 85 %             |
| Vibración del motor en 5.0 mm/s (alarma 4.5)                                    | 114 %            |

Por encima de 100 %, la señal ya pasó su límite de alarma, y el número dice por cuánto. No tiene tope, así que dos activos en alarma se pueden seguir distinguiendo.

Medir desde `nominal` y no desde cero importa: una bomba sana a 70 °C con alarma en 90 °C está al 78 % "del límite", pero casi no ha consumido margen.

### Disponibilidad de datos

Las fuentes publican cada 5 s, así que una ventana de un minuto atrapa 11 o 12 lecturas según el instante exacto de la consulta. Con 11 ya cuenta como 100 %, para que una fuente sana no muestre 92 %. Un problema real de comunicación se sigue viendo: 6 lecturas dan 55 % y ninguna da 0 %.

La disponibilidad cuenta todas las lecturas que llegaron, sea cual sea su calidad: mide comunicación, no confianza.

### Calidad de los datos

Tres ideas responden preguntas distintas:

| Concepto       | Pregunta                          | Quién lo sabe                               |
| -------------- | --------------------------------- | ------------------------------------------- |
| Condición      | ¿La máquina está sana?            | La base, comparando con los límites         |
| Disponibilidad | ¿Llegaron las lecturas?           | La base, contando lecturas                  |
| Calidad        | ¿Se puede confiar en este número? | La fuente: el sensor, el equipo o el driver |

Cada lectura lleva `quality`, con los tres niveles de OPC UA: `good`, `uncertain` o `bad`. La fuente la decide, el borde la traduce y la TI la valida:

- **Fuente.** El slave Modbus reporta un estado en HR3; el simulador MQTT hace de equipo y de borde a la vez y pone la calidad él mismo.
- **Borde.** Node-RED traduce el código de HR3 al vocabulario del contrato y convierte un código desconocido en `bad`.
- **TI.** El ETL rechaza un mensaje sin calidad o con una calidad fuera del vocabulario, y `sensor_readings_quality_check`, en `003_reading_quality.sql`, hace lo mismo con las inserciones directas.

El demo tiene un episodio por cada nivel anormal:

| Activo              | Cuándo                                     | Calidad     | Qué pasa                                                                                                                       |
| ------------------- | ------------------------------------------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `critical-motor-01` | Minuto 1:00–1:30 de su ciclo de 13 minutos | `bad`       | El transmisor de vibración se satura en 25 mm/s. Las lecturas quedan fuera, así que no hay falsa alarma                        |
| `critical-pump-01`  | 2 minutos de cada 10, desde el minuto 5    | `uncertain` | El sensor de temperatura marca 3 °C de más. Las lecturas se usan, así que el margen consumido sube un poco, y quedan señaladas |

La calidad es un solo valor por mensaje, así que cubre las tres señales a la vez: cuando un sensor falla, la fuente informa la peor calidad y las otras dos señales también la llevan. La calidad por señal queda escrita como destino en [adr-measurements.md](adr-measurements.md): una fila por señal, y esta tabla ancha sigue vigente.

## Consultar

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, condition, worst_signal, limit_usage_pct, data_availability_pct, last_seen FROM asset_condition;"'
```

Las comillas simples hacen que `$POSTGRES_USER` y `$POSTGRES_DB` se lean dentro del contenedor, que ya los tiene definidos.

## Aplicar el script en una base existente

Los scripts de `/docker-entrypoint-initdb.d/` solo se ejecutan cuando la base está vacía. En una base que ya existe, el script se aplica a mano:

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/020_asset_condition.sql'
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/030_reading_quality.sql'
```

Un script recién montado en `docker-compose.yaml` necesita antes `docker compose up -d timescaledb`, para que el contenedor lo vea.

Los dos scripts son idempotentes: cada uno se puede ejecutar varias veces y siempre deja el mismo resultado, sin filas duplicadas. Los cambios de esquema siguen estas reglas, para que una base nueva y una existente terminen iguales:

- `CREATE TABLE IF NOT EXISTS` no modifica una tabla que ya existe. Las columnas agregadas después van por `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, como `nominal`.
- PostgreSQL no tiene `ADD CONSTRAINT IF NOT EXISTS`. Las reglas nuevas van dentro de un bloque `DO` que primero revisa `pg_constraint`, como `asset_limits_nominal_check`.
- `CREATE OR REPLACE VIEW` solo puede agregar columnas al final. Para renombrar o reordenar columnas hay que ejecutar `DROP VIEW asset_condition` antes.

## Cambiar un umbral

Edita el valor en el `INSERT` de `002_asset_condition.sql` y vuelve a aplicar el script. `ON CONFLICT ... DO UPDATE` actualiza la fila existente, incluido `nominal`. Las líneas de límite del dashboard se mueven en el siguiente refresco.

Un `UPDATE` directo en la base también funciona, pero deja el archivo y la base con valores distintos. El archivo es la fuente de verdad: una instalación nueva tomará lo que diga el archivo.

## Comprobación

1. La consulta devuelve tres filas, con `data_availability_pct` en 100 para todos los activos.
2. Reinicia el ciclo del motor con `docker compose restart modbus-slave` y consulta de nuevo en estos momentos:
   | Minuto del ciclo | `condition` de `critical-motor-01` |
   | --- | --- |
   | 0–8 | `normal` |
   | ~8.3 | `warning` |
   | ~10 | `alarm` |
   | ~13.1 | `warning`, durante unos 25 s |
   | ~13.5 | `normal` |

   Cada cambio llega unos 30 s después de que la lectura cruza el umbral, por el promedio de un minuto. Por la misma razón, al bajar después del mantenimiento el motor pasa brevemente por `warning`.

3. La bomba y el compresor siguen en `normal` durante todo el ciclo, con un margen consumido cercano a 0 %, salvo mientras la temperatura de la bomba está `uncertain`.
4. Cerca de un minuto después del reinicio, el motor tiene `bad_1m` mayor que 0 y `data_quality = bad`, mientras `condition` sigue en `normal`.
5. Durante el episodio de calibración de la bomba, la bomba tiene `uncertain_1m` mayor que 0 y `data_quality = uncertain`.
6. Detén el slave con `docker compose stop modbus-slave`. Un minuto después, el motor queda en `stale` con `samples_1m = 0`. Para volver, ejecuta `docker compose start modbus-slave` y después `docker compose restart node-red-ingestion`. Ver la nota de reconexión en [modbus-tcp.md](modbus-tcp.md).
