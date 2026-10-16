# OPC UA con Prosys (opcional)

[English](opcua-prosys.en.md)

La fuente OT por defecto es `mqtt-simulator` en Compose. Prosys OPC UA Simulation Server es un camino opcional. Corre en el host Windows; no hay servicio de Prosys en `docker-compose.yaml`.

La pestaña **OPC UA Ingestion** en `node-red-ingestion` está **deshabilitada por defecto** para no publicar en el mismo topic que el simulador. Habilítala solo después de detener `mqtt-simulator` y confirmar que Prosys es alcanzable.

## Qué lee el flujo

`node-red-ingestion` hace un poll cada 5 segundos. Lee tres variables Double y las junta en un solo mensaje. Si en 0,5 s no llegan las tres, esa vuelta no se publica.

| Señal | NodeId |
| --- | --- |
| Temperatura | `ns=3;s=criticalTemp1` |
| Presión | `ns=3;s=criticalPressure1` |
| Vibración | `ns=3;s=criticalVibration1` |

Esos NodeId tienen que existir en Prosys como `Double`. El índice de namespace `3` es el que usa este flujo; si Prosys los publica en otro índice, la lectura falla.

El cliente OPC UA está en modo `None` / `None`, sin usuario ni certificado. El endpoint sale de la variable `OPCUA_ENDPOINT`.

Con las tres lecturas, el flujo arma este JSON y lo publica con QoS 1 en `plant-01/area-01/critical-pump-01/telemetry`:

```json
{
  "asset_id": "critical-pump-01",
  "ts": "<hora del contenedor, ISO-8601>",
  "temperature": 0,
  "pressure": 0,
  "vibration": 0,
  "quality": "good"
}
```

`quality` sale siempre como `good`. El flujo no traduce el código de estado OPC UA. `ts` es la hora del contenedor en el momento de armar el mensaje, no el source timestamp del servidor.

## Cómo lo alcanza Docker

El valor de `.env.example` es:

```text
OPCUA_ENDPOINT=opc.tcp://host.docker.internal:53530/OPCUA/SimulationServer
```

`localhost` dentro del contenedor es el contenedor, no Windows. `host.docker.internal` es el nombre con el que el contenedor llega al host donde escucha Prosys. El puerto `53530` y la ruta `/OPCUA/SimulationServer` son el endpoint por defecto de Prosys OPC UA Simulation Server.

En Docker Desktop sobre Windows o WSL2, ese nombre suele resolver solo. Si el motor de Docker corre solo dentro de Linux y el nombre no resuelve, el endpoint tiene que usar una IP del host Windows que el contenedor pueda enrutar, y el firewall de Windows tiene que permitir el puerto `53530`.

## Comprobación

1. Detén el simulador MQTT para que no compita en el topic: `docker compose stop mqtt-simulator`.
2. Prosys está en ejecución y las tres variables existen con los NodeId de la tabla.
3. `.env` tiene `OPCUA_ENDPOINT` apuntando a ese servidor.
4. `docker compose up -d` (si la ingesta ya corre, basta).
5. En el editor de ingesta, `http://localhost:1881`, habilita la pestaña **OPC UA Ingestion** y despliega. El nodo **Publish telemetry** muestra actividad cada 5 segundos.
6. Una lectura MQTT del tópico `plant-01/area-01/critical-pump-01/telemetry` devuelve el JSON de arriba.
7. Grafana, en `http://localhost:3001`, carpeta **IIoT**, dashboard **Asset Health**, muestra la serie de `critical-pump-01`.

Si el paso 5 no avanza, Prosys no es alcanzable o los NodeId no coinciden. El ETL y TimescaleDB no reciben nada que insertar.
