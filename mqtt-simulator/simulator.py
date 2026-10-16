#!/usr/bin/env python3
"""Publish lab pump telemetry to Mosquitto every 5 seconds."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_HOST", "mosquitto")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TOPIC = os.environ.get(
    "MQTT_TOPIC", "plant-01/area-01/critical-pump-01/telemetry"
)
ASSET_ID = os.environ.get("ASSET_ID", "critical-pump-01")
INTERVAL_S = float(os.environ.get("PUBLISH_INTERVAL_S", "5"))

# Nominal operating points (same order of magnitude as the OPC UA lab payload).
BASE_TEMPERATURE = 70.0
BASE_PRESSURE = 2.5
BASE_VIBRATION = 1.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("mqtt-simulator")

_running = True


def _handle_stop(signum: int, _frame: object) -> None:
    global _running
    log.info("received signal %s, stopping", signum)
    _running = False


def soft_noise(t: float, base: float, amplitude: float, period_s: float) -> float:
    """Slow sine drift plus tiny measurement jitter."""
    drift = amplitude * math.sin(2.0 * math.pi * t / period_s)
    return base + drift + random.uniform(-amplitude * 0.05, amplitude * 0.05)


def build_payload(elapsed_s: float) -> dict:
    return {
        "asset_id": ASSET_ID,
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        # Mild process drift (~±0.4 °C / ±0.03 bar / ±0.02), not lab-demo swings.
        "temperature": round(soft_noise(elapsed_s, BASE_TEMPERATURE, 0.4, 300.0), 2),
        "pressure": round(soft_noise(elapsed_s, BASE_PRESSURE, 0.03, 240.0), 3),
        "vibration": round(soft_noise(elapsed_s, BASE_VIBRATION, 0.02, 180.0), 3),
        "quality": "good",
    }


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="mqtt-simulator",
    )
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while _running:
        try:
            client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning(
                "broker %s:%s unreachable (%s); retrying in 2s",
                BROKER_HOST,
                BROKER_PORT,
                exc,
            )
            time.sleep(2)

    client.loop_start()
    log.info(
        "publishing QoS 1 to %s every %ss via %s:%s",
        TOPIC,
        INTERVAL_S,
        BROKER_HOST,
        BROKER_PORT,
    )

    started = time.monotonic()
    next_publish = started

    while _running:
        now = time.monotonic()
        if now >= next_publish:
            payload = build_payload(now - started)
            body = json.dumps(payload, separators=(",", ":"))
            info = client.publish(TOPIC, body, qos=1)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                log.error("publish failed rc=%s", info.rc)
            else:
                log.info("published %s", body)
            next_publish = now + INTERVAL_S
        time.sleep(0.2)

    client.loop_stop()
    client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
