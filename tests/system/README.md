# System tests

These tests spin up RabbitMQ and TimescaleDB, run the consumer, publish
synthetic miniSEED messages, and verify integration behavior end-to-end.

Currently maintained system tests:
- multi-stream ingest
- detector synthetic event e2e

## Run: multi-stream ingest
```sh
bash tests/system/run_functional_tests.sh
```
The script uses `docker compose` and requires support for
`docker compose up --wait`.

## Run: detector synthetic event e2e
```sh
bash tests/system/run_detector_event_test.sh
```
Runs detector in `sta_lta` mode, publishes synthetic event-bearing waveforms,
and asserts at least one row is inserted into `event_detections`.
