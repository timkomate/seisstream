#!/usr/bin/env python3
import argparse
import logging
import math
import signal
import time

import pika
from pymseed import MS3TraceList, system_time
import numpy as np


def handle_signal(signum, _frame) -> None:
    global RUNNING
    logging.info("Received signal %s, shutting down", signum)
    RUNNING = False


def sine_generator(start_degree: int, batch_size: int, amplitude: int) -> np.ndarray:
    angles = np.radians(np.arange(start_degree, start_degree + batch_size))
    return np.rint(np.sin(angles) * amplitude).astype(int)


def ricker_generator(
    start_sample: int,
    batch_size: int,
    sample_rate: float,
    frequency: float,
    amplitude: int,
    total_samples: int,
) -> np.ndarray:
    idx = np.arange(start_sample, start_sample + batch_size)
    center = total_samples / 2.0
    t = (idx - center) / sample_rate
    pi_f = math.pi * frequency
    arg = pi_f * t
    wavelet = (1.0 - 2.0 * arg * arg) * np.exp(-(arg * arg))
    wavelet[idx >= total_samples] = 0.0
    return np.rint(wavelet * amplitude).astype(int)


def build_sourceid(net: str, sta: str, loc: str, chan: str) -> str:
    chan_fmt = f"{chan[0]}_{chan[1]}_{chan[2]}"
    return f"FDSN:{net}_{sta}_{loc}_{chan_fmt}"


def validate_args(args: argparse.Namespace) -> None:
    if args.sample_rate <= 0:
        raise ValueError("--samprate must be > 0")
    if args.chunk_samples <= 0:
        raise ValueError("--chunk-samples must be > 0")
    if args.amplitude <= 0:
        raise ValueError("--amplitude must be > 0")
    if args.count < 0:
        raise ValueError("--count must be >= 0")
    if args.record_length < 256 or (args.record_length & (args.record_length - 1)) != 0:
        raise ValueError("--record-length must be a power of two >= 256")
    if args.event:
        if args.event_duration <= 0:
            raise ValueError("--event-duration must be > 0")
        if args.event_frequency <= 0:
            raise ValueError("--event-frequency must be > 0")
        if not (0.0 <= args.event_probability <= 1.0):
            raise ValueError("--event-probability must be between 0 and 1")


