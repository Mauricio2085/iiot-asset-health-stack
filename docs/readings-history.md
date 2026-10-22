# Historial de lecturas

[English](readings-history.en.md)

Timescale guarda dos capas. `sensor_readings` conserva cada punto de 5 segundos. `sensor_readings_1m` conserva un minuto de reloj por activo. La condición en vivo y el dashboard de 15 minutos siguen leyendo el crudo. El agregado es lo que queda cuando ese punto envejece.

El script está en `timescaledb/init/005_readings_history.sql`. Usa condicionales de `psql`, así que se aplica con `psql -f`.

## Agregado: `sensor_readings_1m`

Una fila por activo, planta, área y minuto de reloj. El minuto es el del reloj (16:14:00–16:15:00), no la ventana móvil de los últimos 60 segundos que usa `asset_condition`.

| Columna | Contenido |
| --- | --- |
| `bucket` | Inicio del minuto |
| `asset_id`, `plant`, `area` | Activo y la jerarquía que traía el tópico |
| `temperature_avg`, `pressure_avg`, `vibration_avg` | Promedio de las lecturas con `quality` distinto de `bad` |
| `samples` | Lecturas llegadas en ese minuto, incluidas las `bad` |
| `uncertain` | Cuántas fueron `uncertain` |
| `bad` | Cuántas fueron `bad` |

Una lectura `bad` no mueve el promedio y sí aumenta `bad`. Una `uncertain` entra en el promedio y se cuenta. Es el mismo criterio que la vista de condición.

El agregado se refresca cada minuto, desde hace una hora hasta hace un minuto. El minuto que todavía está recibiendo puntos queda fuera hasta que cumple un minuto de edad. Una consulta al agregado no rellena ese hueco con el crudo.

## Compresión

Los trozos de `sensor_readings` con más de un día se comprimen, agrupados por `asset_id` y ordenados por tiempo. El trozo que todavía recibe inserciones sigue en filas. Las consultas no cambian: Timescale lee el trozo comprimido y devuelve las mismas filas.

El job corre cada hora. Al aplicar el script, los trozos que ya cumplieron el día se comprimen en ese momento.

## Retención

Un trozo crudo se borra cuando su fin tiene más de 7 días. El job corre cada hora, así que el trozo cae en la primera pasada después de cumplir el plazo. El agregado no tiene plazo: esos minutos siguen en `sensor_readings_1m`.

El trozo del 14 de octubre termina a las 19:00 hora de Bogotá y cumple 7 días el 21 de octubre a esa hora. La pasada siguiente es una hora después de la anterior: la de las 18:51 llegó temprano, y la de las 19:51 lo borra.

Volver a aplicar el script refresca solo el tramo que todavía tiene crudo. Un refresco de toda la historia, después de esa borrada, dejaría vacíos los minutos cuyo punto ya no existe.

## Consultar

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT bucket, asset_id, vibration_avg, samples, uncertain, bad FROM sensor_readings_1m WHERE bucket > now() - make_interval(mins => 15) ORDER BY bucket DESC, asset_id;"'
```

## Aplicar el script en una base existente

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/050_readings_history.sql'
```

`docker compose up -d timescaledb` hace falta para que el contenedor vea un script recién montado. El script se puede ejecutar varias veces.

## Comprobación

1. `sensor_readings_1m` tiene filas de los tres activos.
2. En un minuto con lecturas `bad`, `bad` coincide con el crudo y el promedio no las incluye.
3. Los trozos con más de un día aparecen con `is_compressed = true`. El que cerró hace menos de un día, y el que sigue abierto, siguen en `false`.
4. Existen tres jobs: refresco del agregado, compresión y retención.
5. El número de filas crudas no baja al aplicar el script. El primer trozo que cae es el del 14 de octubre, el 21 en la pasada de las 19:51.
