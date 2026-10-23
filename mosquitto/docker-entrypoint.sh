#!/bin/sh
# Build the password file from the environment on every start, then run
# the image entrypoint. The file lives on the data volume and is not in git.
set -eu

if [ -z "${MQTT_USER:-}" ] || [ -z "${MQTT_PASSWORD:-}" ]; then
  echo "mosquitto: MQTT_USER and MQTT_PASSWORD are required" >&2
  exit 1
fi

mosquitto_passwd -b -c /mosquitto/data/passwd "$MQTT_USER" "$MQTT_PASSWORD"
chmod 0600 /mosquitto/data/passwd

exec /docker-entrypoint.sh /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf
