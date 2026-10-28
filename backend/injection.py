"""Demo injections: fake incidents layered on top of the live VLE feed.

Same incident types as detector/inject.py (the offline test set), but squeezed
into a few minutes so the jury can watch one being caught. The backend applies
the active injection to every reading it serves, so the detector and the
dashboard both see it exactly like real data. Injected readings carry
"injected": true, so the dashboard can label them honestly.
"""
from datetime import datetime, timedelta

RAMP = 60  # seconds to fade an incident in and out

# label, what it simulates, how long it lasts (s), which rule catches it,
# and how long that took in our timing test (s), so the demo panel can say which are fast
TYPES = {
    "acid_spill": ("Acid spill", "pH falls to 7.7", 360, "out of range", 10),
    "dredging": ("Dredging", "turbidity +3.5 NTU with no extra wind", 360, "turbidity mismatch", 35),
    "spike": ("Sensor spike", "one temperature reading +4.5 °C", 90, "spike", 38),
    "freshwater_pulse": ("Sewage overflow", "salinity -4, turbidity +1, temperature -0.5", 480, "turbidity mismatch, out of range", 47),
    "thermal_discharge": ("Warm-water discharge", "temperature +2 °C, still in the normal range", 480, "fast change", 180),
    "drift": ("Calibration drift", "salinity creeps up 0.004 PSU per second", 480, "fast change", 261),
    "stuck": ("Stuck sensor", "temperature frozen at its current value", 720, "stuck sensor", 556),
    "gap": ("Feed gap", "no new readings for 6 min", 360, "feed stalled", 298),
}
DECIMALS = {"temp": 2, "ph": 2, "sal": 1, "turb": 1}

_active = None  # the one running injection, or None


def parse_time(t, today):
    """VLE times are 'YYYY-MM-DD HH:MM:SS', except 1H history: 'HH:MM:SS' only."""
    return datetime.strptime(t if len(t) > 8 else f"{today} {t}", "%Y-%m-%d %H:%M:%S")


def start(kind, latest):
    """Begin an injection from the next reading after `latest` (the current one)."""
    global _active
    label, what, duration, detect, catch = TYPES[kind]
    t0 = parse_time(latest["time"], latest["time"][:10]) + timedelta(seconds=1)
    _active = {
        "type": kind, "label": label, "what": what, "detect": detect, "catch_seconds": catch,
        "start": t0, "end": t0 + timedelta(seconds=duration),
        "frozen_temp": latest.get("temp"),  # for "stuck"
        "last_before": dict(latest),        # for "gap": what the feed keeps showing
    }
    return status()


def stop():
    global _active
    _active = None


def status():
    if not _active:
        return None
    fmt = "%Y-%m-%d %H:%M:%S"
    return {k: (v.strftime(fmt) if isinstance(v, datetime) else v)
            for k, v in _active.items() if k not in ("last_before", "frozen_temp", "spike_time")}


def _expire(now_reading_time):
    global _active
    if _active and now_reading_time > _active["end"]:
        _active = None


def _weight(elapsed, duration):
    """0 -> 1 over RAMP seconds, hold, then 1 -> 0 over the last RAMP seconds."""
    return max(0.0, min(1.0, elapsed / RAMP, (duration - elapsed) / RAMP))


def apply(reading, today):
    """Return the reading with the active injection applied (a copy), or as is."""
    if not _active or reading.get("time") is None:
        return reading
    t = parse_time(reading["time"], today)
    if not (_active["start"] <= t <= _active["end"]):
        return reading
    r = dict(reading)
    kind = _active["type"]
    elapsed = (t - _active["start"]).total_seconds()
    w = _weight(elapsed, (_active["end"] - _active["start"]).total_seconds())

    if kind == "acid_spill":
        r["ph"] = r["ph"] + (7.70 - r["ph"]) * w
    elif kind == "dredging":
        r["turb"] = r["turb"] + 3.5 * w
    elif kind == "spike":
        # Only the first reading after the start. VLE posts every 30-35 s, so a
        # fixed time window could miss the reading entirely.
        if _active.setdefault("spike_time", t) != t:
            return reading
        r["temp"] = r["temp"] + 4.5
    elif kind == "freshwater_pulse":
        r["sal"], r["turb"], r["temp"] = r["sal"] - 4.0 * w, r["turb"] + 1.0 * w, r["temp"] - 0.5 * w
    elif kind == "thermal_discharge":
        r["temp"] = r["temp"] + 2.0 * w
    elif kind == "drift":
        r["sal"] = r["sal"] + 0.004 * elapsed
    elif kind == "stuck":
        r["temp"] = _active["frozen_temp"]
    for k, d in DECIMALS.items():  # round like the real sensor, so values look real
        if r.get(k) is not None:
            r[k] = round(r[k], d)
    r["injected"] = True
    return r


def apply_latest(latest):
    """For /api/latest. A gap keeps showing the last reading from before it started."""
    today = latest["time"][:10]
    _expire(parse_time(latest["time"], today))
    if _active and _active["type"] == "gap" and parse_time(latest["time"], today) >= _active["start"]:
        return _active["last_before"]
    return apply(latest, today)


def apply_history(points, today):
    """For /api/history. A gap removes the readings inside it."""
    if not _active:
        return points
    if _active["type"] == "gap":
        return [p for p in points if not (_active["start"] <= parse_time(p["time"], today) <= _active["end"])]
    return [apply(p, today) for p in points]
