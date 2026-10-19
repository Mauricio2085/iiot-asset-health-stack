#!/usr/bin/env python3
"""Modbus TCP slave that exposes motor telemetry as holding registers.

Register map (unit id 1):
  HR0  temperature * 10   (e.g. 550  → 55.0 °C)
  HR1  pressure * 100     (e.g. 100  → 1.00 bar)
  HR2  vibration * 100    (e.g. 80   → 0.80 mm/s RMS)
  HR3  device status      (0 good, 1 uncertain, 2 bad)

The motor runs a repeating unbalance scenario: normal operation, a
progressive vibration ramp through warning (2.8 mm/s) and alarm (4.5 mm/s),
a sustained alarm, then a simulated rotor balancing that restarts the cycle.
During normal operation the vibration transmitter also fails briefly: its
reading saturates at the top of its range and the device flags it as bad.
"""

from __future__ import annotations

import logging
import math
import os
import random
import signal
import sys
import threading
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartTcpServer

HOST = os.environ.get("MODBUS_BIND_HOST", "0.0.0.0")
PORT = int(os.environ.get("MODBUS_BIND_PORT", "502"))
UNIT_ID = int(os.environ.get("MODBUS_UNIT_ID", "1"))
UPDATE_INTERVAL_S = float(os.environ.get("UPDATE_INTERVAL_S", "1"))

# Nominal points of critical-motor-01; soft-noise shape matches mqtt-simulator.
MOTOR_TEMPERATURE = 55.0
MOTOR_PRESSURE = 1.0
MOTOR_VIBRATION = 0.8

# Unbalance scenario. Thresholds follow ISO 10816-3 zones for medium machines
# on rigid foundations: warning at the B/C limit, alarm at the C/D limit.
NORMAL_S = 180
RAMP_S = 420
ALARM_HOLD_S = 180
CYCLE_S = NORMAL_S + RAMP_S + ALARM_HOLD_S
PEAK_VIBRATION = 5.0
TEMPERATURE_RISE = 1.5

# Vibration transmitter fault, inside the normal phase so it does not overlap
# the unbalance ramp. A broken 4-20 mA loop drives the reading to the top of
# the sensor range (NAMUR NE43 treats over 21 mA as a failure).
SENSOR_FAULT_START_S = 60
SENSOR_FAULT_S = 30
SATURATED_VIBRATION = 25.0

STATUS_GOOD = 0
STATUS_UNCERTAIN = 1
STATUS_BAD = 2

# Holding-register function code used by pymodbus setValues / getValues.
HR_FC = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("modbus-slave")

_running = True


def _handle_stop(signum: int, _frame: object) -> None:
    global _running
    log.info("received signal %s, stopping", signum)
    _running = False


def soft_noise(t: float, base: float, amplitude: float, period_s: float) -> float:
    drift = amplitude * math.sin(2.0 * math.pi * t / period_s)
    return base + drift + random.uniform(-amplitude * 0.05, amplitude * 0.05)


def unbalance_state(elapsed_s: float) -> tuple[str, float]:
    """Return the scenario phase and unbalance severity from 0 (healthy) to 1 (peak)."""
    t = elapsed_s % CYCLE_S
    if t < NORMAL_S:
        return "normal", 0.0
    if t < NORMAL_S + RAMP_S:
        progress = (t - NORMAL_S) / RAMP_S
        # Quadratic, so the ramp starts slow and accelerates like a P-F curve.
        return "unbalance-ramp", progress * progress
    return "alarm-hold", 1.0


def sensor_fault(elapsed_s: float) -> bool:
    t = elapsed_s % CYCLE_S
    return SENSOR_FAULT_START_S <= t < SENSOR_FAULT_START_S + SENSOR_FAULT_S


def scenario_phase(elapsed_s: float) -> str:
    return "sensor-fault" if sensor_fault(elapsed_s) else unbalance_state(elapsed_s)[0]


def scaled_registers(elapsed_s: float) -> list[int]:
    _, severity = unbalance_state(elapsed_s)
    temperature = soft_noise(
        elapsed_s, MOTOR_TEMPERATURE + TEMPERATURE_RISE * severity, 0.4, 300.0
    )
    pressure = soft_noise(elapsed_s, MOTOR_PRESSURE, 0.03, 240.0)
    vibration = soft_noise(
        elapsed_s,
        MOTOR_VIBRATION + (PEAK_VIBRATION - MOTOR_VIBRATION) * severity,
        0.02 + 0.08 * severity,
        180.0,
    )
    status = STATUS_GOOD
    if sensor_fault(elapsed_s):
        vibration = SATURATED_VIBRATION
        status = STATUS_BAD
    return [
        int(round(temperature * 10)),
        int(round(pressure * 100)),
        int(round(vibration * 100)),
        status,
    ]


def update_loop(context: ModbusServerContext) -> None:
    started = time.monotonic()
    ticks = 0
    last_phase = None
    while _running:
        elapsed = time.monotonic() - started
        phase = scenario_phase(elapsed)
        if phase != last_phase:
            if last_phase == "alarm-hold":
                log.info("scenario: maintenance balanced the rotor, back to normal")
            elif last_phase == "sensor-fault":
                log.info("scenario: vibration transmitter recovered, back to normal")
            else:
                log.info("scenario: entering %s", phase)
            last_phase = phase
        values = scaled_registers(elapsed)
        # single=True → slave address 0x00 regardless of UNIT_ID on the wire.
        context[0x00].setValues(HR_FC, 0, values)
        ticks += 1
        if ticks == 1 or ticks % 30 == 0:
            log.info(
                "[%s] HR0=%s HR1=%s HR2=%s HR3=%s  (temp=%.1f press=%.2f vib=%.2f)",
                phase,
                values[0],
                values[1],
                values[2],
                values[3],
                values[0] / 10.0,
                values[1] / 100.0,
                values[2] / 100.0,
            )
        time.sleep(UPDATE_INTERVAL_S)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 10),
        zero_mode=True,
    )
    context = ModbusServerContext(slaves=store, single=True)

    updater = threading.Thread(target=update_loop, args=(context,), daemon=True)
    updater.start()

    log.info(
        "Modbus TCP slave on %s:%s unit_id=%s (HR0-HR2 telemetry, HR3 status)",
        HOST,
        PORT,
        UNIT_ID,
    )
    # StartTcpServer blocks until the process is stopped.
    StartTcpServer(context=context, address=(HOST, PORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
