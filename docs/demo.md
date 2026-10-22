# Recorrido del demo

[English](demo.en.md)

Un recorrido de cinco minutos por el stack: un motor pasa de sano a alarma, un sensor falla sin disparar una falsa alarma y un dato dudoso queda señalado. Los escenarios del laboratorio corren con sus propios ciclos; `scripts/demo-prep.sh` los alinea para que los eventos clave ocurran mientras se mira el tablero.

## Preparación

1. Levanta el stack: `docker compose up -d`.
2. Abre Grafana en `http://localhost:3001`, dashboard **Asset Health**, rango **Last 15 minutes**.
3. Ejecuta:

   ```bash
   scripts/demo-prep.sh
   ```

Primero, el script verifica que los siete servicios estén corriendo, que Grafana vea su dashboard y que los tres activos reporten con disponibilidad completa. Si una verificación falla, muestra el comando que lo arregla. Después reinicia el slave y el simulador en momentos fijos e imprime **L**, el momento de empezar a mirar el tablero. Tarda 8 minutos en llegar a L.

| Tiempo | Evento |
| --- | --- |
| L − 8:00 | `modbus-slave` se reinicia: el ciclo del motor empieza en 0 |
| L − 7:00 | El transmisor de vibración del motor falla durante 30 s |
| L − 4:30 | `mqtt-simulator` se reinicia: el reloj de la bomba empieza en 0 |
| L − 1:45 | Aviso: faltan unos dos minutos |
| L | Mirar el tablero |
| L + 0:20 | El motor pasa a `warning` |
| L + 0:30 | La bomba pasa a `uncertain` |
| L + 2:00 | El motor pasa a `alarm` |

Para hacer solo las verificaciones, sin reiniciar nada: `scripts/demo-prep.sh --check-only`.

La tendencia del motor muestra una caída brusca en L − 8:00. Es el reinicio del escenario que hace el script, no parte de la historia.

## Qué mirar

| Momento | Dónde | Qué muestra |
| --- | --- | --- |
| L | Franja del pipeline y tarjeta del motor | El pipeline está gris: unas 36 lecturas por minuto, cero rechazos, lag bajo 15 s. La tarjeta del motor marca cerca de 50 % de margen consumido: la vibración sube hacia la alarma |
| L + 0:20 | Tarjeta del motor y contador de warning | `WARNING` en ámbar. Solo sube la vibración; la temperatura y la presión siguen estables, lo que apunta a una causa mecánica compatible con un desbalance |
| L + 0:30 | Tabla de detalle, fila de la bomba | Data quality `UNCERTAIN`: el sensor de temperatura marca 3 °C de más. Las lecturas se usan y quedan señaladas; la condición sigue en `normal` |
| L + 1:00 | Fila del motor, tendencia de vibración | Un hueco de hace unos 8 minutos. El transmisor marcó 25 mm/s y lo señaló como `bad`: las lecturas se guardan, pero no entran a la condición, así que no hubo falsa alarma |
| L + 2:00 | Tarjeta del motor y contador de alarma | `ALARM` en rojo, con más de 100 % de margen consumido. Esta vez el dato es bueno |

Cada parte se explica con más detalle en [asset-condition.md](asset-condition.md) y [modbus-tcp.md](modbus-tcp.md).

## Tiempos

Los tiempos están escenificados. Aquí, del warning a la alarma pasan menos de dos minutos; en planta, una degradación así toma días o semanas. El promedio de un minuto hace que cada cambio de estado llegue unos 30 s después de que la lectura cruza su umbral.

## Problemas frecuentes

| Problema | Solución |
| --- | --- |
| Grafana no muestra el dashboard | `docker compose up -d --force-recreate grafana`. Pasa cuando Docker arranca antes que los archivos de WSL |
| El motor aparece en `NO DATA` | `docker compose restart node-red-ingestion`. El cliente Modbus no siempre reconecta solo; el script ya lo intenta una vez |
| Los eventos se desfasaron | Cambia el rango a **Last 30 minutes** para verlos en el historial, o vuelve a ejecutar `scripts/demo-prep.sh` |
| Un cambio en el dashboard no aparece | Refresca el navegador |
