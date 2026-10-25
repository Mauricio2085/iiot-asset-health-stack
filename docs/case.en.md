# Critical asset health

[Español](case.md)

## Problem

A maintenance lead, looking at three trends, has to separate three things: a motor that is unbalancing, a vibration transmitter that has failed, and an edge that has stopped delivering.

## Architecture

The sources publish to Mosquitto, on `ot-net`. The ETL validates the message and TimescaleDB stores it, on `it-net`. Grafana reads that database. The crossing is one QoS 1 MQTT message on `plant/area/asset/telemetry`. The boundary and the topic are accepted in [adr-ot-it.en.md](adr-ot-it.en.md).

## Result

Condition comes from the one-minute average, and the worst signal sets it. A `bad` reading stays in history and out of that average. An `uncertain` reading enters the average, and the dashboard marks it.

The vibration of `critical-motor-01` crosses warning at 2.8 mm/s and alarm at 4.5 mm/s (ISO 10816-3). Temperature and pressure stay at their nominal values, so the cause reads as mechanical.

The vibration transmitter saturates at 25 mm/s and marks the reading `bad`. The point is stored, the average leaves it out, and the motor stays `normal`.

`critical-pump-01` stays healthy. Its temperature reads 3 °C high and arrives with quality `uncertain`: the average uses it, the condition stays `normal`, and the dashboard flags it.

The top band of the dashboard says whether the edge is still alive: readings in the last minute, rejections, and the age of the newest reading. That band appears before the motor tile.

The walkthrough, with the timings, is in [demo.en.md](demo.en.md).
