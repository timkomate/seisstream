from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from obspy import Stream, Trace, UTCDateTime

from .utils import parse_sid

logger = logging.getLogger("detector.seisbench")


@dataclass
class SeisBenchConfig:
    model_class: str = "eqtransformer"
    pretrained: str = "original"
    threshold_p: float = 0.3
    threshold_s: float = 0.3
    detection_threshold: float = 0.3
    device: str = "cpu"


class SeisBenchPredictor:
    def __init__(self, config: SeisBenchConfig):
        self.config = config

        import seisbench.models as sbm

        model_class = config.model_class.lower()
        if model_class == "eqtransformer":
            self.model = sbm.EQTransformer.from_pretrained(config.pretrained)
        else:
            raise ValueError(
                f"Unsupported SeisBench model_class='{config.model_class}'. "
                "Only 'eqtransformer' is supported."
            )

        # Most SeisBench models expose a fixed in_samples.
        self.input_samples = int(getattr(self.model, "in_samples", 0) or 0)
        if self.input_samples <= 0:
            raise ValueError(
                "Loaded SeisBench model does not expose a valid in_samples value."
            )

        desired_device = config.device.lower()
        if desired_device == "cuda":
            import torch

            if not torch.cuda.is_available():
                logger.warning("CUDA requested but unavailable; using CPU.")
                desired_device = "cpu"
        self.device = desired_device
        self.model.to(self.device)
        self.model.eval()
        logger.info(
            "SeisBench predictor initialized model=%s pretrained=%s device=%s input_samples=%d "
            "thresholds(P=%.3f S=%.3f D=%.3f)",
            self.config.model_class,
            self.config.pretrained,
            self.device,
            self.input_samples,
            self.config.threshold_p,
            self.config.threshold_s,
            self.config.detection_threshold,
        )

    def _build_multichannel_window(
        self,
        segments: List[Dict],
        channels: List[str],
        samprate: float,
    ) -> Optional[Tuple[np.ndarray, float]]:
        if not segments:
            return None

        window_samples = self.input_samples
        common_end = min(seg["end"] for seg in segments)
        data = np.zeros((len(segments), window_samples), dtype=np.float32)

        for idx, seg in enumerate(segments):
            samples = seg["samples"]
            end_time = seg["end"]
            offset = int(round((end_time - common_end) * samprate))
            if offset >= 0:
                usable = samples[: max(len(samples) - offset, 0)]
            else:
                usable = samples
            if usable.size >= window_samples:
                window = usable[-window_samples:]
            else:
                pad = window_samples - usable.size
                window = np.concatenate((np.zeros(pad, dtype=usable.dtype), usable))
            data[idx, :] = window

        logger.debug(
            "Built SeisBench window channels=%d samples=%d samprate=%.2f common_end=%.3f channel_ids=%s",
            len(channels),
            window_samples,
            samprate,
            common_end,
            channels,
        )
        return data, common_end

    # TODO:
    # Eventually I want to drop obspy dependency.
    # The biggest work here is to update seisbench...
    # Seisbench Waveform class should be overwritten here somehow.
    def _build_stream(
        self,
        window: np.ndarray,
        channels: List[str],
        window_end: float,
        samprate: float,
    ) -> Stream:
        st = Stream()
        window_start = window_end - (window.shape[1] / samprate)
        for idx, sid in enumerate(channels):
            parsed = parse_sid(sid)
            net, sta, loc, chan = parsed

            tr = Trace(data=window[idx].astype(np.float32))
            tr.stats.network = net
            tr.stats.station = sta
            tr.stats.location = loc
            tr.stats.channel = chan
            tr.stats.sampling_rate = samprate
            tr.stats.starttime = UTCDateTime(window_start)
            st += tr
        return st

    def predict_multichannel(
        self,
        segments: List[Dict],
        channels: List[str],
        samprate: float,
    ) -> Tuple[List[Tuple[float, str, Optional[float]]], List[Tuple[float, float]]]:
        built = self._build_multichannel_window(segments, channels, samprate)
        if built is None:
            logger.debug("Skipping SeisBench classify: no segments available")
            return [], []
        window, common_end = built
        stream = self._build_stream(window, channels, common_end, samprate)
        logger.debug(
            "Calling SeisBench classify traces=%d start=%s end=%s",
            len(stream),
            stream[0].stats.starttime if len(stream) else "n/a",
            stream[0].stats.endtime if len(stream) else "n/a",
        )

        result = self.model.classify(
            stream,
            P_threshold=self.config.threshold_p,
            S_threshold=self.config.threshold_s,
            detection_threshold=self.config.detection_threshold,
        )

        raw_picks = getattr(result, "picks", [])
        raw_detections = getattr(result, "detections", [])
        logger.debug("SeisBench classify returned raw_picks=%d", len(raw_picks))
        logger.debug(
            "SeisBench classify returned raw_detections=%d", len(raw_detections)
        )
        picks: List[Tuple[float, str, Optional[float]]] = []
        for pick in raw_picks:
            phase = str(getattr(pick, "phase", "") or "").upper()
            if phase not in {"P", "S"}:
                continue
            peak_time = getattr(pick, "peak_time", None) or getattr(
                pick, "start_time", None
            )
            if peak_time is None:
                continue
            score = getattr(pick, "peak_value", None)
            if score is not None:
                score = float(score)
            picks.append((float(peak_time.timestamp), phase, score))

        picks.sort(key=lambda item: item[0])
        if picks:
            logger.debug(
                "Converted SeisBench picks=%d first_pick=(%.3f,%s)",
                len(picks),
                picks[0][0],
                picks[0][1],
            )
        else:
            logger.debug("Converted SeisBench picks=0 after phase/time filtering")
        detections: List[Tuple[float, float]] = []
        for detection in raw_detections:
            start_time = getattr(detection, "start_time", None)
            end_time = getattr(detection, "end_time", None)
            if start_time is None or end_time is None:
                continue
            detections.append(
                (
                    float(start_time.timestamp),
                    float(end_time.timestamp),
                )
            )
        detections.sort(key=lambda item: item[0])
        if detections:
            logger.debug(
                "Converted SeisBench detections=%d first_detection=(%.3f -> %.3f)",
                len(detections),
                detections[0][0],
                detections[0][1],
            )
        else:
            logger.debug("Converted SeisBench detections=0 after filtering")

        return picks, detections
