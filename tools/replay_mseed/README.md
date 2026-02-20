## replay_mseed.py

Replays one or more miniSEED files over AMQP, pacing messages based on
record timestamps so it mimics real-time ingestion. Timestamps are shifted to
start at the current time. Records from all input files are merged into one
global timeline and sent in timestamp order.

Example:

```bash
python3 tools/replay_mseed/replay_mseed.py /path/to/event.mseed \
  --host 127.0.0.1 \
  --exchange stations
```

Replay multiple files in one run:

```bash
python3 tools/replay_mseed/replay_mseed.py \
  /path/to/station_a.mseed \
  /path/to/station_b.mseed \
  --host 127.0.0.1 \
  --exchange stations
```

Notes:

- If no records are loaded from input files, the program exits with a non-zero code.
- If `sourceid` cannot be parsed, replay fails with an error (no fallback routing key).
