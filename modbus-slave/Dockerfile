FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY slave.py .

ENV MODBUS_BIND_HOST=0.0.0.0 \
    MODBUS_BIND_PORT=502 \
    MODBUS_UNIT_ID=1 \
    UPDATE_INTERVAL_S=1

EXPOSE 502

CMD ["python", "-u", "slave.py"]
