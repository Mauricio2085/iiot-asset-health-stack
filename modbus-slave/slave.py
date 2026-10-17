#!/usr/bin/env python3
"""Modbus TCP slave that exposes motor telemetry as holding registers.

Register map (unit id 1):
  HR0  temperature * 10   (e.g. 550  → 55.0 °C)
  HR1  pressure * 100     (e.g. 100  → 1.00 bar)
  HR2  vibration * 100    (e.g. 80   → 0.80)
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


def scaled_registers(elapsed_s: float) -> list[int]:
    temperature = soft_noise(elapsed_s, MOTOR_TEMPERATURE, 0.4, 300.0)
    pressure = soft_noise(elapsed_s, MOTOR_PRESSURE, 0.03, 240.0)
    vibration = soft_noise(elapsed_s, MOTOR_VIBRATION, 0.02, 180.0)
    return [
        int(round(temperature * 10)),
        int(round(pressure * 100)),
        int(round(vibration * 100)),
    ]


def update_loop(context: ModbusServerContext) -> None:
    started = time.monotonic()
    ticks = 0
    while _running:
        values = scaled_registers(time.monotonic() - started)
        # single=True → slave address 0x00 regardless of UNIT_ID on the wire.
        context[0x00].setValues(HR_FC, 0, values)
        ticks += 1
        if ticks == 1 or ticks % 30 == 0:
            log.info(
                "HR0=%s HR1=%s HR2=%s  (temp=%.1f press=%.2f vib=%.2f)",
                values[0],
                values[1],
                values[2],
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
        "Modbus TCP slave on %s:%s unit_id=%s (HR0-HR2 telemetry)",
        HOST,
        PORT,
        UNIT_ID,
    )
    # StartTcpServer blocks until the process is stopped.
    StartTcpServer(context=context, address=(HOST, PORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
