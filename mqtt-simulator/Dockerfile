FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py .

ENV MQTT_HOST=mosquitto \
    MQTT_PORT=1883 \
    MQTT_TOPIC=plant-01/area-01/critical-pump-01/telemetry \
    ASSET_ID=critical-pump-01 \
    PUBLISH_INTERVAL_S=5

CMD ["python", "-u", "simulator.py"]
