# Salud de activos críticos

[English](README.md)

Tres activos simulados — una bomba, un compresor y un motor — publican temperatura, presión y vibración. El laboratorio separa un motor que se desbalancea, un transmisor de vibración que falló y un borde que dejó de entregar. La vibración del motor cruza el aviso en 2.8 mm/s y la alarma en 4.5 mm/s; un `bad` de 25 mm/s queda fuera de la condición; la bomba sigue sana con la temperatura 3 °C alta y `uncertain`. El caso está en [docs/case.md](docs/case.md).

## Arranque

Hace falta Docker.

```bash
cp .env.example .env
docker compose up -d --build
```

Cambia las contraseñas de `.env` antes de usar el stack fuera de esta máquina.

Grafana queda en `http://localhost:3001`, dashboard **Asset Health**. Los editores de Node-RED piden usuario en `http://localhost:1881` y `http://localhost:1882`.

La arquitectura, los puertos, el contrato y los límites están en el [README en inglés](README.md).
