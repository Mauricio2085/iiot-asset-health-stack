# Salud de un activo crítico

[English](case.en.md)

## Problema

Un jefe de mantenimiento, con tres tendencias en pantalla, tiene que separar tres cosas: un motor que se desbalancea, un transmisor de vibración que falló y un borde que dejó de entregar.

## Arquitectura

Las fuentes publican en Mosquitto, en `ot-net`. El ETL valida el mensaje y TimescaleDB lo guarda, en `it-net`. Grafana lee esa base. El cruce es un MQTT con QoS 1 en `planta/área/activo/telemetry`. La frontera y el tópico están aceptados en [adr-ot-it.md](adr-ot-it.md).

## Resultado

La condición sale del promedio de un minuto, y la peor señal la define. Una lectura `bad` queda en el historial y fuera de ese promedio. Una `uncertain` entra en el promedio y el tablero la marca.

La vibración de `critical-motor-01` cruza el aviso en 2.8 mm/s y la alarma en 4.5 mm/s (ISO 10816-3). La temperatura y la presión se quedan en su valor nominal, así que la causa se lee mecánica.

El transmisor de vibración satura a 25 mm/s y marca la lectura `bad`. El punto queda guardado, el promedio no lo usa y el motor sigue `normal`.

`critical-pump-01` sigue sana. Su temperatura lee 3 °C por encima y llega con calidad `uncertain`: el promedio la usa, la condición sigue `normal` y el tablero la señala.

La primera banda del tablero dice si el borde sigue vivo: lecturas del último minuto, rechazos y la edad de la lectura más nueva. Eso aparece antes que la ficha del motor.

El recorrido, con los tiempos, está en [demo.md](demo.md).
