# Demo walkthrough

[Español](demo.md)

A five-minute tour of the stack in which a motor goes from healthy to alarm, a sensor fails without raising a false alarm, and doubtful data is flagged. The lab scenarios run on their own cycles; `scripts/demo-prep.sh` lines them up so the key events happen while you watch.

## Preparation

1. Start the stack: `docker compose up -d`.
2. Open Grafana at `http://localhost:3001`, dashboard **Asset Health**, range **Last 15 minutes**.
3. Run:

   ```bash
   scripts/demo-prep.sh
   ```

The script first checks that the seven services are running, that Grafana sees its dashboard, and that the three assets report at full availability. If a check fails it prints the command that fixes it. Then it restarts the slave and the simulator at set times and prints **L**, the moment to start watching the dashboard. It takes 8 minutes to reach L.

| Time | Event |
| --- | --- |
| L − 8:00 | `modbus-slave` restarts: the motor cycle starts at 0 |
| L − 7:00 | The motor vibration transmitter fails for 30 s |
| L − 4:30 | `mqtt-simulator` restarts: the pump clock starts at 0 |
| L − 1:45 | Reminder: about two minutes to go |
| L | Watch the dashboard |
| L + 0:20 | The motor turns `warning` |
| L + 0:30 | The pump turns `uncertain` |
| L + 2:00 | The motor turns `alarm` |

To run only the checks, without restarting anything: `scripts/demo-prep.sh --check-only`.

The motor trend shows a sudden drop at L − 8:00. That is the scenario restart done by the script, not part of the story.

## What to look at

| Moment | Where | What it shows |
| --- | --- | --- |
| L | Pipeline band and motor tile | The pipeline is gray: about 36 readings a minute, zero rejections, lag under 15 s. The motor tile shows about 50 % of its margin used: vibration is rising toward the alarm |
| L + 0:20 | Motor tile, warning counter | `WARNING` in amber. Only vibration rises; temperature and pressure stay steady, which points to a mechanical cause consistent with unbalance |
| L + 0:30 | Detail table, pump row | Data quality `UNCERTAIN`: the temperature sensor reads 3 °C high. The readings are used and flagged; the condition stays `normal` |
| L + 1:00 | Motor row, vibration trend | A gap about 8 minutes back. The transmitter read 25 mm/s and flagged it as `bad`: the readings are stored but left out of the condition, so there was no false alarm |
| L + 2:00 | Motor tile, alarm counter | `ALARM` in red, with more than 100 % of margin used. This time the data is good |

Each part is explained in more depth in [asset-condition.en.md](asset-condition.en.md) and [modbus-tcp.en.md](modbus-tcp.en.md).

## Timing

The timing is staged. Warning to alarm takes under two minutes here; in a plant, a degradation like this takes days or weeks. The 1-minute average puts each state change about 30 s after the reading crosses its threshold.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Grafana shows no dashboard | `docker compose up -d --force-recreate grafana`. It happens when Docker starts before the WSL files are available |
| The motor shows `NO DATA` | `docker compose restart node-red-ingestion`. The Modbus client does not always reconnect on its own; the script already tries once |
| Events are off schedule | Switch the range to **Last 30 minutes** to see them in history, or run `scripts/demo-prep.sh` again |
| A dashboard change does not show | Refresh the browser |
