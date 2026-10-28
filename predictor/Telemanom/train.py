"""Train the Telemanom-style LSTM on the VLE SP-02 export and score it.

Usage (from this folder):
    python train.py                     # full run with Telemanom defaults
    python train.py --epochs 2          # quick smoke test

Writes to ./runs/<name>/:
    model.pt     weights, config, feature lists and scaler stats
    scores.csv   per-step predictions, errors, thresholds and anomaly flags
    history.csv  train/val loss per epoch
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from model import ModelConfig, TelemanomLSTM, detect

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parents[1] / "data" / "vle" / "VLE_Sovereign_Data.csv"

# Water-quality channels the model forecasts and scores.
TARGETS = ["Temp_C", "pH", "Salinity_PSU", "Turbidity_NTU", "Bio_Load_kgm2"]
# Extra inputs the model sees but is not scored on, like Telemanom's command channels.
EXOGENOUS = ["Wind_Speed_ms", "Wind_Dir_sin", "Wind_Dir_cos"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--name", default="default", help="run folder name under ./runs")
    p.add_argument("--freq", default="30s", help="resampling interval")
    p.add_argument("--l-s", type=int, default=250, help="input window length (steps)")
    p.add_argument("--n-predictions", type=int, default=10, help="steps predicted ahead")
    p.add_argument("--hidden", type=int, nargs="+", default=[80, 80])
    p.add_argument("--dropout", type=float, default=0.3)
    p.add_argument("--epochs", type=int, default=35)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--min-delta", type=float, default=1e-5)
    p.add_argument("--val-frac", type=float, default=0.15)
    p.add_argument("--test-frac", type=float, default=0.15)
    p.add_argument("--smoothing-span", type=int, default=50, help="EWMA span for errors")
    p.add_argument("--threshold-window", type=int, default=2880, help="steps per threshold window (2880 = 1 day)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def load_data(path: Path, freq: str) -> tuple[pd.DataFrame, pd.Series]:
    """Returns the resampled data and each target's measurement step."""
    df = pd.read_csv(path, parse_dates=["Timestamp"]).set_index("Timestamp")
    df = df.drop(columns=["ID", "Signal_dBM"])  # row counter and a constant
    # Smallest change the sensor reports, e.g. 0.01 for pH. Rounded to drop
    # float noise from the CSV's decimal values.
    steps = df[TARGETS].diff().abs().round(6)
    resolution = steps[steps > 0].min()
    rad = np.deg2rad(df.pop("Wind_Dir_Deg"))
    df["Wind_Dir_sin"], df["Wind_Dir_cos"] = np.sin(rad), np.cos(rad)
    # Readings are ~30 s apart; put them on a regular grid and fill short gaps.
    df = df.resample(freq).mean().interpolate(limit=20).dropna()
    return df[TARGETS + EXOGENOUS], resolution


def make_windows(data: torch.Tensor, n_targets: int, l_s: int, n_pred: int):
    """Sliding windows as views: X (N, l_s, F), Y (N, n_pred, n_targets)."""
    n = len(data) - l_s - n_pred + 1
    x = data.unfold(0, l_s, 1)[:n].transpose(1, 2)
    y = data[l_s:, :n_targets].unfold(0, n_pred, 1)[:n].transpose(1, 2)
    return x, y


def run_epoch(model, x, y, idx, loss_fn, batch_size, opt=None) -> float:
    model.train(opt is not None)
    if opt is not None:
        idx = idx[torch.randperm(len(idx), device=idx.device)]
    total = 0.0
    with torch.set_grad_enabled(opt is not None):
        for b in idx.split(batch_size):
            loss = loss_fn(model(x[b]), y[b])
            if opt is not None:
                opt.zero_grad()
                loss.backward()
                opt.step()
            total += loss.item() * len(b)
    return total / len(idx)


