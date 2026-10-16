# OPC UA with Prosys

[Español](opcua-prosys.md)

Prosys OPC UA Simulation Server is the OT source for this lab. It runs on the Windows host. There is no Prosys service in `docker-compose.yaml`. Without that process, the rest of the stack still starts and Grafana stays empty.

## What the flow reads

`node-red-ingestion` polls every 5 seconds. It reads three Double variables and joins them into one message. If all three do not arrive within 0.5 s, that cycle is not published.

| Signal | NodeId |
| --- | --- |
| Temperature | `ns=3;s=criticalTemp1` |
| Pressure | `ns=3;s=criticalPressure1` |
| Vibration | `ns=3;s=criticalVibration1` |

Those NodeIds must exist in Prosys as `Double`. This flow uses namespace index `3`. If Prosys publishes them under another index, the read fails.

The OPC UA client uses `None` / `None`, with no user and no certificate. The endpoint comes from the `OPCUA_ENDPOINT` variable.

When all three reads succeed, the flow builds this JSON and publishes it at QoS 1 to `plant-01/area-01/critical-pump-01/telemetry`:

```json
{
  "asset_id": "critical-pump-01",
  "ts": "<container time, ISO-8601>",
  "temperature": 0,
  "pressure": 0,
  "vibration": 0,
  "quality": "good"
}
```

`quality` is always `good`. The flow does not translate the OPC UA status code. `ts` is the container time when the message is built, not the server source timestamp.

## How Docker reaches it

The value in `.env.example` is:

```text
OPCUA_ENDPOINT=opc.tcp://host.docker.internal:53530/OPCUA/SimulationServer
```

`localhost` inside the container is the container, not Windows. `host.docker.internal` is the name the container uses to reach the host where Prosys is listening. Port `53530` and the path `/OPCUA/SimulationServer` are the default endpoint of Prosys OPC UA Simulation Server.

On Docker Desktop for Windows or WSL2, that name usually resolves on its own. If the Docker engine runs only inside Linux and the name does not resolve, the endpoint must use a Windows host IP that the container can route to, and the Windows firewall must allow port `53530`.

## Check

1. Prosys is running and the three variables exist with the NodeIds in the table.
2. `.env` has `OPCUA_ENDPOINT` pointing at that server.
3. `docker compose up -d`.
4. In the ingestion editor, `http://localhost:1881`, the **Publish telemetry** node shows activity every 5 seconds.
5. An MQTT read of `plant-01/area-01/critical-pump-01/telemetry` returns the JSON above.
6. Grafana at `http://localhost:3001`, folder **IIoT**, dashboard **Asset Health**, shows the `critical-pump-01` series.

If step 4 does not move, Prosys is unreachable or the NodeIds do not match. The ETL flow and TimescaleDB receive nothing to insert.
