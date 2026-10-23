#!/usr/bin/env python3
"""Publish lab telemetry for critical assets to Mosquitto every 5 seconds."""

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
INTERVAL_S = float(os.environ.get("PUBLISH_INTERVAL_S", "5"))

# Same JSON contract per asset; distinct nominal points so Grafana shows
# different "personalities". Motor arrives via Modbus, not this process.
# The simulator plays both device and edge, so it also decides quality.
ASSETS = [
    {
        "asset_id": "critical-pump-01",
        "topic": "plant-01/area-01/critical-pump-01/telemetry",
        "temperature": 70.0,
        "pressure": 2.5,
        "vibration": 1.0,
        # Temperature sensor out of calibration: for 2 minutes in every 10 it
        # reads 3 °C high and the device flags the whole message as uncertain.
        "calibration_drift": {
            "period_s": 600,
            "start_s": 300,
            "duration_s": 120,
            "temperature_offset": 3.0,
        },
    },
    {
        "asset_id": "critical-compressor-01",
        "topic": "plant-01/area-01/critical-compressor-01/telemetry",
        "temperature": 85.0,
        "pressure": 6.0,
        "vibration": 1.5,
    },
]

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


def in_calibration_drift(elapsed_s: float, asset: dict) -> bool:
    drift = asset.get("calibration_drift")
    if drift is None:
        return False
    t = elapsed_s % drift["period_s"]
    return drift["start_s"] <= t < drift["start_s"] + drift["duration_s"]


def build_payload(elapsed_s: float, asset: dict) -> dict:
    temperature = soft_noise(elapsed_s, asset["temperature"], 0.4, 300.0)
    quality = "good"
    if in_calibration_drift(elapsed_s, asset):
        temperature += asset["calibration_drift"]["temperature_offset"]
        quality = "uncertain"
    return {
        "asset_id": asset["asset_id"],
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        ),
        # Mild process drift (~±0.4 °C / ±0.03 bar / ±0.02), not lab-demo swings.
        "temperature": round(temperature, 2),
        "pressure": round(soft_noise(elapsed_s, asset["pressure"], 0.03, 240.0), 3),
        "vibration": round(soft_noise(elapsed_s, asset["vibration"], 0.02, 180.0), 3),
        "quality": quality,
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
            client.username_pw_set(
                os.environ["MQTT_USER"],
                os.environ["MQTT_PASSWORD"],
            )
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
    topics = ", ".join(asset["topic"] for asset in ASSETS)
    log.info(
        "publishing QoS 1 to [%s] every %ss via %s:%s",
        topics,
        INTERVAL_S,
        BROKER_HOST,
        BROKER_PORT,
    )

    started = time.monotonic()
    next_publish = started

    while _running:
        now = time.monotonic()
        if now >= next_publish:
            elapsed = now - started
            for asset in ASSETS:
                payload = build_payload(elapsed, asset)
                body = json.dumps(payload, separators=(",", ":"))
                info = client.publish(asset["topic"], body, qos=1)
                if info.rc != mqtt.MQTT_ERR_SUCCESS:
                    log.error(
                        "publish failed asset=%s rc=%s",
                        asset["asset_id"],
                        info.rc,
                    )
                else:
                    log.info("published %s", body)
            next_publish = now + INTERVAL_S
        time.sleep(0.2)

    client.loop_stop()
    client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
