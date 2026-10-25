# Frontera OT/IT y taxonomía MQTT

[English](adr-ot-it.en.md)

Estado: aceptada. 2026-10-24.

## Contexto

El laboratorio separa el borde en dos redes. La lectura de la bomba, el compresor o el motor tiene que llegar a TimescaleDB, y el proceso que habla Modbus u OPC UA no abre la base.

| Red | Quién está |
| --- | --- |
| `ot-net` | `mqtt-simulator`, `modbus-slave`, `node-red-ingestion` |
| `it-net` | `node-red-etl`, TimescaleDB, Grafana |
| las dos | Mosquitto |

Mosquitto es el único nombre que las dos redes resuelven. El ETL no resuelve el esclavo Modbus. La ingesta no resuelve `timescaledb`, y ese contenedor no recibe `POSTGRES_PASSWORD`. Grafana y el ETL usan el nombre `timescaledb` dentro de `it-net`.

Cada Node-RED agrega una ruta `prohibit` sobre `172.16.0.0/12`, el rango de las redes bridge de este Docker. La ruta conectada de su propia red es más específica, así que el broker de esa red sigue respondiendo. Una IP de la otra subred, dentro de ese rango, cae en la ruta prohibida y se rechaza. TimescaleDB solo se publica en `127.0.0.1:5435`.

El mensaje cruza con QoS 1 en `plant-01/area-01/<asset_id>/telemetry`. El ETL se suscribe a `+/+/+/telemetry`.

| Nivel | Ejemplo | Qué es |
| --- | --- | --- |
| 1 | `plant-01` | `assets.plant` |
| 2 | `area-01` | `assets.area` |
| 3 | `critical-pump-01` | `assets.asset_id`. El cuerpo trae el mismo `asset_id` |
| 4 | `telemetry` | Clase de mensaje |

Planta y área del tópico tienen que coincidir con la fila de `assets`. Un mensaje que no cumple el contrato se publica en el tópico `rejected` y se guarda en `rejected_messages`.

## Decisión

La frontera aceptada es esta: OT e IT solo se encuentran en el broker. El tópico aceptado es un namespace corto de tres niveles de equipo y una clase de mensaje.

`plant` y `area` son las columnas de `assets`. El tercer nivel es el activo. `telemetry` no nombra un equipo: nombra la clase. `rejected` no termina en `/telemetry`, así que el ETL no se vuelve a leer su propio rechazo.

ISA-95 es la referencia de poner la jerarquía en el nombre. Por encima de planta iría la empresa. El registro y el tópico empiezan en planta.

Sparkplug B es otro namespace, `spBv1.0/grupo/tipo/nodo/dispositivo`, con mensajes de nacimiento y de muerte. Este laboratorio publica el JSON del contrato v1. Sin un mensaje de muerte, un activo sin lecturas utilizables en el último minuto queda `stale` en `asset_condition`.

Estos límites siguen siendo de laboratorio:

- Hay una sola cuenta MQTT. `allow_anonymous false` y no hay ACL. Quien tiene `MQTT_USER` y `MQTT_PASSWORD` publica y se suscribe a cualquier tópico.
- El puerto `1883` se publica en el host. TimescaleDB escucha en `127.0.0.1:5435`.
- `rejected` es un tópico plano.
- El camino opcional de OPC UA usa el modo de seguridad `None`, el del simulador de laboratorio.

El compose, los flujos y los tópicos quedan como están.

## Consecuencias

- Un editor de ingesta abierto no llega a TimescaleDB por el nombre `timescaledb` ni por una IP de `it-net` dentro de `172.16.0.0/12`. Con la cuenta MQTT sí publica en cualquier tópico.
- Un equipo que deja de publicar queda `stale` cuando el último minuto no tiene lecturas utilizables.
- Una planta o un área nuevos son una fila de `assets` y dos segmentos del tópico. Un quinto nivel cambia la suscripción `+/+/+/telemetry` y el corte del tópico en el ETL.
- Sparkplug B queda nombrado y sin implementar.
