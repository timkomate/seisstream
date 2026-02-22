#!/usr/bin/env python3
import argparse
import logging
import signal
import time
from typing import Any

import pika
from pymseed import MS3Record, nstime2timestr, sourceid2nslc

RUNNING = True


def handle_signal(signum, _frame) -> None:
    global RUNNING
    logging.info("Received signal %s, shutting down", signum)
    RUNNING = False


def build_routing_key(sourceid: str) -> str:
    net, sta, loc, chan = sourceid2nslc(sourceid)
    return f"{net}.{sta}.{loc}.{chan}"


def publish_message(channel, exchange: str, routing_key: str, payload: bytes) -> None:
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=payload,
        properties=pika.BasicProperties(content_type="application/vnd.fdsn.mseed"),
    )


def load_records(
    file_paths: list[str],
    skip_not_data: bool,
    validate_crc: bool,
) -> list[dict]:
    records: list[dict] = []
    seq = 0
    for file_path in file_paths:
        logging.info(
            "Reading miniSEED from %s (skip_not_data=%s validate_crc=%s)",
            file_path,
            skip_not_data,
            validate_crc,
        )
        for msr in MS3Record.from_file(
            file_path,
            unpack_data=True,
            skip_not_data=skip_not_data,
            validate_crc=validate_crc,
        ):
            records.append(
                {
                    "starttime": msr.starttime,
                    "sourceid": msr.sourceid,
                    "samprate": msr.samprate,
                    "encoding": msr.encoding,
                    "reclen": msr.reclen,
                    "sampletype": msr.sampletype or "i",
                    "data": msr.np_datasamples.copy(),
                    "seq": seq,
                }
            )
            seq += 1
    records.sort(key=lambda r: (r["starttime"], r["sourceid"], r["seq"]))
    logging.info("Loaded %d records", len(records))
    return records


def replay_records(
    records: list[dict],
    channel: Any,
    exchange: str,
) -> int:
    first_start_ns = records[0]["starttime"]
    loop_start = time.monotonic()
    published = 0
    last_routing_key = None
    base_start_ns = int(time.time() * 1_000_000_000)
    base_iso = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(base_start_ns / 1_000_000_000)
    )
    logging.info("Shifting timestamps to start at %s", base_iso)

    for rec in records:
        if not RUNNING:
            break

        desired_elapsed = (rec["starttime"] - first_start_ns) / 1_000_000_000
        elapsed = time.monotonic() - loop_start
        sleep_for = desired_elapsed - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

        msr = MS3Record()
        msr.sourceid = rec["sourceid"]
        msr.samprate = rec["samprate"]
        msr.encoding = rec["encoding"]
        msr.reclen = rec["reclen"]
        msr.starttime = base_start_ns + (rec["starttime"] - first_start_ns)

        try:
            routing_key = build_routing_key(msr.sourceid)
        except Exception:
            logging.exception(
                "Unable to derive routing key from sourceid=%s", msr.sourceid
            )
            raise

        if routing_key != last_routing_key:
            logging.info(
                "Routing key %s sourceid=%s start=%s samples=%d sr=%.3f",
                routing_key,
                msr.sourceid,
                nstime2timestr(msr.starttime),
                len(rec["data"]),
                msr.samprate,
            )
            last_routing_key = routing_key

        out_records = list(
            msr.generate(data_samples=rec["data"], sample_type=rec["sampletype"])
        )
        if len(out_records) != 1:
            logging.warning(
                "Repacked into %d records for sourceid=%s",
                len(out_records),
                msr.sourceid,
            )
        for record in out_records:
            publish_message(channel, exchange, routing_key, record)
            published += 1

        if published % 100 == 0:
            logging.info("Published %d records", published)

    return published


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay one or more miniSEED files over AMQP with real-time pacing."
    )
    parser.add_argument("files", nargs="+", help="Path(s) to miniSEED file(s)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5672)
    parser.add_argument("--user", default="guest")
    parser.add_argument("--password", default="guest")
    parser.add_argument("--vhost", default="/")
    parser.add_argument("--exchange", default="stations")
    parser.add_argument(
        "--skip-not-data",
        action="store_true",
        help="Skip non-data records instead of raising errors",
    )
    parser.add_argument(
        "--no-validate-crc",
        action="store_true",
        help="Disable CRC validation for miniSEED v3",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    records = load_records(
        file_paths=args.files,
        skip_not_data=args.skip_not_data,
        validate_crc=not args.no_validate_crc,
    )
    if not records:
        logging.error("No miniSEED data records were loaded from input file(s).")
        raise SystemExit(1)

    credentials = pika.PlainCredentials(args.user, args.password)
    params = pika.ConnectionParameters(
        host=args.host,
        port=args.port,
        virtual_host=args.vhost,
        credentials=credentials,
    )

    logging.info(
        "Connecting to AMQP %s:%d vhost=%s exchange=%s",
        args.host,
        args.port,
        args.vhost,
        args.exchange,
    )

    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    if args.exchange:
        channel.exchange_declare(
            exchange=args.exchange, exchange_type="topic", durable=True
        )

    try:
        published = replay_records(
            records=records,
            channel=channel,
            exchange=args.exchange,
        )
        logging.info("Replay done: published %d records", published)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
