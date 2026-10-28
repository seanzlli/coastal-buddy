"""Rule-based anomaly detector for the VLE Aveiro feed.

Every threshold below comes from the real history (117k readings), with a safety
margin above the largest change ever seen in normal data, so the rules stay
quiet on normal days. All rules run on a DataFrame with the CSV column names and
a DatetimeIndex; detect() works the same on the full history and on the live
2-hour buffer.

Two kinds of output:
- faults: the data looks wrong (sensor glitch, broken feed, or a water incident
  the simulator would never produce on its own). Shown in red.
- events: the data is fine but the port should know (strong wind, low salinity...).
  Thresholds from the team's data analysis. Shown in orange.
"""
import numpy as np
import pandas as pd

COLS = ["Temp_C", "pH", "Salinity_PSU", "Turbidity_NTU", "Wind_Speed_ms", "Wind_Dir_Deg", "Bio_Load_kgm2"]
# CSV column -> key used by the API, the dashboard and the detector JSON
KEY = {"Temp_C": "temp", "pH": "ph", "Salinity_PSU": "sal", "Turbidity_NTU": "turb",
       "Wind_Speed_ms": "wind", "Wind_Dir_Deg": "wdir", "Bio_Load_kgm2": "bio"}

# Hard limits: well outside everything measured so far (pH has only ever been 8.03-8.07).
RANGE = {"Temp_C": (10, 28), "pH": (8.0, 8.1), "Salinity_PSU": (30, 38), "Turbidity_NTU": (0, 5)}
# Largest normal change between two readings is 0.78 (temp), 0.01 (pH), 0.2 (salinity).
JUMP = {"Temp_C": 1.0, "pH": 0.03, "Salinity_PSU": 0.5}
# Largest normal change in 15 min: temp 0.31, salinity 0.20. In 2 h: temp 1.2, salinity 0.5, pH 0.02.
FAST_15MIN = {"Temp_C": 0.8, "Salinity_PSU": 0.5}
DRIFT_2H = {"Salinity_PSU": 0.9, "pH": 0.05}
STUCK_READINGS = {"Temp_C": 20, "Bio_Load_kgm2": 90}  # normal max flat run: temp 11, bio 24
GAP_SECONDS = 300                                     # normal max gap between readings: 182 s
TURB_TOLERANCE = 0.15                                 # turbidity = round(1.2 + 0.04 * wind, 1) in 100% of normal rows
# Events: 30-minute rolling median beyond these values (team's thresholds, ~most extreme 1%).
EVENTS = {
    "strong_wind": ("Wind_Speed_ms", ">=", 20),  # km/h (the CSV column name says m/s, the VLE UI and organizers say km/h)
    "high_turbidity": ("Turbidity_NTU", ">=", 2.0),
    "warm_water": ("Temp_C", ">=", 21),
    "cold_water": ("Temp_C", "<=", 15.5),
    "low_salinity": ("Salinity_PSU", "<=", 33.5),
}
EVENT_TYPES = set(EVENTS)


def _change(x, window):
    """Change of the 5-min median versus `window` earlier. Medians make a single
    spike invisible here (spikes have their own rule), so one glitch can't raise
    a 15-minute alarm afterwards."""
    m = x.rolling("5min").median()
    past = m.shift(freq=window).reindex(m.index, method="nearest", tolerance=pd.Timedelta("2min"))
    return m - past


def _run_length(x):
    """For each reading: how many readings in a row the value has been identical."""
    run_id = (x != x.shift()).cumsum()
    return x.groupby(run_id).cumcount() + 1


def detect(df):
    """Return a list of (type, csv_column, boolean mask, message) for every rule."""
    out = []
    wind, turb = df["Wind_Speed_ms"], df["Turbidity_NTU"]

    fallback = (wind == 10) & (df["Wind_Dir_Deg"] == 180) & (turb == 1.6)
    out.append(("feed_fallback", "Wind_Speed_ms", fallback,
                "Weather feed fell back to default values (wind 10, direction 180, turbidity 1.6)"))

    expected_turb = (1.2 + 0.04 * wind).round(1)
    mismatch = ((turb - expected_turb).abs() >= TURB_TOLERANCE) & ~fallback
    out.append(("turbidity_mismatch", "Turbidity_NTU", mismatch,
                "Turbidity does not match the wind (sediment or discharge without a storm)"))

    for col, (lo, hi) in RANGE.items():
        out.append(("out_of_range", col, (df[col] < lo) | (df[col] > hi), f"{KEY[col]} outside the plausible range {lo}-{hi}"))

    for col, thr in JUMP.items():
        x = df[col]
        # differs from the previous AND the one before, so the step back after a spike isn't a 2nd alarm
        jump = ((x - x.shift(1)).abs() > thr) & ((x - x.shift(2)).abs() > thr)
        out.append(("spike", col, jump, f"{KEY[col]} jumped more than {thr} in one reading"))

    for col, thr in FAST_15MIN.items():
        out.append(("fast_change", col, _change(df[col], "15min").abs() > thr, f"{KEY[col]} changed more than {thr} within 15 min"))

    for col, thr in DRIFT_2H.items():
        out.append(("drift", col, _change(df[col], "2h").abs() > thr, f"{KEY[col]} drifted more than {thr} within 2 h"))

    for col, n in STUCK_READINGS.items():
        out.append(("stuck", col, _run_length(df[col]) >= n, f"{KEY[col]} has not changed for {n} readings"))

    dt = df.index.to_series().diff().dt.total_seconds()
    out.append(("gap", "feed", dt > GAP_SECONDS, f"No readings for more than {GAP_SECONDS // 60} min"))

    for name, (col, op, thr) in EVENTS.items():
        med = df[col].rolling("30min").median()
        mask = med >= thr if op == ">=" else med <= thr
        out.append((name, col, mask, f"{name.replace('_', ' ')}: 30-min median of {KEY[col]} {op} {thr}"))
    return out


def turbidity_error(df):
    """measured - predicted turbidity: the one value with an exact formula."""
    return df["Turbidity_NTU"] - (1.2 + 0.04 * df["Wind_Speed_ms"]).round(1)


def since(mask, index):
    """Timestamp where the current (last) run of True values started."""
    if not mask.iloc[-1]:
        return None
    starts = mask & ~mask.shift(fill_value=False)
    return index[starts.to_numpy()][-1]