@torch.no_grad()
def predict_next(model, x, batch_size=512) -> torch.Tensor:
    """One-step-ahead predictions (first of the n_predictions) for every window."""
    model.eval()
    return torch.cat([model(x[i : i + batch_size])[:, 0] for i in range(0, len(x), batch_size)])


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    out_dir = HERE / "runs" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    df, resolution = load_data(args.data, args.freq)
    n = len(df)
    n_train = int(n * (1 - args.val_frac - args.test_frac))
    n_val = int(n * args.val_frac)
    print(f"{n} steps at {args.freq}: train {n_train}, val {n_val}, test {n - n_train - n_val}")

    # Scale with training-period statistics only.
    mean, std = df.iloc[:n_train].mean(), df.iloc[:n_train].std().replace(0, 1)
    data = torch.tensor(((df - mean) / std).to_numpy(), dtype=torch.float32, device=args.device)
    x, y = make_windows(data, len(TARGETS), args.l_s, args.n_predictions)

    # Assign each window to the split its first predicted step falls in,
    # so validation and test windows can still look back into earlier data.
    target_pos = torch.arange(len(x), device=args.device) + args.l_s
    train_idx = torch.where(target_pos + args.n_predictions <= n_train)[0]
    val_idx = torch.where((target_pos >= n_train) & (target_pos + args.n_predictions <= n_train + n_val))[0]
    test_idx = torch.where(target_pos >= n_train + n_val)[0]

    cfg = ModelConfig(
        n_inputs=data.shape[1],
        n_outputs=len(TARGETS),
        hidden_sizes=args.hidden,
        dropout=args.dropout,
        n_predictions=args.n_predictions,
    )
    model = TelemanomLSTM(cfg).to(args.device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.MSELoss()

    best_val, best_state, stale, history = float("inf"), None, 0, []
    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(model, x, y, train_idx, loss_fn, args.batch_size, opt)
        val_loss = run_epoch(model, x, y, val_idx, loss_fn, args.batch_size)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"epoch {epoch:3d}  train {train_loss:.5f}  val {val_loss:.5f}")
        if val_loss < best_val - args.min_delta:
            best_val, stale = val_loss, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= args.patience:
                print(f"early stop: no val improvement for {args.patience} epochs")
                break
    model.load_state_dict(best_state)
    pd.DataFrame(history).to_csv(out_dir / "history.csv", index=False)

    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": asdict(cfg),
            "targets": TARGETS,
            "inputs": TARGETS + EXOGENOUS,
            "mean": mean.to_dict(),
            "std": std.to_dict(),
            "resolution": resolution.to_dict(),
            "l_s": args.l_s,
            "freq": args.freq,
            "args": {k: str(v) for k, v in vars(args).items()},
        },
        out_dir / "model.pt",
    )

    # Score every step that has a full input window behind it.
    pred = predict_next(model, x).cpu().numpy()
    actual = y[:, 0].cpu().numpy()
    errors = pred - actual  # standardised units, so channels are comparable
    # Errors are in standardised units, so express each sensor's step the same way.
    sensor_step = (resolution / std[TARGETS]).to_numpy()
    e_s, thresholds, flags = detect(
        errors, args.smoothing_span, args.threshold_window, sensor_step=sensor_step
    )

    pos = target_pos.cpu().numpy()
    split = np.where(pos < n_train, "train", np.where(pos < n_train + n_val, "val", "test"))
    scores = pd.DataFrame({"Timestamp": df.index[pos], "split": split})
    for c, name in enumerate(TARGETS):
        scores[f"{name}_actual"] = actual[:, c] * std[name] + mean[name]
        scores[f"{name}_pred"] = pred[:, c] * std[name] + mean[name]
        scores[f"{name}_err_smooth"] = e_s[:, c]
        scores[f"{name}_threshold"] = thresholds[:, c]
        scores[f"{name}_anomaly"] = flags[:, c]
    scores.to_csv(out_dir / "scores.csv", index=False)

    test = scores["split"] == "test"
    summary = {
        "best_val_mse": best_val,
        "test_mse_1step": float((errors[test.to_numpy()] ** 2).mean()),
        "persistence_mse_1step": float(
            ((data[pos[test.to_numpy()] - 1, : len(TARGETS)].cpu().numpy() - actual[test.to_numpy()]) ** 2).mean()
        ),
        "flagged_steps": {name: int(scores[f"{name}_anomaly"].sum()) for name in TARGETS},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"saved to {out_dir}")


if __name__ == "__main__":
    main()
