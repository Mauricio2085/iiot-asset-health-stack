#!/usr/bin/env bash
# Stage the lab scenarios for the five-minute demo in docs/demo.en.md.
#
# L is the moment to start watching the dashboard.
#   L - 8:00  restart modbus-slave: the motor cycle starts at 0
#   L - 4:30  restart mqtt-simulator: the pump clock starts at 0
#   L - 1:45  reminder
#   L         watch the dashboard
# Then the motor turns warning near L + 0:20 and alarm near L + 2:00, and the
# pump turns uncertain near L + 0:30. The motor sensor fault (L - 7:00) is
# already in the 15-minute trend as a gap.
#
# Usage: scripts/demo-prep.sh [--check-only]

set -euo pipefail
cd "$(dirname "$0")/.."

SIMULATOR_RESTART_S=210
REMINDER_S=375
LIVE_START_S=480
SERVICES=(mosquitto mqtt-simulator modbus-slave node-red-ingestion node-red-etl timescaledb grafana)

psql_value() {
    docker compose exec -T timescaledb sh -c \
        "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"$1\""
}

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

preflight() {
    echo "== Preflight"
    local running
    running=$(docker compose ps --status running --services)
    for service in "${SERVICES[@]}"; do
        grep -qx "$service" <<<"$running" \
            || fail "$service is not running. Run: docker compose up -d"
    done
    echo "ok   all services running"

    docker exec edge-grafana test -f /etc/grafana/dashboards/asset-health.json \
        || fail "Grafana sees no dashboard file. Run: docker compose up -d --force-recreate grafana"
    echo "ok   Grafana dashboard mounted"

    local assets low
    assets=$(psql_value "SELECT count(*) FROM asset_condition")
    [[ "$assets" == "3" ]] || fail "asset_condition has $assets rows, expected 3"
    low=$(psql_value "SELECT string_agg(asset_id, ', ') FROM asset_condition WHERE data_availability_pct < 100")
    [[ -z "$low" ]] || fail "data availability below 100 % for: $low"
    echo "ok   3 assets reporting at full availability"
}

motor_readings_last_15s() {
    psql_value "SELECT count(*) FROM sensor_readings WHERE asset_id = 'critical-motor-01' AND time > now() - interval '15 seconds'"
}

wait_until() {
    local target_s=$1 label=$2 remaining
    while true; do
        remaining=$(( target_s - ($(date +%s) - T0) ))
        (( remaining <= 0 )) && break
        printf '\r  %-24s in %d:%02d ' "$label" $(( remaining / 60 )) $(( remaining % 60 ))
        sleep 1
    done
    printf '\r%60s\r' ''
}

preflight
[[ "${1:-}" == "--check-only" ]] && exit 0

echo "== Staging"
docker compose restart modbus-slave >/dev/null 2>&1
T0=$(date +%s)
echo "$(date +%T)  modbus-slave restarted (motor cycle at 0)"
echo "           live block (L) at $(date -d "@$(( T0 + LIVE_START_S ))" +%T)"

sleep 25
if [[ "$(motor_readings_last_15s)" == "0" ]]; then
    echo "$(date +%T)  motor not reporting, restarting node-red-ingestion"
    docker compose restart node-red-ingestion >/dev/null 2>&1
fi

wait_until "$SIMULATOR_RESTART_S" "mqtt-simulator restart"
docker compose restart mqtt-simulator >/dev/null 2>&1
echo "$(date +%T)  mqtt-simulator restarted (pump clock at 0)"

wait_until "$REMINDER_S" "reminder"
echo "$(date +%T)  L in 1:45"

wait_until "$LIVE_START_S" "L"
echo "$(date +%T)  L: watch the dashboard. Motor warning in ~20 s, pump uncertain in ~30 s, motor alarm in ~2 min"
