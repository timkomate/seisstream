#!/usr/bin/env bash
set -euo pipefail

COMPOSE=${COMPOSE:-"docker compose"}
SKIP_COMPOSE_BUILD=${SKIP_COMPOSE_BUILD:-0}

PGUSER=${PGUSER:-seis}
PGPASSWORD=${PGPASSWORD:-seis}
PGDATABASE=${PGDATABASE:-seismic}

NET=${NET:-ZZL}
LOC=${LOC:-}
CHAN=${CHAN:-HHZ}
WAIT_SECONDS=${WAIT_SECONDS:-60}

# Synthetic truth used for assertions.
EXPECTED_ORIGIN_LAT=${EXPECTED_ORIGIN_LAT:-47.50}
EXPECTED_ORIGIN_LON=${EXPECTED_ORIGIN_LON:-19.05}
EXPECTED_ORIGIN_DEPTH_KM=${EXPECTED_ORIGIN_DEPTH_KM:-8.0}
LAT_LON_TOL=${LAT_LON_TOL:-0.08}
DEPTH_TOL_KM=${DEPTH_TOL_KM:-2.5}
TT_TOL_SECONDS=${TT_TOL_SECONDS:-0.35}

# Pre-calculated P travel times (vp=6.0 km/s) for the station geometry below.
TT_STA1=${TT_STA1:-2.283048}
TT_STA2=${TT_STA2:-2.303230}
TT_STA3=${TT_STA3:-2.737404}
TT_STA4=${TT_STA4:-2.642552}

export PGUSER PGPASSWORD PGDATABASE

${COMPOSE} version >/dev/null 2>&1
${COMPOSE} down --remove-orphans
${COMPOSE} up -d --wait timescaledb
if [[ "${SKIP_COMPOSE_BUILD}" != "1" ]]; then
  ${COMPOSE} build locator
fi

: > stderr.log

psql_exec() {
  local sql=$1
  docker exec \
    -e PGPASSWORD="${PGPASSWORD}" \
    seisstream-timescaledb \
    psql -U "${PGUSER}" -d "${PGDATABASE}" -t -A -c "${sql}"
}

