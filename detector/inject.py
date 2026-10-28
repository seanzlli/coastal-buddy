"""Inject labelled fake anomalies into the VLE Aveiro history.

Why: the real history contains only one fault type (the weather-feed fallback,
wind 10 / direction 180 / turbidity 1.6), so a detector that only checks that
fingerprint would score 100%. These injections add the incidents a port really
worries about, with a known start and end, so we can measure what the rules
and the predictor actually catch.

Train on the original data before TEST_START; test on the file written here.

Usage (from the repo root):
    .venv/bin/python -m detector.inject
writes data/vle/injected/vle_injected_test.csv     (every row, with labels)
       data/vle/injected/vle_injected_incidents.csv (one row per injected incident)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "data/vle/VLE_Sovereign_Data.csv"
DEFAULT_OUT = ROOT / "data/vle/injected"
TEST_START = "2026-10-18 00:00:00"
PER_TYPE = 4        # incidents per anomaly type
SLOT = 720          # rows between incident starts (~6 h at one reading per 30 s), so they never overlap
SEED = 42           # fixed, so everyone regenerates exactly the same file

# The simulator rounds every column to a fixed resolution. Injected values are
# rounded the same way, otherwise a detector could spot them by their decimals.
DECIMALS = {"Temp_C": 2, "pH": 2, "Salinity_PSU": 1, "Turbidity_NTU": 1, "Bio_Load_kgm2": 2}


def envelope(up, hold, down):
    """How strongly an incident is present per row: ramp up, plateau, ramp down."""
    return np.concatenate([np.linspace(0, 1, up, endpoint=False), np.ones(hold), np.linspace(1, 0, down)])


def add(df, i0, col, delta):
    """Add delta (one value per row) to col starting at row i0, rounded like the sensor."""
    rows = slice(i0, i0 + len(delta))
    j = df.columns.get_loc(col)
    df.iloc[rows, j] = (df.iloc[rows, j].to_numpy() + delta).round(DECIMALS[col])
    return i0 + len(delta) - 1


# Each injector changes df in place from row i0 and returns
# (measures, last row, description). LENGTH is the number of rows it touches.

def acid_spill(df, i0, rng):
    w = envelope(20, 120, 20)
    target = rng.uniform(7.65, 7.75)
    ph = df["pH"].iloc[i0 : i0 + len(w)].to_numpy()
    end = add(df, i0, "pH", (target - ph) * w)
    return "pH", end, f"pH falls to {target:.2f} for 1 h (chemical spill)"


def dredging(df, i0, rng):
    w = envelope(10, 90, 20)
    amp = rng.uniform(3.0, 4.5)
    end = add(df, i0, "Turbidity_NTU", amp * w)
    return "Turbidity_NTU", end, f"turbidity +{amp:.1f} NTU with calm wind for 45 min (dredging / sediment)"


def freshwater_pulse(df, i0, rng):
    w = envelope(30, 120, 120)
    drop = rng.uniform(3.0, 4.5)
    add(df, i0, "Salinity_PSU", -drop * w)
    add(df, i0, "Turbidity_NTU", 1.0 * w)
    end = add(df, i0, "Temp_C", -0.5 * w)
    return "Salinity_PSU,Turbidity_NTU,Temp_C", end, f"salinity -{drop:.1f} PSU, turbidity +1, temp -0.5 (sewage overflow / fresh-water pulse)"


def thermal_discharge(df, i0, rng):
    w = envelope(20, 240, 40)
    rise = rng.uniform(1.8, 2.3)
    end = add(df, i0, "Temp_C", rise * w)
    return "Temp_C", end, f"temperature +{rise:.1f} °C for 2 h, still inside the normal range (cooling-water discharge)"


def spike(df, i0, rng):
    jump = rng.uniform(4.0, 5.0) * rng.choice([-1, 1])
    end = add(df, i0, "Temp_C", np.array([jump]))
    return "Temp_C", end, f"one temperature reading {jump:+.1f} °C (sensor glitch)"


def stuck(df, i0, rng):
    temp = df["Temp_C"].iloc[i0 : i0 + 120].to_numpy()
    end = add(df, i0, "Temp_C", temp[0] - temp)
    return "Temp_C", end, f"temperature frozen at {temp[0]:.2f} °C for 1 h (stuck sensor)"


def drift(df, i0, rng):
    # +0.005 PSU per reading for 2 h, then the sensor is recalibrated (back to normal)
    end = add(df, i0, "Salinity_PSU", 0.005 * np.arange(1, 241))
    return "Salinity_PSU", end, "salinity creeps up +1.2 PSU over 2 h (calibration drift)"


def gap(df, i0, rng):
    # The rows are only marked here; main() deletes them after all injections,
    # so row positions stay valid while injecting. The label goes on the first
    # reading after the gap, because that is when a detector can notice it.
    df.loc[df.index[i0 : i0 + 20], "_drop"] = True
    return "all", i0 + 20, "no readings for 10 min (feed gap)"


INJECTORS = {
    # name: (function, difficulty, rows it needs)
    "acid_spill": (acid_spill, "easy", 160),
    "spike": (spike, "easy", 1),
    "gap": (gap, "easy", 21),
    "dredging": (dredging, "medium", 120),
    "freshwater_pulse": (freshwater_pulse, "medium", 270),
    "stuck": (stuck, "medium", 120),
    "thermal_discharge": (thermal_discharge, "hard", 300),
    "drift": (drift, "hard", 240),
}


def fallback_rows(df):
    """The weather-feed fallback fault that already exists in the real data."""
    return (df["Wind_Speed_ms"] == 10) & (df["Wind_Dir_Deg"] == 180) & (df["Turbidity_NTU"] == 1.6)


def can_place(df, name, i0, n, fallback):
    lo, hi = max(i0 - 10, 0), i0 + n + 10
    if hi >= len(df) or fallback.iloc[lo:hi].any():
        return False  # keep injections away from the real faults, so labels stay unambiguous
    if name == "dredging" and df["Wind_Speed_ms"].iloc[i0 : i0 + n].max() >= 8:
        return False  # "turbidity without wind" needs calm wind to make sense
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=DEFAULT_IN)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--start", default=TEST_START)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    full = pd.read_csv(args.input, parse_dates=["Timestamp"])
    df = full[full["Timestamp"] >= args.start].reset_index(drop=True)
    df["_drop"] = False
    fallback = fallback_rows(df)

    # Shuffle the incident types over ~6-hour slots; skip the first 3 h of the window.
    todo = [name for name in INJECTORS for _ in range(PER_TYPE)]
    rng.shuffle(todo)
    incidents = []
    for slot_start in range(360, len(df) - SLOT, SLOT):
        placed = False
        for k, name in enumerate(todo):  # if one type doesn't fit here (e.g. no calm wind), try the next
            fn, level, n = INJECTORS[name]
            for shift in range(0, SLOT - n - 20, 30):  # slide within the slot until it fits
                i0 = slot_start + shift
                if can_place(df, name, i0, n, fallback):
                    measures, end, desc = fn(df, i0, rng)
                    incidents.append(dict(type=name, level=level, measures=measures,
                                          start_ID=int(df.at[i0, "ID"]), end_ID=int(df.at[end, "ID"]), description=desc))
                    todo.pop(k)
                    placed = True
                    break
            if placed:
                break
    if todo:
        print(f"warning: {len(todo)} incidents did not fit: {todo}")

    # Labels per row. Original fallback faults keep their own label, so a
    # detector is not punished for catching a real fault.
    df["label"] = "normal"
    df["anomaly_type"] = ""
    df["incident_id"] = ""
    df["level"] = ""
    df["source"] = ""
    fb = fallback_rows(df)
    df.loc[fb, ["label", "anomaly_type", "incident_id", "level", "source"]] = ["anomaly", "feed_fallback", "ORIG", "easy", "original"]
    for k, inc in enumerate(sorted(incidents, key=lambda x: x["start_ID"]), 1):
        inc["incident_id"] = f"INJ-{k:02d}"
        rows = df["ID"].between(inc["start_ID"], inc["end_ID"])
        if inc["type"] == "gap":
            rows = df["ID"] == inc["end_ID"]  # the deleted rows are gone; label the reading after
        df.loc[rows, ["label", "anomaly_type", "incident_id", "level", "source"]] = [
            "anomaly", inc["type"], inc["incident_id"], inc["level"], "injected"]

    df = df[~df["_drop"]].drop(columns="_drop")
    inc_df = pd.DataFrame(sorted(incidents, key=lambda x: x["start_ID"]))
    times = full.set_index("ID")["Timestamp"]
    inc_df["start_time"] = inc_df["start_ID"].map(times)
    inc_df["end_time"] = inc_df["end_ID"].map(times)
    inc_df = inc_df[["incident_id", "type", "level", "measures", "start_time", "end_time", "start_ID", "end_ID", "description"]]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "vle_injected_test.csv", index=False)
    inc_df.to_csv(out / "vle_injected_incidents.csv", index=False)
    print(f"{len(df)} rows, {len(inc_df)} injected incidents, {int(fb.sum())} original fallback faults -> {out}")
    print(inc_df.groupby(["level", "type"]).size().to_string())


if __name__ == "__main__":
    main()
