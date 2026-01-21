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
