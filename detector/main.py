from __future__ import annotations

import logging

import pika

from detector.detector.buffer import RollingTraceBuffer
from detector.detector.db import (
    connect as db_connect,
    insert_event_detections,
    insert_phase_picks,
    insert_picks,
)
from detector.detector.detection import decode_mseed, detect_sta_lta
from detector.detector.picks import filter_phase_picks, filter_picks
from detector.detector.settings import Settings, parse_args
from detector.detector.seisbench_backend import SeisBenchConfig, SeisBenchPredictor

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
    phase_predictor = None
    if settings.detector_mode == "seisbench":
        sb_config = SeisBenchConfig(
            model_class="eqtransformer",
            pretrained=settings.sb_pretrained,
            threshold_p=settings.sb_threshold_p,
            threshold_s=settings.sb_threshold_s,
            detection_threshold=settings.sb_detection_threshold,
            device=settings.sb_device,
        )

        phase_predictor = SeisBenchPredictor(sb_config)
        logging.info(
            "Loaded SeisBench model class=%s pretrained=%s window=%d thresholds(P=%.3f S=%.3f D=%.3f) device=%s",
            sb_config.model_class,
            sb_config.pretrained,
            phase_predictor.input_samples,
            sb_config.threshold_p,
            sb_config.threshold_s,
            sb_config.detection_threshold,
            sb_config.device,
        )
        logging.info(
            "SeisBench readiness uses sample count: required_samples=%d (overrides --buffer-seconds for seisbench mode)",
            phase_predictor.input_samples,
        )

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
                    logging.debug("Data with sid: %s received", sid)
                    for seg in traceid:
                        samples = seg.create_numpy_array_from_recordlist()
                        if samples is None:
                            logging.warning("No samples for %s segment; skipping", sid)
                            continue

                        start = seg.starttime_seconds
                        end = seg.endtime_seconds
                        samprate = seg.samprate
                        buffer.add_segment(sid, start, samprate, samples)
                        buffered_samples = buffer.get_segment_length(sid)
                        buffered_seconds = buffered_samples / buffer.get_samplerate(sid)
                        logging.debug(
                            "Buffered %s: samples=%d seconds=%.2f",
                            sid,
                            buffered_samples,
                            buffered_seconds,
                        )
                        mode_ready = False
                        if settings.detector_mode == "seisbench":
                            mode_ready = phase_predictor is not None and buffered_samples >= phase_predictor.input_samples
                        else:
                            mode_ready = buffered_seconds >= settings.buffer_seconds

                        if mode_ready:
                            if settings.detector_mode == "seisbench":
                                if phase_predictor is None:
                                    continue
                                parsed = buffer.parse_sid(sid)
                                if not parsed:
                                    logging.warning("Unable to parse source id for SeisBench: %s", sid)
                                    continue
                                net, sta, loc, _chan = parsed
                                station_buffers = buffer.get_station_buffers(net, sta, loc)
                                if not station_buffers:
                                    logging.debug("No station buffers available for %s.%s.%s", net, sta, loc)
                                    continue
                                station_buffers.sort(key=lambda item: item[0])
                                segments = [seg for _sid, seg in station_buffers]
                                channels = [seg_id for seg_id, _seg in station_buffers]
                                ready_samples = [seg["samples"].size for seg in segments]
                                if min(ready_samples) < phase_predictor.input_samples:
                                    logging.debug(
                                        "Skipping detector for %s.%s.%s: channel buffers not ready min_samples=%d required_samples=%d per_channel=%s",
                                        net,
                                        sta,
                                        loc,
                                        min(ready_samples),
                                        phase_predictor.input_samples,
                                        ready_samples,
                                    )
                                    continue
                                group_end = max(seg["end"] for seg in segments)
                                group_key = f"{net}.{sta}.{loc}"
                                last = last_detect.get(group_key)
                                if last is None or (group_end - last) >= settings.detect_every_seconds or group_end < last:
                                    samprate = segments[0]["samprate"]
                                    window_seconds = phase_predictor.input_samples / samprate
                                    logging.info(
                                        "Running detector for %s at %.3f (window=%d samples, %.1fs channels=%d)",
                                        group_key,
                                        group_end,
                                        phase_predictor.input_samples,
                                        window_seconds,
                                        len(segments),
                                    )
                                    triggers, detections = phase_predictor.predict_multichannel(
                                        segments,
                                        channels,
                                        samprate,
                                    )
                                    logging.info(
                                        "Detector raw result for %s: triggers=%d detections=%d",
                                        group_key,
                                        len(triggers),
                                        len(detections),
                                    )

                                    last_detect[group_key] = group_end
                                    sid_for_db = channels[0]
                                    if len(detections):
                                        try:
                                            insert_event_detections(db_conn, sid_for_db, detections)
                                            logging.debug(
                                                "Inserted %d event detections for %s",
                                                len(detections),
                                                sid_for_db,
                                            )
                                        except Exception:
                                            logging.exception(
                                                "Failed to insert event detections for %s", sid_for_db
                                            )
                                    else:
                                        logging.debug(
                                            "No detections produced for %s with current thresholds/window.",
                                            group_key,
                                        )
                                    if len(triggers):
                                        logging.info("Detector returned %d phase picks for %s", len(triggers), group_key)
                                        logging.debug("Raw triggers for %s: %s", group_key, triggers)
                                        last_ts_on = previous_picks.get(group_key)
                                        filtered, last_ts_on = filter_phase_picks(
                                            triggers,
                                            last_ts_on,
                                            settings.pick_filter_seconds,
                                        )
                                        previous_picks[group_key] = last_ts_on
                                        dropped = len(triggers) - len(filtered)
                                        logging.debug(
                                            "Pick filter for %s kept=%d dropped=%d window=%.2fs last_ts_on=%.3f",
                                            group_key,
                                            len(filtered),
                                            dropped,
                                            settings.pick_filter_seconds,
                                            last_ts_on if last_ts_on is not None else -1.0,
                                        )
                                        if filtered:
                                            logging.debug("Filtered triggers for %s: %s", group_key, filtered)
                                        if not filtered:
                                            logging.debug(
                                                "All triggers for %s discarded within %.2fs dedupe window",
                                                group_key,
                                                settings.pick_filter_seconds,
                                            )
                                            continue
                                        triggers = filtered
                                        logging.debug("Detected %d triggers for %s", len(triggers), group_key)
                                        for trigger in triggers:
                                            t_start = trigger[0]
                                            phase = trigger[1]
                                            logging.debug("Trigger %s: %.3f phase=%s", group_key, t_start, phase)
                                        try:
                                            logging.debug(
                                                "Inserting %d phase picks for %s", len(triggers), sid_for_db
                                            )
                                            insert_phase_picks(db_conn, sid_for_db, triggers)
                                            logging.debug(
                                                "Inserted %d phase picks for %s",
                                                len(triggers),
                                                sid_for_db,
                                            )
                                        except Exception:
                                            logging.exception("Failed to insert phase picks for %s", sid_for_db)
                                    else:
                                        logging.debug(
                                            "No triggers produced for %s with current thresholds/window.",
                                            group_key,
                                        )
                                else:
                                    logging.debug(
                                        "Skipping detector for %s: cooldown active %.2fs < %.2fs",
                                        group_key,
                                        group_end - last,
                                        settings.detect_every_seconds,
                                    )
                            else:
                                last = last_detect.get(sid)
                                if last is None or (end - last) >= settings.detect_every_seconds or end < last:
                                    logging.info("Running STA/LTA detector for %s at %.3f (window=%.1fs)", sid, end,
                                                 settings.buffer_seconds)
                                    triggers = detect_sta_lta(
                                        buffer.get(sid),
                                        sid,
                                        settings.preprocess_fmin,
                                        settings.preprocess_fmax,
                                        settings.sta_seconds,
                                        settings.lta_seconds,
                                        settings.trigger_on,
                                        settings.trigger_off,
                                    )
                                    last_detect[sid] = end
                                    if len(triggers):
                                        logging.info("Detector returned %d STA/LTA windows for %s", len(triggers), sid)
                                        logging.debug("Raw triggers for %s: %s", sid, triggers)
                                        last_ts_on = previous_picks.get(sid)
                                        filtered, last_ts_on = filter_picks(
                                            triggers,
                                            last_ts_on,
                                            settings.pick_filter_seconds,
                                        )
                                        previous_picks[sid] = last_ts_on
                                        dropped = len(triggers) - len(filtered)
                                        logging.debug(
                                            "Pick filter for %s kept=%d dropped=%d window=%.2fs last_ts_on=%.3f",
                                            sid,
                                            len(filtered),
                                            dropped,
                                            settings.pick_filter_seconds,
                                            last_ts_on if last_ts_on is not None else -1.0,
                                        )
                                        if filtered:
                                            logging.debug("Filtered triggers for %s: %s", sid, filtered)
                                        if not filtered:
                                            logging.debug(
                                                "All triggers for %s discarded within %.2fs dedupe window",
                                                sid,
                                                settings.pick_filter_seconds,
                                            )
                                            continue
                                        triggers = filtered
                                        logging.debug("Detected %d triggers for %s", len(triggers), sid)
                                        for t_start, t_end in triggers:
                                            logging.debug("Trigger %s: %.3f -> %.3f", sid, t_start, t_end)
                                        try:
                                            logging.debug("Inserting %d picks for %s", len(triggers), sid)
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
