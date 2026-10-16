# Modbus TCP

[English](modbus-tcp.en.md)

`modbus-slave` es la segunda fuente OT de este laboratorio. Es un servidor Modbus TCP con tres holding registers. `node-red-ingestion` los lee cada 5 segundos, aplica el escalado y publica el mismo contrato JSON de telemetría que el simulador MQTT, en un activo distinto para que ambas fuentes puedan correr a la vez.

## Mapa de registros

| Registro | Señal | Escalado | Ejemplo |
| --- | --- | --- | --- |
| HR0 | temperature | valor / 10 | `702` → `70.2` °C |
| HR1 | pressure | valor / 100 | `250` → `2.50` bar |
| HR2 | vibration | valor / 100 | `100` → `1.00` |

- Unit id: `1`
- Puerto en el contenedor: `502`
- Puerto en el host: `1502` (`localhost:1502` desde la máquina)
- El ruido suave es el mismo patrón que `mqtt-simulator` (seno lento más jitter pequeño)

## Contrato MQTT

Tópico: `plant-01/area-01/modbus-pump-01/telemetry` (QoS 1)

```json
{
  "asset_id": "modbus-pump-01",
  "ts": "2026-10-16T15:00:00.000Z",
  "temperature": 70.2,
  "pressure": 2.5,
  "vibration": 1.0,
  "quality": "good"
}
```

`asset_id` es `modbus-pump-01` a propósito. El simulador por defecto sigue en `critical-pump-01`, así Grafana puede mostrar ambas series.

## Comprobación

1. `docker compose up -d --build`
2. Desde el host, un cliente Modbus TCP contra `localhost:1502`, unit `1`, lee los holding registers 0–2.
3. En el editor de ingesta (`http://localhost:1881`), el tab **Modbus TCP Ingestion** está activo y el getter muestra actividad cada 5 segundos.
4. Una lectura MQTT de `plant-01/area-01/modbus-pump-01/telemetry` devuelve el JSON de arriba.
5. Grafana **Asset Health** lista `modbus-pump-01` junto a `critical-pump-01`.

Si el paso 3 falla, confirma que `modbus-slave` está sano y que Node-RED terminó de instalar `node-red-contrib-modbus` (el primer arranque puede tardar un minuto).

## RTU (horizonte)

El mismo mapa de registros y escalado aplicaría sobre Modbus RTU (`/dev/ttyUSB0`, baud, paridad, stop bits). Este stack todavía no implementa RTU: Compose no monta un dispositivo serial y no hay tab cliente RTU en Node-RED. Cuando haya un adaptador USB, el cliente de ingesta pasaría de TCP a serial; el contrato MQTT se mantendría.
