# Registro de activos

[English](asset-registry.en.md)

La jerarquía de la planta vive en la tabla `assets`: una fila por activo, con planta, área, tipo y criticidad. El tópico MQTT sigue siendo la dirección del mensaje. El registro confirma que esa dirección existe.

El script está en `timescaledb/init/004_assets.sql`.

## Tabla: `assets`

| Activo                   | Planta    | Área     | Tipo         | Criticidad |
| ------------------------ | --------- | -------- | ------------ | ---------- |
| `critical-pump-01`       | `plant-01` | `area-01` | `pump`       | `critical` |
| `critical-compressor-01` | `plant-01` | `area-01` | `compressor` | `critical` |
| `critical-motor-01`      | `plant-01` | `area-01` | `motor`      | `critical` |

Planta y área son texto libre: un sitio nuevo es una fila. Tipo y criticidad son listas cerradas.

- `asset_type`: `pump`, `compressor`, `motor`.
- `criticality`: `critical`, `standard`. Los tres activos del laboratorio son `critical`. `standard` queda disponible para un activo que no pare la planta.

`sensor_readings` y `asset_limits` apuntan a `assets` con clave foránea. `ON DELETE RESTRICT` y `ON UPDATE RESTRICT` impiden borrar o renombrar un activo que ya tiene lecturas o límites.

## Qué comprueba el ETL

Después de las reglas del payload (tópico, señales, `ts` y `quality`), el ETL busca el `asset_id` en `assets`.

| Caso | Razón del rechazo |
| --- | --- |
| El activo no está en el registro | `asset_id is not in the asset registry` |
| La planta o el área del tópico no son las de la fila | `plant or area does not match the asset registry` |

Si coinciden, la lectura se guarda con la planta y el área del tópico. Esas columnas de `sensor_readings` no cambian de origen: solo se escriben cuando el registro está de acuerdo.

La clave foránea cubre las inserciones directas de un `asset_id` desconocido. Una inserción directa de un activo conocido puede guardar otra planta: esa comparación vive en el ETL, no en la base.

## Consultar

```bash
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT asset_id, plant, area, asset_type, criticality FROM assets ORDER BY asset_id;"'
```

## Aplicar el script en una base existente

Los scripts de `/docker-entrypoint-initdb.d/` solo se ejecutan cuando la base está vacía. En una base que ya existe:

```bash
docker compose up -d timescaledb
docker compose exec -T timescaledb sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/040_assets.sql'
```

`docker compose up -d timescaledb` hace falta para que el contenedor vea un script recién montado. El script se puede ejecutar varias veces: actualiza las tres filas y no vuelve a crear las claves si ya existen.

Un activo nuevo se agrega en el `INSERT` del script y se vuelve a aplicar. Mientras no esté en `assets`, el ETL rechaza sus mensajes.

## Comprobación

1. La consulta devuelve las tres filas de la tabla de arriba.
2. Un mensaje con `asset_id` desconocido no aparece en `sensor_readings`.
3. Un mensaje de `critical-pump-01` publicado en `plant-99/area-01/...` tampoco aparece.
4. `DELETE FROM assets WHERE asset_id = 'critical-pump-01'` falla por la clave foránea.
5. Las lecturas de los tres activos siguen entrando.
