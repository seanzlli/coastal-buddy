"""FastAPI backend for the VLE dashboard.

It sits between our React frontend and the live VLE Aveiro API:
- the browser can't call sp02.aveiro.vle.global directly from our page (other origin),
- field names differ between the VLE endpoints, so we normalise them here once,
- long ranges (1W / ALL) have 100k+ points, so we average them into buckets,
- the anomaly detector pushes its JSON here, and the dashboard reads it back.

Run from the repo root:  .venv/bin/uvicorn backend.main:app --reload --port 8000
"""
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import explain, injection

VLE ="https://sp02.aveiro.vle.global"
FIELDS = ["temp", "sal", "turb", "ph", "bio", "wind", "wdir"]
# A chart can't usefully draw more points than it has pixels, so cap the series.
MAX_POINTS = 1500
# How long an upstream response stays fresh (seconds). Longer ranges change
# relatively less and are slow to fetch (ALL is ~13 MB), so they are cached longer.
CACHE_TTL = {"latest": 4, "1h": 5, "1d": 15, "1w": 60, "all": 120}
# How many detector payloads we remember for the alert list and predicted line.
DETECTOR_HISTORY = 500

@asynccontextmanager
async def lifespan(app):
    # On Render everything runs as one service: with RUN_DETECTOR=1 the rule-based
    # detector runs in a background thread and talks to this same server.
    # Locally start.sh runs it as its own process instead.
    if os.environ.get("RUN_DETECTOR") == "1":
        from detector.live import run

        port = os.environ.get("PORT", "8000")
        threading.Thread(target=run, args=(f"http://127.0.0.1:{port}",), daemon=True).start()
    yield


app = FastAPI(title="VLE dashboard backend", lifespan=lifespan)
client = httpx.AsyncClient(base_url=VLE, timeout=60)
_cache: dict[str, tuple[float, object]] = {}


async def fetch_upstream(path: str, key: str):
    """GET from the VLE API with a small cache; serve stale data if VLE is down."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL[key]:
        return hit[1]
    try:
        r = await client.get(path)
        r.raise_for_status()
    except httpx.HTTPError as e:
        if hit:
            return hit[1]  # a slightly old dashboard beats a blank one
        raise HTTPException(502, f"VLE API unreachable: {e}")
    data = r.json()
    _cache[key] = (time.monotonic(), data)
    return data


async def upstream_latest():
    """The newest real reading, normalised, without any demo injection."""
    raw = await fetch_upstream("/api/latest", "latest")
    # /api/latest calls wind w_spd/w_dir, /api/history calls it wind/wdir: use the latter.
    return {
        "time": raw.get("time"),
        "temp": raw.get("temp"),
        "sal": raw.get("sal"),
        "turb": raw.get("turb"),
        "ph": raw.get("ph"),
        "bio": raw.get("bio"),
        "wind": raw.get("w_spd"),
        "wdir": raw.get("w_dir"),
        "sig": raw.get("sig"),
    }


@app.get("/api/latest")
async def latest():
    return injection.apply_latest(await upstream_latest())


def downsample(points: list[dict]) -> list[dict]:
    """Average consecutive readings into at most MAX_POINTS buckets.

    Wind direction is an angle (359 and 1 are neighbours), so averaging it would
    be wrong; we keep the bucket's first direction instead.
    """
    n = len(points)
    if n <= MAX_POINTS:
        return points
    size = -(-n // MAX_POINTS)  # ceiling division
    out = []
    for i in range(0, n, size):
        bucket = points[i : i + size]
        row = {"time": bucket[0]["time"], "wdir": bucket[0].get("wdir")}
        for f in FIELDS:
            if f == "wdir":
                continue
            vals = [p[f] for p in bucket if p.get(f) is not None]
            row[f] = round(sum(vals) / len(vals), 3) if vals else None
        out.append(row)
    return out


@app.get("/api/history")
async def history(range: str = Query("1h", pattern="^(1h|1d|1w|all)$"), raw: bool = False):
    points = await fetch_upstream(f"/api/history?range={range}", range)
    # 1H history has no date in its times; take today's date from the latest reading.
    today = (await upstream_latest())["time"][:10]
    points = injection.apply_history(points, today)
    if raw:  # the detector needs every reading, not chart-sized averages
        return points
    # Min/max come from the full data, so a short spike still shows in the cards
    # even when downsampling averages it away in the chart.
    minmax = {}
    for f in FIELDS:
        vals = [p[f] for p in points if p.get(f) is not None]
        minmax[f] = {"min": min(vals), "max": max(vals)} if vals else None
    return {"range": range, "count": len(points), "minmax": minmax, "points": downsample(points)}


# ---- Demo injection ------------------------------------------------------------
# Start a fake incident on top of the live feed, so the jury can watch it get caught.

class InjectRequest(BaseModel):
    type: str


@app.get("/api/inject")
async def get_inject():
    types = [{"type": k, "label": v[0], "what": v[1], "seconds": v[2], "detect": v[3], "catch_seconds": v[4]}
             for k, v in sorted(injection.TYPES.items(), key=lambda kv: kv[1][4])]  # fastest first
    return {"active": injection.status(), "types": types}


@app.post("/api/inject")
async def post_inject(req: InjectRequest):
    if req.type not in injection.TYPES:
        raise HTTPException(400, f"unknown type; choose one of {list(injection.TYPES)}")
    return {"active": injection.start(req.type, await upstream_latest())}


@app.delete("/api/inject")
async def delete_inject():
    injection.stop()
    return {"active": None}


# ---- Detector slot -------------------------------------------------------------
# The detector (built by a teammate) POSTs one payload per check. The format is the
# one the team agreed on; "anomalies" is an empty list when nothing is wrong.

class Anomaly(BaseModel):
    measure: str               # temp, sal, turb, ph, bio, wind, wdir
    type: str                  # spike, level_shift, drift, stuck, out_of_range, noise, gap, multi_sensor
    message: str = ""          # human-readable text
    since: Optional[str] = None  # when the anomaly started (drift/stuck start earlier)


class DetectorPayload(BaseModel):
    checked_at: str                          # when the detector ran
    reading_time: Optional[str] = None       # "time" of the reading that was checked
    error: dict[str, Optional[float]] = {}   # measured - predicted, per measure, in its own unit
    anomalies: list[Anomaly] = []


_detector: list[dict] = []


@app.post("/api/detector")
async def push_detector(payload: DetectorPayload):
    data = payload.model_dump()
    _detector.append(data)
    del _detector[:-DETECTOR_HISTORY]
    if data["anomalies"]:
        # New incidents get a plain-language explanation in the background (off without an API key).
        explain.request(data, injection.apply_latest(await upstream_latest()))
    return {"ok": True, "stored": len(_detector)}


@app.get("/api/detector")
async def get_detector():
    return {"latest": _detector[-1] if _detector else None, "recent": _detector, "explanations": explain.results()}


# ---- Built dashboard -------------------------------------------------------------
# In the deployed version FastAPI also serves the built React app, so the whole
# thing is one URL. Mounted last, so every /api route above takes precedence.
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
