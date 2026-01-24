# Tools

## publish_mseed.py

Publishes synthetic miniSEED chunks to AMQP using `pymseed` and `pika`.

### Usage
```sh
python3 tools/publish_mseed/publish_mseed.py --host 127.0.0.1 --exchange stations --count 3
```

Or using docker compose:
```sh
COMPOSE_PROFILES=tools docker compose run --rm publisher --host rabbitmq --exchange stations --count 3
```
