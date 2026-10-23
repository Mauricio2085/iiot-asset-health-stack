# Mediciones anchas y estrechas

[English](adr-measurements.en.md)

Estado: aceptada. 2026-10-22.

## Contexto

Cada lectura es una fila de `sensor_readings`. Las tres señales viven en columnas porque el laboratorio nació de un solo mensaje MQTT: tres números y una calidad. Con eso, la condición, el margen consumido, la calidad y `stale` se calcularon nombrando columnas, y cada tendencia de Grafana es una consulta por señal. El ETL, el SQL y el tablero no pivotan datos.

| Columna | Contenido |
| --- | --- |
| `time` | `ts` del mensaje |
| `plant`, `area` | Planta y área del tópico, después de coincidir con `assets` |
| `asset_id` | Activo |
| `temperature`, `pressure`, `vibration` | Tres señales fijas |
| `quality` | Un valor para las tres |

`asset_limits` ya es estrecha: una fila por `asset_id` y `signal`, con unidad y umbrales. `assets` guarda planta, área, tipo y criticidad.

El modelo ancho se queda corto en cuatro sitios:

- `critical-motor-01` guarda `pressure` y no tiene fila de umbral para esa señal. Una columna fija no sigue el modo de falla: un motor no tiene presión de proceso que evaluar.
- `quality` es una por mensaje. Cuando el transmisor de vibración del motor marca `bad`, la temperatura y la presión de esa lectura también quedan `bad`.
- Una señal nueva pide cambiar `sensor_readings`, `sensor_readings_1m`, `asset_condition` y los paneles.
- El join con `asset_limits` tiene que nombrar la columna (`vibration`, `temperature` o `pressure`).

## Decisión

El destino es una fila por activo, señal y tiempo.

| Columna | Contenido |
| --- | --- |
| `time` | Instante de la medición |
| `asset_id` | Activo |
| `signal` | Nombre de la señal, el mismo que `asset_limits.signal` |
| `value` | El número |
| `quality` | Calidad de esa señal |

Planta y área siguen en `assets`. Unidad y umbrales siguen en `asset_limits`.

`sensor_readings` sigue siendo el almacén. Las tablas, los flujos y el tablero quedan como están.

El JSON de hoy es el contrato v1. No lleva campo de versión:

```json
{
  "asset_id": "critical-pump-01",
  "ts": "2026-10-15T21:00:00.000Z",
  "temperature": 70.2,
  "pressure": 2.4,
  "vibration": 1.1,
  "quality": "good"
}
```

v1 se sigue aceptando durante la migración. Un ETL posterior parte un mensaje en tres filas y copia esa única calidad en las tres. El contrato v2 es el que podrá traer una calidad por señal. El simulador y el flujo siguen publicando v1.

## Consecuencias

- El demo, `sensor_readings_1m`, `asset_condition` y las tendencias de Grafana siguen leyendo las tres columnas.
- Un sensor `bad` sigue marcando las otras dos señales de esa lectura.
- Una señal nueva sigue pidiendo un cambio de esquema mientras la tabla ancha sea el almacén. En el destino, la medición nueva es una fila. `asset_limits` todavía cierra `signal` a `temperature`, `pressure` y `vibration`, así que un cuarto nombre abre ese `CHECK` y agrega su fila de umbrales.
- La migración —tabla nueva, relleno del historial, agregado de un minuto y paneles— queda fuera de este texto.
- v2 queda nombrado y sin implementar.
