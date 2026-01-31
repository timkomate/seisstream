# seisstream

Simple utilities for streaming MiniSEED over AMQP, ingesting samples into TimescaleDB, and detecting picks.

## Architecture
```mermaid
%%{init: {"theme":"neutral","themeVariables":{"fontSize":"18px","primaryTextColor":"#000","lineColor":"#000"}}}%%
flowchart TB
  subgraph SeedLink Servers
    SL1[SeedLink Server #1]:::src
    SL2[SeedLink Server #2]:::src
    SL3[SeedLink Server #3]:::src
  end

  SL1 -->|SeedLink/MiniSEED| CON1[Connector #1<br/>libslink → AMQP]
  SL2 -->|SeedLink/MiniSEED| CON2[Connector #2<br/>libslink → AMQP]
  SL3 -->|SeedLink/MiniSEED| CON3[Connector #3<br/>libslink → AMQP]

  CON1 -->|AMQP publish| MQ[(AMQP Broker<br/>RabbitMQ)]
  CON2 -->|AMQP publish| MQ
  CON3 -->|AMQP publish| MQ

  MQ -->|AMQP consume| CNS1[Consumer #1<br/>AMQP → libmseed]
  MQ -->|AMQP consume| CNS2[Consumer #2<br/>AMQP → libmseed]
  MQ -->|AMQP consume| CNS3[Consumer #3<br/>AMQP → libmseed]
  MQ -->|AMQP consume| DET[Detector<br/>AMQP → picks]

  CNS1 -->|bulk load| PG[(Timescale DB)]
  CNS2 -->|bulk load| PG
  CNS3 -->|bulk load| PG
  DET -->|insert picks| PG

  PG -->|SQL queries| GRAF[Grafana<br/>Dashboards/Alerts]

  classDef src fill:#eef,stroke:#557;

```


## Components
- `connector/`: SeedLink client that forwards packets to an AMQP (RabbitMQ) broker.
- `consumer/`: AMQP consumer that parses MiniSEED (libmseed) and bulk-loads samples into TimescaleDB.
- `detector/`: Python STA/LTA detector that consumes MiniSEED from AMQP and inserts picks into TimescaleDB.

## Build
Prerequisites: `libslink`, `librabbitmq`, `libmseed`, `libpq` headers/libs available to the compiler.

```sh
make            # builds connector and consumer into ./build
make connector  # builds only connector
make consumer   # builds only consumer
```

## Connector usage (SeedLink → AMQP)
```sh
./build/connector [options] host[:port]
  -V                 report version
  -h                 show help
  -v                 increase verbosity (repeatable)
  -p                 print packet details
  -Ap                prompt for SeedLink user/password
  -At                prompt for SeedLink token
  -nd <secs>         reconnect delay (default 30)
  -nt <secs>         idle timeout (default 600)
  -k <secs>          keepalive interval
  -l <listfile>      stream list file (multi-station)
  -s <selectors>     selectors for all-station/default
  -S <streams>       NET_STA[:selectors], comma-separated
  -x <statefile>     save/restore sequence state
  --amqp-host host   AMQP host (default 127.0.0.1)
  --amqp-port port   AMQP port (default 5672)
  --amqp-user user   AMQP user (default guest)
  --amqp-password pw AMQP password (default guest)
  --amqp-vhost vhost AMQP vhost (default /)
  --amqp-exchange ex AMQP exchange (default empty)
  --amqp-routing-key k AMQP routing key/queue (default binq)
```
## Consumer usage (AMQP → TimescaleDB)
```sh
./build/consumer [opts]
  -h <amqp-host>      (default 127.0.0.1)
  -p <amqp-port>      (default 5672)
  -u <amqp-user>      (default guest)
  -P <amqp-pass>      (default guest)
  -v <amqp-vhost>     (default /)
  -q <queue>          (default binq)
  --prefetch <n>      (default 10)
  --pg-host <host>    (default 192.168.0.106)
  --pg-port <port>    (default 5432)
  --pg-user <user>    (default admin)
  --pg-password <pw>  (default my-secret-pw)
  --pg-db <name>      (default seismic)
```
Note: libmseed parsing runs in verbose mode by default.

## Detector usage (AMQP → picks)
```sh
python -m detector.main [opts]
  --host <amqp-host>             (default 127.0.0.1)
  --port <amqp-port>             (default 5672)
  --user <amqp-user>             (default guest)
  --password <amqp-pass>         (default guest)
  --vhost <amqp-vhost>           (default /)
  --exchange <amqp-exchange>     (default stations)
  --queue <queue>                (default empty for exclusive)
  --binding-key <key>            (repeatable, default "#")
  --prefetch <n>                 (default 50)
  --buffer-seconds <secs>        (default 120)
  --detect-every-seconds <secs>  (default 15)
  --pick-filter-seconds <secs>   (default 2)
  --log-level <level>            (default INFO)
  --pg-host <host>               (default localhost)
  --pg-port <port>               (default 5432)
  --pg-user <user>               (default seis)
  --pg-password <pw>             (default seis)
  --pg-db <name>                 (default seismic)
```

## Database schema
`db/init/01_schema.sql` defines TimescaleDB hypertables for `seismic_samples` and `picks` with indexes and a unique constraint on picks.
