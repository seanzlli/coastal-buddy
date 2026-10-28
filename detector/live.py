"""Run the rule-based detector on the live feed and push results to the dashboard.

It reads through our own backend (not VLE directly), so anything the backend
changes, such as an injected demo anomaly later, is seen exactly like the dashboard sees it.

Every new reading: take the last 3 hours from the backend, run detector/rules.py,
and POST the agreed JSON to the backend's /api/detector. If no new reading
arrives for 4 minutes, it reports the feed as stalled.

Usage (from the repo root, with the backend running):
    .venv/bin/python -m detector.live
"""
import argparse
import time
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd

from detector.rules import KEY, detect, since, turbidity_error

API_TO_CSV = {v: k for k, v in KEY.items()}
BUFFER = pd.Timedelta("3h")  # longest rule looks back 2 h; keep a margin
# VLE timestamps are local time UTC+1. Stamp our checks the same way, so they line
# up on any server (Render's clock runs on UTC).
FEED_TZ = timezone(timedelta(hours=1))
POLL_SECONDS = 10            # VLE posts every ~30 s, so we never miss one by much
STALL_SECONDS = 240          # no new reading for 4 min = feed stalled (largest normal gap: 182 s)


def to_frame(points):
    """API readings (temp, sal, ...) -> DataFrame with CSV column names and a time index."""
    df = pd.DataFrame(points).rename(columns=API_TO_CSV)
    df["Timestamp"] = pd.to_datetime(df["time"])
    df = df.drop_duplicates("Timestamp").set_index("Timestamp").sort_index()
    return df[[c for c in API_TO_CSV.values() if c in df.columns]]


def build_payload(buf, reading_time, ongoing):
    """`ongoing` remembers when each still-active anomaly started. Without it, a
    long event's start would slide along with the 3-hour buffer and look new."""
    anomalies = []
    active = set()
    for kind, col, mask, msg in detect(buf):
        mask = mask.fillna(False)
        if mask.iloc[-1]:
            key = (kind, col)
            active.add(key)
            if key not in ongoing:
                start = since(mask, buf.index)
                ongoing[key] = start.strftime("%Y-%m-%d %H:%M:%S") if start is not None else reading_time
            anomalies.append({"measure": KEY.get(col, col), "type": kind, "message": msg, "since": ongoing[key]})
    for key in set(ongoing) - active:
        del ongoing[key]
    err = turbidity_error(buf).iloc[-1]
    return {
        "checked_at": datetime.now(FEED_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "reading_time": reading_time,
        "error": {"turb": None if pd.isna(err) else round(float(err), 2)},
        "anomalies": anomalies,
    }


def load_buffer(client, latest=None):
    """The last 3 h of readings from the backend's history, plus the newest one.

    Rebuilt for every new reading instead of only appending to it: when a demo
    injection ends, its fake readings disappear from the history as well, so they
    can't trigger "recovery" alarms 15 minutes or 2 hours later.
    """
    buf = to_frame(client.get("/api/history", params={"range": "1d", "raw": True}).raise_for_status().json())
    if latest is not None:
        buf = pd.concat([buf, to_frame([latest])])
        buf = buf[~buf.index.duplicated(keep="last")].sort_index()
    return buf[buf.index > buf.index[-1] - BUFFER]


def stall_payload(last_time, silent_seconds, ongoing):
    """No new reading for a while: report the feed as stalled *while* it happens,
    instead of only noticing the gap once readings come back."""
    ongoing.setdefault(("gap", "feed"), last_time)
    return {
        "checked_at": datetime.now(FEED_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "reading_time": last_time,
        "error": {},
        "anomalies": [{
            "measure": "feed",
            "type": "gap",
            "message": f"No new reading for {silent_seconds / 60:.0f} min: the data feed has stalled",
            "since": ongoing[("gap", "feed")],
        }],
    }


def run(backend):
    client = httpx.Client(base_url=backend, timeout=60)

    # Wait until the backend answers (on Render it starts in the same process).
    while True:
        try:
            buf = load_buffer(client)
            break
        except (httpx.HTTPError, KeyError, ValueError) as e:
            print(f"waiting for backend: {e}")
            time.sleep(3)
    print(f"buffer: {len(buf)} readings up to {buf.index[-1]}")
    last_time, last_new = None, time.monotonic()
    ongoing = {}

    while True:
        try:
            latest = client.get("/api/latest").raise_for_status().json()
            payload = None
            if latest["time"] != last_time:
                last_time, last_new = latest["time"], time.monotonic()
                payload = build_payload(load_buffer(client, latest), latest["time"], ongoing)
            elif time.monotonic() - last_new > STALL_SECONDS:
                payload = stall_payload(last_time, time.monotonic() - last_new, ongoing)
            if payload:
                client.post("/api/detector", json=payload).raise_for_status()
                found = ", ".join(f"{a['type']}:{a['measure']}" for a in payload["anomalies"]) or "none"
                print(f"{payload['reading_time']}  anomalies: {found}")
        except (httpx.HTTPError, KeyError, ValueError) as e:
            print(f"warning: {e}")  # keep running; the dashboard shows the feed as stalled
        time.sleep(POLL_SECONDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="http://127.0.0.1:8000")
    run(ap.parse_args().backend)


if __name__ == "__main__":
    main()
