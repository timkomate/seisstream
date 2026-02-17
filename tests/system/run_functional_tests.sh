#!/usr/bin/env bash
set -euo pipefail

COMPOSE=${COMPOSE:-"docker compose"}
SKIP_COMPOSE_BUILD=${SKIP_COMPOSE_BUILD:-0}

HOST=${HOST:-rabbitmq}
PORT=${PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-guest}
RABBITMQ_PASS=${RABBITMQ_PASS:-guest}
PGUSER=${PGUSER:-seis}
PGPASSWORD=${PGPASSWORD:-seis}
PGDATABASE=${PGDATABASE:-seismic}
AMQP_EXCHANGE=${AMQP_EXCHANGE:-stations}
CONSUMER_AMQP_BINDING_KEY=${CONSUMER_AMQP_BINDING_KEY:-#}

SAMPRATE=${SAMPRATE:-20}
COUNT=${COUNT:-3}
CHUNK_SAMPLES=${CHUNK_SAMPLES:-200}

STREAMS=${STREAMS:-$'XX|TEST1||HHZ\nXX|TEST2||HHN'}

export RABBITMQ_USER RABBITMQ_PASS PGUSER PGPASSWORD PGDATABASE AMQP_EXCHANGE

${COMPOSE} version >/dev/null 2>&1

${COMPOSE} down --remove-orphans
${COMPOSE} up -d --wait rabbitmq timescaledb
if [[ "${SKIP_COMPOSE_BUILD}" != "1" ]]; then
  ${COMPOSE} build consumer publisher
fi
${COMPOSE} up -d consumer

psql_exec() {
  local sql=$1
  docker exec \
    -e PGPASSWORD="${PGPASSWORD}" \
    seisstream-timescaledb \
    psql -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "${sql}"
}

echo " " > stderr.log

while IFS='|' read -r net sta loc chan; do
  psql_exec "delete from seismic_samples where net='${net}' and sta='${sta}' and loc='${loc}' and chan='${chan}';" \
    2>> stderr.log
done < <(printf '%s\n' "${STREAMS}")

sleep 5

while IFS='|' read -r net sta loc chan; do
  COMPOSE_PROFILES=tools ${COMPOSE} run --rm publisher \
    --host "${HOST}" \
    --port "${PORT}" \
    --user "${RABBITMQ_USER}" \
    --password "${RABBITMQ_PASS}" \
    --exchange "${AMQP_EXCHANGE}" \
    --net "${net}" \
    --sta "${sta}" \
    --loc "${loc}" \
    --chan "${chan}" \
    --samprate "${SAMPRATE}" \
    --chunk-samples "${CHUNK_SAMPLES}" \
    --count "${COUNT}" \
    --log-level INFO </dev/null 2>> stderr.log
done < <(printf '%s\n' "${STREAMS}")

sleep 5

expected_rows=$((COUNT * CHUNK_SAMPLES))

while IFS='|' read -r net sta loc chan; do
  rows=$(psql_exec "select count(*) from seismic_samples where net='${net}' and sta='${sta}' and loc='${loc}' and chan='${chan}';")
  if [[ "${rows}" -ne "${expected_rows}" ]]; then
    echo "Functional test failed for ${net}.${sta}.${loc}.${chan}. Expected ${expected_rows} rows, got ${rows}" >&2
    exit 1
  fi
done < <(printf '%s\n' "${STREAMS}")

echo "Functional tests passed for all streams."
