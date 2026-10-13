## Overview

This project presents an **end-to-end industrial telemetry pipeline** designed for **critical asset health monitoring** (tracking vibration, temperature, and pressure).

### Key Features

- **OT Simulation:** Prosys OPC UA Simulation Server.
- **Messaging & Decoupling:** Mosquitto MQTT Broker running in Docker.
- **ETL & Data Normalization:** Dual Node-RED containers for message consumption and JSON payload normalization.
- **Time-Series Storage:** PostgreSQL with TimescaleDB hypertables for high-throughput sensor data.
- **Visualization:** Real-time dashboards using Grafana.
