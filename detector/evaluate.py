"""Score the rule-based detector on the real history and on the injected test set.

Reported per incident (did any fault rule fire inside the incident window?)
because that is what an operator cares about: "was I warned?". False alarms are
counted as alarm episodes on normal rows, per day.

Usage (from the repo root):  .venv/bin/python -m detector.evaluate
"""
from pathlib import Path

import pandas as pd

from detector.rules import EVENT_TYPES, detect

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    df = pd.read_csv(path, parse_dates=["Timestamp"]).set_index("Timestamp", drop=False)
    return df


def fault_flags(df):
    """One boolean per row: did any fault rule (not an event) fire?"""
    flags = pd.Series(False, index=df.index)
    for kind, _col, mask, _msg in detect(df):
        if kind not in EVENT_TYPES:
            flags |= mask.fillna(False).to_numpy()
    return flags


def episodes(mask):
    """Number of separate runs of True values."""
    return int((mask & ~mask.shift(fill_value=False)).sum())


def history_check():
    df = load(ROOT / "data/vle/VLE_Sovereign_Data.csv")
    df = df[df.index >= "2026-09-17 13:30"]  # skip the start-up phase the analysis marked uncertain
    flags = fault_flags(df).to_numpy()
    fb = ((df.Wind_Speed_ms == 10) & (df.Wind_Dir_Deg == 180) & (df.Turbidity_NTU == 1.6)).to_numpy()
    trick = ((df.Wind_Speed_ms == 10) & (df.Turbidity_NTU == 1.6) & (df.Wind_Dir_Deg != 180)).to_numpy()
    other = pd.Series(flags & ~fb, index=df.index)
    days = (df.index[-1] - df.index[0]).total_seconds() / 86400
    print("REAL HISTORY")
    print(f"  fallback faults caught:          {int((flags & fb).sum())} / {int(fb.sum())}")
    print(f"  trick rows (real wind 10) flagged: {int((flags & trick).sum())} / {int(trick.sum())}")
    print(f"  other alarm episodes:              {episodes(other)} in {days:.0f} days")


def injected_check():
    df = load(ROOT / "data/vle/injected/vle_injected_test.csv")
    inc = pd.read_csv(ROOT / "data/vle/injected/vle_injected_incidents.csv")
    flags = fault_flags(df)
    by_id = pd.Series(flags.to_numpy(), index=df["ID"].to_numpy())
    inc["caught"] = [bool(by_id.loc[r.start_ID : r.end_ID].any()) for r in inc.itertuples()]
    # delay: how long after the incident started the first alarm came
    first = []
    for r in inc.itertuples():
        hit = by_id.loc[r.start_ID : r.end_ID]
        t = df.set_index("ID").loc[hit[hit].index[0], "Timestamp"] if hit.any() else None
        first.append((t - pd.Timestamp(r.start_time)).total_seconds() / 60 if t is not None else None)
    inc["delay_min"] = first

    # The rules look back up to 2 h (plus a 5-min median), so they also see an
    # incident's recovery (e.g. salinity snapping back after recalibration).
    # Alarms in that window after an incident are counted separately, not as false alarms.
    recovery = pd.Series(False, index=df.index)
    for r in inc.itertuples():
        end = pd.Timestamp(r.end_time)
        recovery |= (df.index > end) & (df.index <= end + pd.Timedelta("2h15min"))
    is_normal = (df["label"] == "normal").to_numpy()
    rec = pd.Series(is_normal & recovery.to_numpy() & flags.to_numpy())
    normal = pd.Series(is_normal & ~recovery.to_numpy() & flags.to_numpy())
    days = (df.index[-1] - df.index[0]).total_seconds() / 86400
    print("\nINJECTED TEST SET (per incident)")
    summary = inc.groupby(["level", "type"]).agg(caught=("caught", "sum"), total=("caught", "size"), median_delay_min=("delay_min", "median"))
    print(summary.round(1).to_string())
    print(f"  total caught: {int(inc.caught.sum())} / {len(inc)}")
    print(f"  false alarm episodes on normal rows: {episodes(normal)} in {days:.0f} days")
    print(f"  alarm episodes during the recovery after an incident: {episodes(rec)}")
    return inc


if __name__ == "__main__":
    history_check()
    injected_check()
