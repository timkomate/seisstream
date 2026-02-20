CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS seismic_samples (
  ts timestamptz NOT NULL,
  net text NOT NULL,
  sta text NOT NULL,
  loc text NOT NULL,
  chan text NOT NULL,
  value bigint NOT NULL,
  sample_rate double precision NOT NULL
);

SELECT create_hypertable('seismic_samples', 'ts',
                         chunk_time_interval => INTERVAL '1 day',
                         if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS seismic_samples_station_ts_idx
  ON seismic_samples (net, sta, loc, chan, ts DESC);

SELECT add_retention_policy('seismic_samples', INTERVAL '3 days');

CREATE TABLE IF NOT EXISTS phase_picks (
  id bigserial,
  ts timestamptz NOT NULL,
  phase text NOT NULL,
  score double precision,
  net text NOT NULL,
  sta text NOT NULL,
  loc text NOT NULL,
  chan text NOT NULL
);

SELECT create_hypertable('phase_picks', 'ts',
                         chunk_time_interval => INTERVAL '7 days',
                         if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS phase_picks_station_ts_idx
  ON phase_picks (net, sta, loc, chan, ts DESC);

CREATE UNIQUE INDEX IF NOT EXISTS phase_picks_unique_idx
  ON phase_picks (net, sta, loc, chan, ts, phase);

ALTER TABLE phase_picks
  SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'net,sta,loc,chan,phase'
  );

SELECT add_compression_policy('phase_picks', INTERVAL '7 days');
SELECT add_retention_policy('phase_picks', INTERVAL '90 days');

CREATE TABLE IF NOT EXISTS event_detections (
  id bigserial,
  ts_on timestamptz NOT NULL,
  ts_off timestamptz NOT NULL,
  score double precision,
  net text NOT NULL,
  sta text NOT NULL,
  loc text NOT NULL,
  chan text NOT NULL
);

SELECT create_hypertable('event_detections', 'ts_on',
                         chunk_time_interval => INTERVAL '7 days',
                         if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS event_detections_station_ts_idx
  ON event_detections (net, sta, loc, chan, ts_on DESC);

CREATE UNIQUE INDEX IF NOT EXISTS event_detections_unique_idx
  ON event_detections (net, sta, loc, chan, ts_on, ts_off);

ALTER TABLE event_detections
  SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'net,sta,loc,chan'
  );

SELECT add_compression_policy('event_detections', INTERVAL '7 days');
SELECT add_retention_policy('event_detections', INTERVAL '90 days');
