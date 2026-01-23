# Tools

## publish_mseed.py

Publishes synthetic miniSEED chunks to AMQP using `pymseed` and `pika`.

### Usage
```sh
COMPOSE_PROFILES=tools docker compose run --rm publisher --host rabbitmq --exchange stations --count 3
```
