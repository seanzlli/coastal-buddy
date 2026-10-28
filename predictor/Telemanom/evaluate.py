"""Measure detection with synthetic anomalies injected into the test period.

The VLE data has no anomaly labels, so this plants known ones and checks what
the detector finds. Each trial injects one anomaly type at one size into one
channel, at ~15 places spread over the test period, then scores the test
period exactly as train.py does.

Anomaly types (sizes are in training standard deviations of that channel):
    spike  one reading (30 s) jumps by +/- size
    drift  the reading slides linearly away by size over 4 hours
    stuck  the sensor repeats one value for 4 hours

An event counts as caught if the channel is flagged while it is happening
(spikes get 100 steps after, since the smoothed error lags). A false alarm is
a flagged run in that channel that touches no event, including 100 steps after
it ends, so the jump back to normal is not counted against the detector.

The same scoring is also run on a persistence forecaster ("next value = last
value"), to show what the LSTM adds.

Usage (from this folder):
    python evaluate.py                  # evaluates runs/default
    python evaluate.py --name h128x128
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from model import ModelConfig, TelemanomLSTM, _groups, detect
from train import DEFAULT_DATA, HERE, TARGETS, load_data, make_windows, predict_next

SPIKE_SIZES = [1.0, 3.0, 6.0]
DRIFT_SIZES = [1.0, 3.0]
EVENT_LEN = 480  # 4 hours of 30 s steps, for drift and stuck
GAP = 1100  # steps between event starts, longer than the 250-step input window
GRACE = 100


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", default="default", help="run folder under ./runs")
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def inject(series: np.ndarray, starts: np.ndarray, kind: str, size: float, rng) -> list[tuple[int, int]]:
    """Modify series in place; returns each event's (start, end) inclusive."""
    events = []
    for s in starts:
        if kind == "spike":
            series[s] += rng.choice([-1, 1]) * size
            events.append((s, s))
        elif kind == "drift":
            series[s : s + EVENT_LEN] += rng.choice([-1, 1]) * np.linspace(0, size, EVENT_LEN)
            events.append((s, s + EVENT_LEN - 1))
        elif kind == "stuck":
            series[s : s + EVENT_LEN] = series[s]
            events.append((s, s + EVENT_LEN - 1))
    return events


def score_events(flags: np.ndarray, events: list[tuple[int, int]], kind: str) -> tuple[int, int]:
    """(events caught, false-alarm runs) for one channel's flags."""
    caught = 0
    for s, e in events:
        end = e + GRACE if kind == "spike" else e
        caught += bool(flags[s : end + 1].any())
    covered = np.zeros(len(flags), dtype=bool)
    for s, e in events:
        covered[s : e + GRACE + 1] = True
    runs = _groups(np.where(flags)[0])
    false_alarms = sum(not covered[s : e + 1].any() for s, e in runs)
    return caught, false_alarms


def main():
    args = parse_args()
    run_dir = HERE / "runs" / args.name
    ckpt = torch.load(run_dir / "model.pt", map_location=args.device, weights_only=False)
    run_args = ckpt["args"]
    l_s, n_pred = ckpt["l_s"], ckpt["config"]["n_predictions"]
    span, window = int(run_args["smoothing_span"]), int(run_args["threshold_window"])

    model = TelemanomLSTM(ModelConfig(**ckpt["config"])).to(args.device)
    model.load_state_dict(ckpt["state_dict"])

    df, _ = load_data(args.data, ckpt["freq"])
    mean, std = pd.Series(ckpt["mean"]), pd.Series(ckpt["std"])
    resolution = pd.Series(ckpt["resolution"])
    n = len(df)
    test_start = int(n * (1 - float(run_args["val_frac"]) - float(run_args["test_frac"]))) + int(
        n * float(run_args["val_frac"])
    )
    clean = ((df - mean) / std).to_numpy(dtype=np.float32)
    # Each channel's sensor step in standardised units: floors the threshold
    # and rounds injected values so they look like real readings.
    step = (resolution / std[TARGETS]).to_numpy()

    def run(data: np.ndarray) -> dict[str, np.ndarray]:
        """Flags over the test period for the LSTM and for persistence."""
        t = torch.tensor(data, device=args.device)
        x, y = make_windows(t, len(TARGETS), l_s, n_pred)
        first = test_start - l_s  # first window whose target is in the test period
        x, actual = x[first:], y[first:, 0]
        lstm_err = (predict_next(model, x) - actual).cpu().numpy()
        persist_err = (x[:, -1, : len(TARGETS)] - actual).cpu().numpy()
        return {
            name: detect(err, span, window, sensor_step=step)[2]
            for name, err in [("lstm", lstm_err), ("persistence", persist_err)]
        }

    test_len = n - test_start - n_pred + 1
    test_days = test_len * pd.Timedelta(ckpt["freq"]) / pd.Timedelta("1D")
    baseline = run(clean)
    rows = []
    for c, name in enumerate(TARGETS):
        for det, flags in baseline.items():
            _, fa = score_events(flags[:, c], [], "spike")
            rows.append({"detector": det, "channel": name, "kind": "none", "size": 0, "events": 0,
                         "caught": 0, "false_alarms": fa})

    rng = np.random.default_rng(args.seed)
    trials = [("spike", s) for s in SPIKE_SIZES] + [("drift", s) for s in DRIFT_SIZES] + [("stuck", 0.0)]
    for c, name in enumerate(TARGETS):
        for kind, size in trials:
            starts = np.arange(300, test_len - EVENT_LEN - 300, GAP) + rng.integers(0, 200)
            data = clean.copy()
            col = data[test_start:, c]
            events = inject(col, starts, kind, size, rng)
            data[test_start:, c] = clean[test_start:, c] + np.round((col - clean[test_start:, c]) / step[c]) * step[c]
            for det, flags in run(data).items():
                caught, fa = score_events(flags[:, c], events, kind)
                rows.append({"detector": det, "channel": name, "kind": kind, "size": size,
                             "events": len(events), "caught": caught, "false_alarms": fa})
            print(f"{name:14s} {kind:5s} {size:3.0f}  done")

    res = pd.DataFrame(rows)
    res.to_csv(run_dir / "eval_injected.csv", index=False)

    injected = res[res.kind != "none"].copy()
    injected["label"] = injected.kind + np.where(injected.kind == "stuck", "", " " + injected["size"].map("{:g}σ".format))
    recall = injected.groupby(["label", "detector"])[["caught", "events"]].sum()
    table = (recall.caught / recall.events).unstack("detector").round(2)
    per_channel = injected.assign(r=injected.caught / injected.events).pivot_table(
        index="label", columns=["detector", "channel"], values="r"
    ).round(2)
    fa_day = (res[res.kind == "none"].set_index(["detector", "channel"]).false_alarms / test_days).round(2)

    print(f"\nTest period: {test_days:.1f} days\n")
    print("Share of injected events caught (all channels):")
    print(table.to_string())
    print("\nCaught per channel, LSTM:")
    print(per_channel["lstm"].to_string())
    print("\nFalse alarms per day on clean test data:")
    print(fa_day.unstack("detector").to_string())
    print(f"\nsaved {run_dir / 'eval_injected.csv'}")


if __name__ == "__main__":
    main()