def publish_message(channel, exchange: str, routing_key: str, payload: bytes) -> None:
    channel.basic_publish(
        exchange=exchange,
        routing_key=routing_key,
        body=payload,
        properties=pika.BasicProperties(content_type="application/vnd.fdsn.mseed"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish generated miniSEED to AMQP.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5672)
    parser.add_argument("--user", default="guest")
    parser.add_argument("--password", default="guest")
    parser.add_argument("--vhost", default="/")
    parser.add_argument("--exchange", default="stations")
    parser.add_argument("--net", default="XX")
    parser.add_argument("--sta", default="TEST")
    parser.add_argument("--loc", default="")
    parser.add_argument("--chan", default="HHZ")
    parser.add_argument("--samprate", type=float, dest="sample_rate", default=40.0)
    parser.add_argument("--chunk-samples", type=int, default=128)
    parser.add_argument("--amplitude", type=int, default=500)
    parser.add_argument(
        "--event",
        action="store_true",
        help="Add a Ricker wavelet burst on top of the sine wave",
    )
    parser.add_argument("--event-duration", type=float, default=100.0)
    parser.add_argument("--event-frequency", type=float, default=0.5)
    parser.add_argument("--event-amplitude", type=int, default=2000)
    parser.add_argument("--event-probability", type=float, default=0.05)
    parser.add_argument(
        "--count", type=int, default=0, help="Number of chunks to publish (0 = forever)"
    )
    parser.add_argument("--record-length", type=int, default=512)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        validate_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    format_version = 2
    start_time_ns = system_time()
    sourceid = build_sourceid(args.net, args.sta, args.loc, args.chan)
    routing_key = f"{args.net}.{args.sta}.{args.loc}.{args.chan}"
    event_total_samples = int(args.event_duration * args.sample_rate)
    rng = np.random.default_rng()
    logging.debug(
        "Publish settings: sourceid=%s sample_rate=%s chunk_samples=%s amplitude=%s record_length=%s",
        sourceid,
        args.sample_rate,
        args.chunk_samples,
        args.amplitude,
        args.record_length,
    )

    logging.info(
        "Connecting to AMQP %s:%d vhost=%s exchange=%s routing_key=%s",
        args.host,
        args.port,
        args.vhost,
        args.exchange,
        routing_key,
    )

    if args.event:
        logging.info(
            "Event mode enabled: duration=%.2fs frequency=%.2fHz amplitude=%d",
            args.event_duration,
            args.event_frequency,
            args.event_amplitude,
        )

    credentials = pika.PlainCredentials(args.user, args.password)
    params = pika.ConnectionParameters(
        host=args.host,
        port=args.port,
        virtual_host=args.vhost,
        credentials=credentials,
    )

    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    logging.debug("AMQP connection established")

    if args.exchange:
        channel.exchange_declare(
            exchange=args.exchange, exchange_type="topic", durable=True
        )
        logging.debug("Declared exchange %s", args.exchange)

    total_records = 0
    total_samples = 0
    start_degree = 0
    event_start_sample = 0
    event_active = False

    try:
        chunk_idx = 0
        while RUNNING:
            if args.count and chunk_idx >= args.count:
                break

            chunk_size = args.chunk_samples
            if chunk_size <= 0:
                break
            logging.debug(
                "Chunk %d: chunk_size=%d start_time_ns=%d",
                chunk_idx + 1,
                chunk_size,
                start_time_ns,
            )

            loop_start = time.monotonic()
            traces = MS3TraceList()
            samples = sine_generator(
                start_degree=start_degree,
                batch_size=chunk_size,
                amplitude=args.amplitude,
            )
            if (
                args.event
                and not event_active
                and rng.random() < args.event_probability
            ):
                event_active = True
                event_start_sample = total_samples
                logging.info(
                    "Generating event at sample %d (duration=%d samples)",
                    event_start_sample,
                    event_total_samples,
                )
            if args.event and event_active:
                offset = total_samples - event_start_sample
                event_samples = ricker_generator(
                    start_sample=offset,
                    batch_size=chunk_size,
                    sample_rate=args.sample_rate,
                    frequency=args.event_frequency,
                    amplitude=args.event_amplitude,
                    total_samples=event_total_samples,
                )
                samples = samples + event_samples
                if offset + chunk_size >= event_total_samples:
                    event_active = False
            traces.add_data(
                sourceid=sourceid,
                data_samples=samples,
                sample_type="i",
                sample_rate=args.sample_rate,
                start_time=start_time_ns,
            )

            records = list(
                traces.generate(
                    format_version=format_version,
                    record_length=args.record_length,
                    flush_data=True,
                    flush_idle_seconds=60,
                    removed_packed=True,
                )
            )

            for record in records:
                publish_message(channel, args.exchange, routing_key, record)

            total_records += len(records)
            total_samples += len(samples)
            logging.info(
                "Published chunk %d (%d records, %d samples) to %s",
                chunk_idx + 1,
                len(records),
                len(samples),
                routing_key,
            )

            start_degree += chunk_size
            start_time_ns += int(chunk_size / args.sample_rate * 1_000_000_000)
            chunk_idx += 1

            target = chunk_size / args.sample_rate
            elapsed = time.monotonic() - loop_start
            sleep_for = max(0.0, target - elapsed)
            if sleep_for:
                logging.debug("Sleeping for %.3fs", sleep_for)
                time.sleep(sleep_for)

        logging.info("Done. Total records=%d samples=%d", total_records, total_samples)
    finally:
        connection.close()


if __name__ == "__main__":
    RUNNING = True
    main()
