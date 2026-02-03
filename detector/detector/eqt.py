from __future__ import annotations

import os
import logging
try:
    from importlib import metadata as _metadata
except ImportError:  # pragma: no cover - Python <3.8 fallback
    import importlib_metadata as _metadata  # type: ignore

logger = logging.getLogger("detector.eqt")

_keras_version = None
try:
    _keras_version = _metadata.version("keras")
except _metadata.PackageNotFoundError:
    _keras_version = None

if _keras_version:
    try:
        _keras_major = int(_keras_version.split(".", 1)[0])
    except ValueError:
        _keras_major = 0
    if _keras_major >= 3:
        os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from tensorflow.keras import backend as K
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import InputSpec
from tensorflow import keras


def _normalize(data: np.ndarray, mode: str) -> np.ndarray:
    data = data - np.mean(data, axis=0, keepdims=True)
    if mode == "max":
        max_data = np.max(data, axis=0, keepdims=True)
        max_data[max_data == 0] = 1
        return data / max_data
    elif mode == "std":
        std_data = np.std(data, axis=0, keepdims=True)
        std_data[std_data == 0] = 1
        return data / std_data
    else:
        raise NotImplementedError("mode can be either max or std...")


def _detect_onsets(y: np.ndarray, thresh_on: float, thresh_off: float) -> List[Tuple[int, int]]:
    onsets: List[Tuple[int, int]] = []
    active = False
    start_idx = 0
    for idx, val in enumerate(y):
        if not active and val >= thresh_on:
            active = True
            start_idx = idx
        elif active and val < thresh_off:
            onsets.append((start_idx, idx))
            active = False
    if active:
        onsets.append((start_idx, len(y) - 1))
    return onsets


def _pick_peaks(
    y: np.ndarray,
    thresh_on: float,
    thresh_off: float,
) -> List[int]:
    onsets = _detect_onsets(y, thresh_on, thresh_off)
    peaks: List[int] = []
    for start_idx, end_idx in onsets:
        if end_idx < start_idx:
            continue
        window = y[start_idx : end_idx + 1]
        if window.size == 0:
            continue
        peak_offset = int(np.argmax(window))
        peaks.append(start_idx + peak_offset)
    return peaks