cleanup() {
  docker rm -f seisstream-locator-test >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Cleaning previous locator test rows..."
psql_exec "DELETE FROM origin_arrivals WHERE net='${NET}';" 2>> stderr.log
psql_exec "DELETE FROM origins WHERE association_key IN (SELECT DISTINCT o.association_key FROM origins o JOIN origin_arrivals oa ON oa.origin_id=o.id WHERE oa.net='${NET}');" 2>> stderr.log || true
psql_exec "DELETE FROM phase_picks WHERE net='${NET}';" 2>> stderr.log
psql_exec "DELETE FROM stations WHERE net='${NET}';" 2>> stderr.log

echo "Inserting station metadata..."
psql_exec "
INSERT INTO stations (net, sta, loc, lat, lon, elev_m) VALUES
('${NET}','STA1','${LOC}',47.60,19.05,100.0),
('${NET}','STA2','${LOC}',47.50,19.20,120.0),
('${NET}','STA3','${LOC}',47.38,18.98,110.0),
('${NET}','STA4','${LOC}',47.57,18.90,130.0);
" 2>> stderr.log

origin_ts="$(psql_exec "SELECT now();")"

echo "Inserting synthetic P picks..."
psql_exec "
INSERT INTO phase_picks (ts, phase, score, net, sta, loc, chan) VALUES
('${origin_ts}'::timestamptz + interval '${TT_STA1} second', 'P', 0.95, '${NET}', 'STA1', '${LOC}', '${CHAN}'),
('${origin_ts}'::timestamptz + interval '${TT_STA2} second', 'P', 0.95, '${NET}', 'STA2', '${LOC}', '${CHAN}'),
('${origin_ts}'::timestamptz + interval '${TT_STA3} second', 'P', 0.95, '${NET}', 'STA3', '${LOC}', '${CHAN}'),
('${origin_ts}'::timestamptz + interval '${TT_STA4} second', 'P', 0.95, '${NET}', 'STA4', '${LOC}', '${CHAN}');
" 2>> stderr.log

echo "Starting locator..."
${COMPOSE} run -d --rm --no-deps --name seisstream-locator-test locator \
  python /app/locator/main.py \
  --pg-host timescaledb \
  --pg-user "${PGUSER}" \
  --pg-password "${PGPASSWORD}" \
  --pg-db "${PGDATABASE}" \
  --poll-seconds 1 \
  --lookback-seconds 300 \
  --association-window-seconds 8 \
  --min-stations 4 \
  --min-pick-score 0.0 \
  --vp-km-s 6.0 \
  --max-residual-seconds 10.0 \
  --log-level INFO >> stderr.log 2>&1

wait_for_origin() {
  local deadline=$((SECONDS + WAIT_SECONDS))
  local rows=0
  while (( SECONDS < deadline )); do
    rows="$(psql_exec "
      SELECT count(DISTINCT o.id)
      FROM origins o
      JOIN origin_arrivals oa ON oa.origin_id = o.id
      WHERE oa.net='${NET}';
    ")"
    if [[ "${rows}" -gt 0 ]]; then
      echo "${rows}"
      return 0
    fi
    sleep 1
  done
  echo "${rows}"
  return 1
}

origin_rows="$(wait_for_origin || true)"
if [[ "${origin_rows}" -le 0 ]]; then
  echo "Locator origin test failed: no origin created for ${NET} within ${WAIT_SECONDS}s." >&2
  docker logs --tail 120 seisstream-locator-test >&2 || true
  exit 1
fi

arrival_rows="$(psql_exec "
  SELECT count(*)
  FROM origin_arrivals oa
  JOIN origins o ON o.id = oa.origin_id
  WHERE oa.net='${NET}';
")"
if [[ "${arrival_rows}" -lt 4 ]]; then
  echo "Locator origin test failed: expected >=4 arrivals, got ${arrival_rows}." >&2
  docker logs --tail 120 seisstream-locator-test >&2 || true
  exit 1
fi

origin_match="$(psql_exec "
  SELECT CASE WHEN (
    abs(o.lat - ${EXPECTED_ORIGIN_LAT}) < ${LAT_LON_TOL}
    AND abs(o.lon - ${EXPECTED_ORIGIN_LON}) < ${LAT_LON_TOL}
    AND abs(o.depth_km - ${EXPECTED_ORIGIN_DEPTH_KM}) < ${DEPTH_TOL_KM}
  ) THEN 1 ELSE 0 END
  FROM origins o
  JOIN origin_arrivals oa ON oa.origin_id = o.id
  WHERE oa.net='${NET}'
  ORDER BY o.updated_at DESC
  LIMIT 1;
")"
if [[ "${origin_match}" != "1" ]]; then
  echo "Locator origin test failed: origin estimate outside tolerance." >&2
  psql_exec "
    SELECT o.origin_ts, o.lat, o.lon, o.depth_km, o.rms_seconds
    FROM origins o
    JOIN origin_arrivals oa ON oa.origin_id = o.id
    WHERE oa.net='${NET}'
    ORDER BY o.updated_at DESC
    LIMIT 1;
  " >&2
  docker logs --tail 120 seisstream-locator-test >&2 || true
  exit 1
fi

tt_match="$(psql_exec "
  SELECT CASE WHEN max(abs(oa.tt_pred_seconds - exp.tt)) < ${TT_TOL_SECONDS} THEN 1 ELSE 0 END
  FROM origin_arrivals oa
  JOIN origins o ON o.id = oa.origin_id
  JOIN (
    VALUES
      ('STA1', ${TT_STA1}),
      ('STA2', ${TT_STA2}),
      ('STA3', ${TT_STA3}),
      ('STA4', ${TT_STA4})
  ) AS exp(sta, tt) ON exp.sta = oa.sta
  WHERE oa.net='${NET}';
")"
if [[ "${tt_match}" != "1" ]]; then
  echo "Locator origin test failed: predicted arrival times outside tolerance." >&2
  psql_exec "
    SELECT oa.sta, oa.tt_pred_seconds, oa.residual_seconds
    FROM origin_arrivals oa
    JOIN origins o ON o.id = oa.origin_id
    WHERE oa.net='${NET}'
    ORDER BY oa.sta;
  " >&2
  docker logs --tail 120 seisstream-locator-test >&2 || true
  exit 1
fi

echo "Locator origin test passed. origins=${origin_rows}, arrivals=${arrival_rows}"

