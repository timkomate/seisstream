#!/usr/bin/env bash
set -euo pipefail

COMPOSE=${COMPOSE:-"docker compose"}

HOST=${HOST:-rabbitmq}
PORT=${PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-guest}
RABBITMQ_PASS=${RABBITMQ_PASS:-guest}
PGUSER=${PGUSER:-seis}
PGPASSWORD=${PGPASSWORD:-seis}
PGDATABASE=${PGDATABASE:-seismic}
AMQP_EXCHANGE=${AMQP_EXCHANGE:-stations}
DETECTOR_AMQP_BINDING_KEY=${DETECTOR_AMQP_BINDING_KEY:-ZZ.#}

NET=${NET:-ZZ}
STA=${STA:-DET}
LOC=${LOC:-}
CHAN=${CHAN:-HHZ}

SAMPRATE=${SAMPRATE:-100}
COUNT=${COUNT:-60}
CHUNK_SAMPLES=${CHUNK_SAMPLES:-100}
WAIT_SECONDS=${WAIT_SECONDS:-90}

# Detector tuning for faster, deterministic system tests.
DETECTOR_BUFFER_SECONDS=${DETECTOR_BUFFER_SECONDS:-40}
DETECTOR_DETECT_EVERY_SECONDS=${DETECTOR_DETECT_EVERY_SECONDS:-5}
DETECTOR_PICK_FILTER_SECONDS=${DETECTOR_PICK_FILTER_SECONDS:-10}
DETECTOR_TRIGGER_ON=${DETECTOR_TRIGGER_ON:-2.0}
DETECTOR_TRIGGER_OFF=${DETECTOR_TRIGGER_OFF:-0.5}

export RABBITMQ_USER RABBITMQ_PASS PGUSER PGPASSWORD PGDATABASE
export AMQP_EXCHANGE DETECTOR_AMQP_BINDING_KEY

${COMPOSE} version >/dev/null 2>&1
${COMPOSE} down --remove-orphans
${COMPOSE} up -d --wait rabbitmq timescaledb
${COMPOSE} build detector publisher

: > stderr.log

psql_exec() {
  local sql=$1
  docker exec \
    -e PGPASSWORD="${PGPASSWORD}" \
    seisstream-timescaledb \
    psql -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "${sql}"
}

cleanup() {
  docker rm -f seisstream-detector-test >/dev/null 2>&1 || true
}
trap cleanup EXIT

psql_exec "delete from event_detections where net='${NET}' and sta='${STA}' and loc='${LOC}' and chan='${CHAN}';" \
  2>> stderr.log

docker compose run -d --rm --no-deps --name seisstream-detector-test detector \
  python -m detector.main \
  --host rabbitmq \
  --port "${PORT}" \
  --user "${RABBITMQ_USER}" \
  --password "${RABBITMQ_PASS}" \
  --exchange "${AMQP_EXCHANGE}" \
  --binding-key "${DETECTOR_AMQP_BINDING_KEY}" \
  --pg-host timescaledb \
  --pg-user "${PGUSER}" \
  --pg-password "${PGPASSWORD}" \
  --pg-db "${PGDATABASE}" \
  --detector-mode sta_lta \
  --buffer-seconds "${DETECTOR_BUFFER_SECONDS}" \
  --detect-every-seconds "${DETECTOR_DETECT_EVERY_SECONDS}" \
  --pick-filter-seconds "${DETECTOR_PICK_FILTER_SECONDS}" \
  --trigger-on "${DETECTOR_TRIGGER_ON}" \
  --trigger-off "${DETECTOR_TRIGGER_OFF}" \
  --log-level INFO >> stderr.log 2>&1

COMPOSE_PROFILES=tools ${COMPOSE} run --rm publisher \
  --host "${HOST}" \
  --port "${PORT}" \
  --user "${RABBITMQ_USER}" \
  --password "${RABBITMQ_PASS}" \
  --exchange "${AMQP_EXCHANGE}" \
  --net "${NET}" \
  --sta "${STA}" \
  --loc "${LOC}" \
  --chan "${CHAN}" \
  --samprate "${SAMPRATE}" \
  --chunk-samples "${CHUNK_SAMPLES}" \
  --count "${COUNT}" \
  --event \
  --event-probability 1.0 \
  --event-amplitude 6000 \
  --event-duration 60 \
  --event-frequency 0.3 \
  --log-level INFO < /dev/null 2>> stderr.log

wait_for_detection() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  local rows=0
  while (( SECONDS < deadline )); do
    rows=$(psql_exec "select count(*) from event_detections where net='${NET}' and sta='${STA}' and loc='${LOC}' and chan='${CHAN}';")
    if [[ "${rows}" -gt 0 ]]; then
      echo "${rows}"
      return 0
    fi
    sleep 1
  done
  echo "${rows}"
  return 1
}

detection_rows=$(wait_for_detection || true)
if [[ "${detection_rows}" -le 0 ]]; then
  echo "Detector event test failed: no event_detections rows for ${NET}.${STA}.${LOC}.${CHAN} after ${WAIT_SECONDS}s." >&2
  echo "Recent detector logs:" >&2
  docker logs --tail 80 seisstream-detector-test >&2 || true
  exit 1
fi

echo "Detector event test passed. event_detections=${detection_rows}"