def f1(y_true, y_pred):
    def recall(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
        return true_positives / (possible_positives + K.epsilon())

    def precision(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
        return true_positives / (predicted_positives + K.epsilon())

    precision = precision(y_true, y_pred)
    recall = recall(y_true, y_pred)
    return 2 * ((precision * recall) / (precision + recall + K.epsilon()))


class LayerNormalization(keras.layers.Layer):
    def __init__(
        self,
        center=True,
        scale=True,
        epsilon=None,
        gamma_initializer="ones",
        beta_initializer="zeros",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.supports_masking = True
        self.center = center
        self.scale = scale
        if epsilon is None:
            epsilon = K.epsilon() * K.epsilon()
        self.epsilon = epsilon
        self.gamma_initializer = keras.initializers.get(gamma_initializer)
        self.beta_initializer = keras.initializers.get(beta_initializer)

    def get_config(self):
        config = {
            "center": self.center,
            "scale": self.scale,
            "epsilon": self.epsilon,
            "gamma_initializer": keras.initializers.serialize(self.gamma_initializer),
            "beta_initializer": keras.initializers.serialize(self.beta_initializer),
        }
        base_config = super().get_config()
        return dict(list(base_config.items()) + list(config.items()))

    def compute_output_shape(self, input_shape):
        return input_shape

    def compute_mask(self, inputs, input_mask=None):
        return input_mask

    def build(self, input_shape):
        self.input_spec = InputSpec(shape=input_shape)
        shape = input_shape[-1:]
        if self.scale:
            self.gamma = self.add_weight(
                shape=shape,
                initializer=self.gamma_initializer,
                name="gamma",
            )
        if self.center:
            self.beta = self.add_weight(
                shape=shape,
                initializer=self.beta_initializer,
                name="beta",
            )
        super().build(input_shape)

    def call(self, inputs, training=None):
        mean = K.mean(inputs, axis=-1, keepdims=True)
        variance = K.mean(K.square(inputs - mean), axis=-1, keepdims=True)
        std = K.sqrt(variance + self.epsilon)
        outputs = (inputs - mean) / std
        if self.scale:
            outputs *= self.gamma
        if self.center:
            outputs += self.beta
        return outputs


class FeedForward(keras.layers.Layer):
    def __init__(
        self,
        units,
        activation="relu",
        use_bias=True,
        kernel_initializer="glorot_normal",
        bias_initializer="zeros",
        dropout_rate=0.0,
        **kwargs,
    ):
        self.supports_masking = True
        self.units = units
        self.activation = keras.activations.get(activation)
        self.use_bias = use_bias
        self.kernel_initializer = keras.initializers.get(kernel_initializer)
        self.bias_initializer = keras.initializers.get(bias_initializer)
        self.dropout_rate = dropout_rate
        self.W1, self.b1 = None, None
        self.W2, self.b2 = None, None
        super().__init__(**kwargs)

    def get_config(self):
        config = {
            "units": self.units,
            "activation": keras.activations.serialize(self.activation),
            "use_bias": self.use_bias,
            "kernel_initializer": keras.initializers.serialize(self.kernel_initializer),
            "bias_initializer": keras.initializers.serialize(self.bias_initializer),
            "dropout_rate": self.dropout_rate,
        }
        base_config = super().get_config()
        return dict(list(base_config.items()) + list(config.items()))

    def compute_output_shape(self, input_shape):
        return input_shape

    def compute_mask(self, inputs, input_mask=None):
        return input_mask

    def build(self, input_shape):
        feature_dim = int(input_shape[-1])
        self.W1 = self.add_weight(
            shape=(feature_dim, self.units),
            initializer=self.kernel_initializer,
            name=f"{self.name}_W1",
        )
        if self.use_bias:
            self.b1 = self.add_weight(
                shape=(self.units,),
                initializer=self.bias_initializer,
                name=f"{self.name}_b1",
            )
        self.W2 = self.add_weight(
            shape=(self.units, feature_dim),
            initializer=self.kernel_initializer,
            name=f"{self.name}_W2",
        )
        if self.use_bias:
            self.b2 = self.add_weight(
                shape=(feature_dim,),
                initializer=self.bias_initializer,
                name=f"{self.name}_b2",
            )
        super().build(input_shape)

    def call(self, x, mask=None, training=None):
        h = K.dot(x, self.W1)
        if self.use_bias:
            h = K.bias_add(h, self.b1)
        if self.activation is not None:
            h = self.activation(h)
        if 0.0 < self.dropout_rate < 1.0:
            def dropped_inputs():
                return K.dropout(h, self.dropout_rate, K.shape(h))
            h = K.in_train_phase(dropped_inputs, h, training=training)
        y = K.dot(h, self.W2)
        if self.use_bias:
            y = K.bias_add(y, self.b2)
        return y


class SeqSelfAttention(keras.layers.Layer):
    ATTENTION_TYPE_ADD = "additive"
    ATTENTION_TYPE_MUL = "multiplicative"

    def __init__(
        self,
        units=32,
        attention_width=None,
        attention_type=ATTENTION_TYPE_ADD,
        return_attention=False,
        history_only=False,
        kernel_initializer="glorot_normal",
        bias_initializer="zeros",
        kernel_regularizer=None,
        bias_regularizer=None,
        kernel_constraint=None,
        bias_constraint=None,
        use_additive_bias=True,
        use_attention_bias=True,
        attention_activation=None,
        attention_regularizer_weight=0.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.supports_masking = True
        self.units = units
        self.attention_width = attention_width
        self.attention_type = attention_type
        self.return_attention = return_attention
        self.history_only = history_only
        if history_only and attention_width is None:
            self.attention_width = int(1e9)

        self.use_additive_bias = use_additive_bias
        self.use_attention_bias = use_attention_bias
        self.kernel_initializer = keras.initializers.get(kernel_initializer)
        self.bias_initializer = keras.initializers.get(bias_initializer)
        self.kernel_regularizer = keras.regularizers.get(kernel_regularizer)
        self.bias_regularizer = keras.regularizers.get(bias_regularizer)
        self.kernel_constraint = keras.constraints.get(kernel_constraint)
        self.bias_constraint = keras.constraints.get(bias_constraint)
        self.attention_activation = keras.activations.get(attention_activation)
        self.attention_regularizer_weight = attention_regularizer_weight
        self._backend = keras.backend.backend()

        if attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            self.Wx, self.Wt, self.bh = None, None, None
            self.Wa, self.ba = None, None
        elif attention_type == SeqSelfAttention.ATTENTION_TYPE_MUL:
            self.Wa, self.ba = None, None
        else:
            raise NotImplementedError("No implementation for attention type : " + attention_type)

    def get_config(self):
        config = {
            "units": self.units,
            "attention_width": self.attention_width,
            "attention_type": self.attention_type,
            "return_attention": self.return_attention,
            "history_only": self.history_only,
            "use_additive_bias": self.use_additive_bias,
            "use_attention_bias": self.use_attention_bias,
            "kernel_initializer": keras.regularizers.serialize(self.kernel_initializer),
            "bias_initializer": keras.regularizers.serialize(self.bias_initializer),
            "kernel_regularizer": keras.regularizers.serialize(self.kernel_regularizer),
            "bias_regularizer": keras.regularizers.serialize(self.bias_regularizer),
            "kernel_constraint": keras.constraints.serialize(self.kernel_constraint),
            "bias_constraint": keras.constraints.serialize(self.bias_constraint),
            "attention_activation": keras.activations.serialize(self.attention_activation),
            "attention_regularizer_weight": self.attention_regularizer_weight,
        }
        base_config = super().get_config()
        return dict(list(base_config.items()) + list(config.items()))

    def build(self, input_shape):
        input_dim = int(input_shape[2])
        if self.attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            self.Wx = self.add_weight(
                name="Wx",
                shape=(input_dim, self.units),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                constraint=self.kernel_constraint,
            )
            self.Wt = self.add_weight(
                name="Wt",
                shape=(input_dim, self.units),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                constraint=self.kernel_constraint,
            )
            if self.use_additive_bias:
                self.bh = self.add_weight(
                    name="bh",
                    shape=(self.units,),
                    initializer=self.bias_initializer,
                    regularizer=self.bias_regularizer,
                    constraint=self.bias_constraint,
                )
            self.Wa = self.add_weight(
                name="Wa",
                shape=(self.units, 1),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                constraint=self.kernel_constraint,
            )
            if self.use_attention_bias:
                self.ba = self.add_weight(
                    name="ba",
                    shape=(1,),
                    initializer=self.bias_initializer,
                    regularizer=self.bias_regularizer,
                    constraint=self.bias_constraint,
                )
        else:
            self.Wa = self.add_weight(
                name="Wa",
                shape=(input_dim, input_dim),
                initializer=self.kernel_initializer,
                regularizer=self.kernel_regularizer,
                constraint=self.kernel_constraint,
            )
            if self.use_attention_bias:
                self.ba = self.add_weight(
                    name="ba",
                    shape=(1,),
                    initializer=self.bias_initializer,
                    regularizer=self.bias_regularizer,
                    constraint=self.bias_constraint,
                )
        super().build(input_shape)

    def call(self, inputs, mask=None, training=None):
        if self.attention_type == SeqSelfAttention.ATTENTION_TYPE_ADD:
            q = K.dot(inputs, self.Wt)
            k = K.dot(inputs, self.Wx)
            e = K.expand_dims(q, 2) + K.expand_dims(k, 1)
            if self.use_additive_bias:
                e = K.bias_add(e, self.bh)
            if self.attention_activation is not None:
                e = self.attention_activation(e)
            e = K.reshape(e, (-1, self.units))
            e = K.dot(e, self.Wa)
            e = K.reshape(
                e,
                (K.shape(inputs)[0], K.shape(inputs)[1], K.shape(inputs)[1], 1),
            )
            if self.use_attention_bias:
                e = K.bias_add(e, self.ba)
            e = K.squeeze(e, axis=3)
        else:
            e = K.batch_dot(K.dot(inputs, self.Wa), K.permute_dimensions(inputs, (0, 2, 1)))
        if self.attention_width is not None:
            if self.history_only:
                lower = K.arange(0, K.shape(e)[1]) - (self.attention_width - 1)
            else:
                lower = K.arange(0, K.shape(e)[1]) - (self.attention_width // 2)
            upper = lower + self.attention_width
            indices = K.expand_dims(K.arange(0, K.shape(e)[1]), 1)
            mask = (indices >= lower) & (indices < upper)
            mask = K.expand_dims(mask, 0)
            mask = K.tile(mask, (K.shape(e)[0], 1, 1))
            if K.ndim(e) == 2 and K.ndim(mask) == 3:
                mask = K.any(mask, axis=-1)
            e = K.switch(mask, e, K.zeros_like(e))

        if self._backend == "tensorflow":
            e = e - K.max(e, axis=-1, keepdims=True)
            a = K.exp(e)
        else:
            a = K.exp(e - K.max(e, axis=-1, keepdims=True))
        a /= K.sum(a, axis=-1, keepdims=True) + K.epsilon()
        v = K.batch_dot(a, inputs)
        if self.return_attention:
            return [v, a]
        return v


@dataclass
class EQTConfig:
    model_path: str
    detection_threshold: float
    norm_mode: str
    window_samples: Optional[int] = None


class EQTPredictor:
    def __init__(self, config: EQTConfig):
        self.config = config
        self.model = load_model(
            config.model_path,
            custom_objects={
                "SeqSelfAttention": SeqSelfAttention,
                "FeedForward": FeedForward,
                "LayerNormalization": LayerNormalization,
                "f1": f1,
            },
            compile=False,
        )
        input_shape = self.model.input_shape
        self.input_samples = int(input_shape[1])
        self.input_channels = int(input_shape[2])
        if self.config.window_samples is None:
            self.config.window_samples = self.input_samples
        if self.config.window_samples != self.input_samples:
            logger.warning(
                "EQT window_samples=%d does not match model input=%d; using model input.",
                self.config.window_samples,
                self.input_samples,
            )
            self.config.window_samples = self.input_samples

    def _build_window(self, samples: np.ndarray) -> Optional[np.ndarray]:
        if samples.size < self.config.window_samples:
            return None
        window = samples[-self.config.window_samples :]
        if self.input_channels == 1:
            return window.reshape(-1, 1)
        padded = np.zeros((self.config.window_samples, self.input_channels), dtype=window.dtype)
        padded[:, 0] = window
        return padded

    def _build_multichannel_window(
        self,
        segments: List[Dict],
        channels: List[str],
        samprate: float,
    ) -> Optional[np.ndarray]:
        if not segments:
            return None
        window_samples = self.config.window_samples
        common_end = min(seg["end"] for seg in segments)
        data = np.zeros((window_samples, self.input_channels), dtype=np.float32)

        for idx, seg in enumerate(segments[: self.input_channels]):
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
            data[:, idx] = window

        return data

    def predict(self, segment: dict) -> List[Tuple[float, str]]:
        samples = segment["samples"]
        samprate = segment["samprate"]
        window = self._build_window(samples)
        if window is None:
            return []
        return self._predict_window(window, segment["end"], samprate)

    def predict_multichannel(
        self,
        segments: List[Dict],
        channels: List[str],
        samprate: float,
    ) -> List[Tuple[float, str]]:
        window = self._build_multichannel_window(segments, channels, samprate)
        if window is None:
            return []
        common_end = min(seg["end"] for seg in segments)
        return self._predict_window(window, common_end, samprate)

    def _predict_window(
        self, window: np.ndarray, window_end: float, samprate: float
    ) -> List[Tuple[float, str]]:
        logger.info(
            "EQT _predict_window: window shape=%s end=%.3f samprate=%.2f norm=%s",
            window.shape,
            window_end,
            samprate,
            self.config.norm_mode,
        )
        window = _normalize(window, self.config.norm_mode)
        batch = window[np.newaxis, ...]
        logger.debug("EQT _predict_window: batch shape=%s dtype=%s", batch.shape, batch.dtype)
        predD, predP, predS = self.model.predict(batch, verbose=1)
        logger.debug(
            "EQT _predict_window: predD shape=%s predP shape=%s predS shape=%s",
            predD.shape,
            predP.shape,
            predS.shape,
        )
        if predP.ndim == 3:
            predP = predP[0, :, 0]
        else:
            predP = predP[0]
        if predS.ndim == 3:
            predS = predS[0, :, 0]
        else:
            predS = predS[0]
        logger.debug(
            "EQT _predict_window: predP shape=%s min=%.6f max=%.6f predS shape=%s min=%.6f max=%.6f",
            predP.shape,
            float(np.min(predP)),
            float(np.max(predP)),
            predS.shape,
            float(np.min(predS)),
            float(np.max(predS)),
        )

        logger.debug(
            "EQT _predict_window: predD shape=%s min=%.6f max=%.6f",
            predD.shape,
            float(np.min(predD)),
            float(np.max(predD)),
        )

        p_peaks = _pick_peaks(
            predP,
            self.config.detection_threshold,
            self.config.detection_threshold,
        )
        s_peaks = _pick_peaks(
            predS,
            self.config.detection_threshold,
            self.config.detection_threshold,
        )
        logger.info(
            "EQT _predict_window: detected %d P peaks and %d S peaks",
            len(p_peaks),
            len(s_peaks),
        )
        if not p_peaks and not s_peaks:
            return []
        window_start = window_end - (self.config.window_samples / samprate)
        picks: List[Tuple[float, str]] = []
        for peak_idx in p_peaks:
            t = window_start + (peak_idx / samprate)
            picks.append((t, "P"))
        for peak_idx in s_peaks:
            t = window_start + (peak_idx / samprate)
            picks.append((t, "S"))
        picks.sort(key=lambda item: item[0])
        return picks
