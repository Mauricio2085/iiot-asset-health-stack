# Modbus TCP

[English](modbus-tcp.en.md)

`modbus-slave` es la segunda fuente OT de este laboratorio. Es un servidor Modbus TCP con cuatro holding registers para `critical-motor-01`: tres lecturas y un estado del equipo. `node-red-ingestion` los lee cada 5 segundos, escala las lecturas, traduce el estado a la calidad del contrato y publica el mismo contrato JSON de telemetría que el simulador MQTT.

El activo es un motor, no una "bomba Modbus". El `asset_id` nombra el equipo; Modbus es solo el camino por el que sus lecturas llegan al edge.

## Mapa de registros

| Registro | Señal | Escalado | Ejemplo |
| --- | --- | --- | --- |
| HR0 | temperature | valor / 10 | `550` → `55.0` °C |
| HR1 | pressure | valor / 100 | `100` → `1.00` bar |
| HR2 | vibration | valor / 100 | `80` → `0.80` mm/s RMS |
| HR3 | estado del equipo | `0` good, `1` uncertain, `2` bad | `0` → `good` |

- Unit id: `1`
- Puerto en el contenedor: `502`
- Puerto en el host: `1502` (`localhost:1502` desde la máquina)
- Punto nominal: ~55 °C, ~1.0 bar, ~0.8 mm/s
- El ruido suave es el mismo patrón que `mqtt-simulator` (seno lento más jitter pequeño)

## Escenario de desbalance

El motor repite un ciclo de 13 minutos que simula un desbalance progresivo del rotor:

| Minutos | Fase en el log | Vibración |
| --- | --- | --- |
| 0–3 | `normal` | ~0.8 mm/s |
| 1:00–1:30 | `sensor-fault` | el transmisor falla: HR2 se satura en 25.00 mm/s y HR3 vale `2` (bad) |
| 3–10 | `unbalance-ramp` | sube en curva; cruza 2.8 cerca del minuto 7.8 y 4.5 cerca del 9.6 |
| 10–13 | `alarm-hold` | ~5.0 mm/s sostenida |
| 13 | mantenimiento | el rotor se balancea, vuelve a ~0.8 y el ciclo se repite |

La rampa es cuadrática: empieza lenta y se acelera, como la curva P-F de una falla real. La temperatura sube como mucho 1.5 °C y la presión no cambia. Que solo se mueva la vibración apunta a una causa mecánica y no de proceso. Con solo la vibración global, el patrón es *compatible* con un desbalance; confirmarlo exigiría el espectro de vibración.

Umbrales de referencia, inspirados en ISO 10816-3 para máquinas medianas sobre base rígida: **warning en 2.8 mm/s** (límite de zonas B/C) y **alarm en 4.5 mm/s** (límite C/D). Los límites exactos dependen del tamaño y del montaje de cada máquina.

### Falla del sensor

Durante la fase normal, el transmisor de vibración falla durante 30 segundos. Un lazo de 4–20 mA con el cable dañado lleva la lectura al tope del rango del sensor (NAMUR NE43 considera falla una corriente sobre 21 mA), así que HR2 marca 25.00 mm/s, cinco veces el límite de alarma. El equipo lo avisa poniendo HR3 en `2`. La temperatura y la presión siguen normales: falló el instrumento, no el motor.

Las lecturas se guardan con `quality = bad`, pero `asset_condition` las deja fuera de los promedios, así que el motor sigue en `normal` en lugar de disparar una alarma falsa. El dashboard muestra un hueco en la tendencia de vibración y anota las lecturas descartadas en la tarjeta del motor. Ver [asset-condition.md](asset-condition.md#calidad-de-los-datos).

Para arrancar el ciclo desde el minuto 0, por ejemplo al empezar un demo:

```bash
docker compose restart modbus-slave
```

## Contrato MQTT

Tópico: `plant-01/area-01/critical-motor-01/telemetry` (QoS 1)

```json
{
  "asset_id": "critical-motor-01",
  "ts": "2026-10-16T15:00:00.000Z",
  "temperature": 55.0,
  "pressure": 1.0,
  "vibration": 0.8,
  "quality": "good"
}
```

El `asset_id` del payload tiene que coincidir con el segmento de activo del tópico; si no, el ETL rechaza el mensaje.

`quality` sale de HR3. El equipo la decide, y Node-RED traduce su código al vocabulario del contrato: `0` → `good`, `1` → `uncertain`, `2` → `bad`. Cualquier otro código se convierte en `bad`, porque el borde no puede garantizar una lectura cuyo estado no entiende.

## Comprobación

1. `docker compose up -d --build`
2. Desde el host, un cliente Modbus TCP contra `localhost:1502`, unit `1`, lee los holding registers 0–3.
3. En el editor de ingesta (`http://localhost:1881`), el tab **Modbus TCP Ingestion** está activo y el getter muestra actividad cada 5 segundos.
4. Una lectura MQTT de `plant-01/area-01/critical-motor-01/telemetry` devuelve el JSON de arriba.
5. Grafana **Asset Health** lista `critical-motor-01` junto a `critical-pump-01` y `critical-compressor-01`.
6. Un minuto después de `docker compose restart modbus-slave`, llegan seis lecturas del motor con `vibration = 25` y `quality = bad`, y la tarjeta del motor sigue en `NORMAL` con "6 bad readings discarded".

Si el paso 3 falla, confirma que `modbus-slave` está sano y que Node-RED terminó de instalar `node-red-contrib-modbus` (el primer arranque puede tardar un minuto).

### Reconexión después de detener el slave

Si `modbus-slave` se detiene con `docker compose stop`, el cliente Modbus de Node-RED no se reconecta solo cuando el slave vuelve. Con el contenedor detenido, el DNS de Docker deja de resolver `modbus-slave` y el cliente recibe `ENOTFOUND`. `node-red-contrib-modbus` 5.45.2 no incluye ese código entre los errores que disparan un reintento, así que el cliente queda detenido en su estado inicial y no vuelve a leer.

Mientras tanto, `critical-motor-01` aparece como `stale` en `asset_condition`. Para recuperarlo:

```bash
docker compose restart node-red-ingestion
```

En las pruebas, `docker compose restart modbus-slave` se recuperó solo, porque el slave vuelve en un par de segundos; una parada más larga deja el cliente atascado. La reconexión automática queda pendiente para la fase de frontera OT.

## RTU (horizonte)

El mismo mapa de registros y escalado aplicaría sobre Modbus RTU (`/dev/ttyUSB0`, baud, paridad, stop bits). Este stack todavía no implementa RTU: Compose no monta un dispositivo serial y no hay tab cliente RTU en Node-RED. Cuando haya un adaptador USB, el cliente de ingesta pasaría de TCP a serial; el contrato MQTT se mantendría.
