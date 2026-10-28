"""Telemanom-style forecaster and anomaly scoring.

Follows Hundman et al. 2018, "Detecting Spacecraft Anomalies Using LSTMs and
Nonparametric Dynamic Thresholding" (NASA Telemanom):

1. An LSTM looks at the last `l_s` steps of all channels and predicts the next
   `n_predictions` steps of the target channels.
2. Prediction errors are smoothed with an exponentially weighted moving average.
3. A threshold is chosen per channel, without labels, as the one whose removal
   of the points above it most reduces the mean and spread of the errors while
   flagging as few points and sequences as possible.
4. Flagged sequences whose peak error is not clearly larger than the next one
   down are pruned as likely false alarms.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
from torch import nn


@dataclass
class ModelConfig:
    n_inputs: int
    n_outputs: int
    hidden_sizes: list[int] = field(default_factory=lambda: [80, 80])
    dropout: float = 0.3
    n_predictions: int = 10


class TelemanomLSTM(nn.Module):
    """Stacked LSTM; the last hidden state maps to the next n_predictions steps.

    Unlike the original, the window is shifted so its last value is zero and the
    model predicts the change from that value. The VLE channels drift (bio load
    only rises, temperature falls with the season), so later data sits outside
    the training range; working in changes keeps the model level-invariant and
    makes "repeat the last value" its starting point. The target channels must
    be the first n_outputs input channels.
    """

    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        layers = []
        in_size = cfg.n_inputs
        for h in cfg.hidden_sizes:
            layers.append(nn.LSTM(in_size, h, batch_first=True))
            in_size = h
        self.lstms = nn.ModuleList(layers)
        self.dropout = nn.Dropout(cfg.dropout)
        self.head = nn.Linear(in_size, cfg.n_predictions * cfg.n_outputs)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, l_s, n_inputs) -> (batch, n_predictions, n_outputs)
        last = x[:, -1:]
        h = x - last
        for lstm in self.lstms:
            h, _ = lstm(h)
            h = self.dropout(h)
        delta = self.head(h[:, -1]).view(-1, self.cfg.n_predictions, self.cfg.n_outputs)
        return last[..., : self.cfg.n_outputs] + delta


# --- Scoring ---------------------------------------------------------------


def smooth_errors(errors: np.ndarray, span: int) -> np.ndarray:
    """EWMA-smooth absolute errors along time; works on 1-D or (time, channels)."""
    return pd.DataFrame(np.abs(errors)).ewm(span=span).mean().to_numpy().squeeze()


def _groups(idx: np.ndarray) -> list[tuple[int, int]]:
    """Consecutive runs in a sorted index array as (start, end) inclusive."""
    if len(idx) == 0:
        return []
    breaks = np.where(np.diff(idx) != 1)[0]
    starts = np.r_[idx[0], idx[breaks + 1]]
    ends = np.r_[idx[breaks], idx[-1]]
    return list(zip(starts.tolist(), ends.tolist()))


def find_threshold(
    e_s: np.ndarray,
    z_range: tuple[float, float, float] = (2.5, 12.0, 0.5),
    error_buffer: int = 100,
    max_sequences: int = 5,
) -> float:
    """Nonparametric dynamic threshold for one channel's smoothed errors."""
    mean, sd = e_s.mean(), e_s.std()
    if sd == 0:
        return float(mean)
    best_score, best_eps = -np.inf, mean + z_range[1] * sd
    for z in np.arange(*z_range):
        eps = mean + z * sd
        below = e_s[e_s < eps]
        above = np.where(e_s >= eps)[0]
        if len(above) == 0 or len(below) == 0:
            continue
        # Pad each flagged point so nearby points merge into one sequence.
        padded = np.unique(
            np.clip(
                (above[:, None] + np.arange(-error_buffer, error_buffer + 1)).ravel(),
                0,
                len(e_s) - 1,
            )
        )
        seqs = [g for g in _groups(padded) if g[0] != g[1]]
        mean_drop = (mean - below.mean()) / mean
        sd_drop = (sd - below.std()) / sd
        score = (mean_drop + sd_drop) / (len(seqs) ** 2 + len(above))
        if score >= best_score and len(seqs) <= max_sequences and len(above) < 0.5 * len(e_s):
            best_score, best_eps = score, eps
    return float(best_eps)


def prune_sequences(
    e_s: np.ndarray, seqs: list[tuple[int, int]], eps: float, p: float = 0.13
) -> list[tuple[int, int]]:
    """Drop flagged sequences whose peak is within p of the next-largest peak."""
    if not seqs:
        return seqs
    peaks = np.array([e_s[s : e + 1].max() for s, e in seqs])
    normal = e_s[e_s < eps]
    floor = normal.max() if len(normal) else 0.0
    order = np.argsort(peaks)[::-1]
    ranked = np.r_[peaks[order], floor]
    keep_upto = -1
    for i in range(len(order)):
        if (ranked[i] - ranked[i + 1]) / ranked[i] >= p:
            keep_upto = i
    # Once a big enough drop is found, everything above it is kept.
    kept = set(order[: keep_upto + 1].tolist())
    return [seq for i, seq in enumerate(seqs) if i in kept]


def detect(
    errors: np.ndarray,
    smoothing_span: int = 50,
    window: int = 2880,
    error_buffer: int = 100,
    p: float = 0.13,
    sensor_step: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run Telemanom scoring on (time, channels) raw prediction errors.

    Thresholds are fitted per channel over consecutive windows (default one
    day of 30 s steps), so they adapt to local noise levels.

    sensor_step (one value per channel, in the same units as errors) floors
    the threshold. Coarse channels such as pH (steps of 0.01 on a range of
    0.04) otherwise flag every routine one-step change. The floor is what two
    unpredicted sensor steps look like after EWMA smoothing, so normal ticks
    never trigger but a jump of several steps still can.

    Returns smoothed errors, per-step thresholds and a boolean anomaly mask,
    each shaped (time, channels).
    """
    errors = errors.reshape(len(errors), -1)
    e_s = smooth_errors(errors, smoothing_span).reshape(errors.shape)
    thresholds = np.zeros_like(e_s)
    flags = np.zeros(e_s.shape, dtype=bool)
    for c in range(e_s.shape[1]):
        for start in range(0, len(e_s), window):
            chunk = e_s[start : start + window, c]
            eps = find_threshold(chunk, error_buffer=error_buffer)
            if sensor_step is not None:
                # A single error of size s peaks at s * 2 / (span + 1) after smoothing.
                eps = max(eps, 2 * float(sensor_step[c]) * 2 / (smoothing_span + 1))
            thresholds[start : start + len(chunk), c] = eps
            above = np.where(chunk >= eps)[0]
            seqs = prune_sequences(chunk, _groups(above), eps, p)
            for s, e in seqs:
                flags[start + s : start + e + 1, c] = True
    return e_s, thresholds, flags
