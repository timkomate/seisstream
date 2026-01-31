from __future__ import annotations

import logging

import pika

from detector.buffer import RollingTraceBuffer
from detector.db import connect as db_connect, insert_picks
from detector.detection import decode_mseed, detect_sta_lta
from detector.settings import Settings, parse_args

def configure_channel(channel: pika.adapters.blocking_connection.BlockingChannel,
                      settings: Settings) -> str:
    channel.basic_qos(prefetch_count=settings.prefetch)
    channel.exchange_declare(exchange=settings.exchange,
                             exchange_type="topic",
                             durable=True)

    exclusive = settings.queue == ""
    result = channel.queue_declare(queue=settings.queue,
                                   durable=not exclusive,
                                   exclusive=exclusive,
                                   auto_delete=exclusive)
    queue_name = result.method.queue

    for key in settings.binding_keys:
        channel.queue_bind(exchange=settings.exchange,
                           queue=queue_name,
                           routing_key=key)
    return queue_name


def main() -> None:
    settings = parse_args()
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logging.debug(f"Settings: {settings}")

    credentials = pika.PlainCredentials(settings.user, settings.password)
    params = pika.ConnectionParameters(
        host=settings.host,
        port=settings.port,
        virtual_host=settings.vhost,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=120,
    )

    buffer = RollingTraceBuffer(settings.buffer_seconds)
    last_detect = {}
    previous_picks = {}

    try:
        db_conn = db_connect(settings)
    except Exception:
        logging.exception("Failed to connect to PostgreSQL")
        return

    try:
        with pika.BlockingConnection(params) as connection:
            channel = connection.channel()
            queue_name = configure_channel(channel, settings)
            logging.info("Consuming from exchange='%s' queue='%s' bindings=%s prefetch=%d",
                         settings.exchange, queue_name, settings.binding_keys, settings.prefetch)

            def on_message(ch, method, properties, body):
                try:
                    traces = decode_mseed(body)
                except Exception:
                    logging.exception("Failed to decode miniSEED from routing key %s", method.routing_key)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return

                for traceid in traces:
                    sid = traceid.sourceid
                    for seg in traceid:
                        samples = seg.create_numpy_array_from_recordlist()
                        if samples is None:
                            logging.warning("No samples for %s segment; skipping", sid)
                            continue

                        start = seg.starttime_seconds
                        end = seg.endtime_seconds
                        samprate = seg.samprate
                        buffer.add_segment(sid, start, end, samprate, samples)
                        buffered_seconds = buffer.get_segment_length(sid) / buffer.get_samplerate(sid)
                        logging.info("Buffered %s: %.2fs", sid, buffered_seconds)
                        if buffered_seconds >= settings.buffer_seconds:
                            last = last_detect.get(sid)
                            if last is None or (end - last) >= settings.detect_every_seconds or end < last:
                                logging.info("Running detector for %s at %.3f (window=%.1fs)", sid, end,
                                             settings.buffer_seconds)
                                triggers = detect_sta_lta(buffer.get(sid), sid)
                                last_detect[sid] = end
                                if len(triggers):
                                    logging.info("Detected %d triggers for %s", len(triggers), sid)
                                    for t_start, t_end in triggers:
                                        logging.info("Trigger %s: %.3f -> %.3f", sid, t_start, t_end)
                                    try:
                                        insert_picks(db_conn, sid, triggers)
                                    except Exception:
                                        logging.exception("Failed to insert picks for %s", sid)

                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=queue_name,
                                  on_message_callback=on_message,
                                  auto_ack=False)
            try:
                channel.start_consuming()
            except KeyboardInterrupt:
                logging.info("Interrupted, stopping consumer")
                channel.stop_consuming()
    finally:
        db_conn.close()


if __name__ == "__main__":
    main()
