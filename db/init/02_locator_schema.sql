CREATE TABLE IF NOT EXISTS stations (
  net text NOT NULL,
  sta text NOT NULL,
  loc text NOT NULL DEFAULT '',
  lat double precision NOT NULL,
  lon double precision NOT NULL,
  elev_m double precision NOT NULL DEFAULT 0,
  PRIMARY KEY (net, sta, loc)
);

CREATE TABLE IF NOT EXISTS origins (
  id bigserial PRIMARY KEY,
  origin_ts timestamptz NOT NULL,
  lat double precision NOT NULL,
  lon double precision NOT NULL,
  depth_km double precision NOT NULL,
  rms_seconds double precision NOT NULL,
  gap_deg double precision,
  n_picks integer NOT NULL,
  n_stations integer NOT NULL,
  status text NOT NULL DEFAULT 'preliminary',
  association_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS origins_association_key_uidx
  ON origins (association_key);

CREATE INDEX IF NOT EXISTS origins_time_idx
  ON origins (origin_ts DESC);

CREATE TABLE IF NOT EXISTS origin_arrivals (
  id bigserial PRIMARY KEY,
  origin_id bigint NOT NULL REFERENCES origins(id) ON DELETE CASCADE,
  phase_pick_id bigint,
  phase text NOT NULL,
  ts timestamptz NOT NULL,
  net text NOT NULL,
  sta text NOT NULL,
  loc text NOT NULL,
  chan text NOT NULL DEFAULT '',
  tt_pred_seconds double precision NOT NULL,
  residual_seconds double precision NOT NULL,
  distance_km double precision,
  azimuth_deg double precision,
  takeoff_deg double precision,
  weight double precision NOT NULL DEFAULT 1.0,
  used boolean NOT NULL DEFAULT TRUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS origin_arrivals_origin_idx
  ON origin_arrivals (origin_id);

CREATE UNIQUE INDEX IF NOT EXISTS origin_arrivals_origin_pick_uidx
  ON origin_arrivals (origin_id, phase_pick_id)
  WHERE phase_pick_id IS NOT NULL;
