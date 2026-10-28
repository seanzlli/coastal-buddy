"""Plain-language explanations of alerts, written by Claude (Haiku).

For every NEW incident the detector reports, we send Claude the detector's
verdict in words (which rule fired, on which sensor, and whether each sensor is
low, normal or high) and get back 2-3 sentences: what happened, the likely
cause, and what to do. No partner data leaves the server: no readings, no
numbers, no timestamps. _summary() refuses any text that contains a digit.

It is optional and can't break anything:
- no ANTHROPIC_API_KEY set: explanations are simply off;
- each incident is explained once and cached, so an ongoing event costs one call;
- at most MAX_PER_HOUR calls, because the public sandbox can create incidents;
- any error, timeout or refusal: the alert keeps its normal rule text.
"""
import asyncio
import os
import re
import time

MODEL = os.environ.get("EXPLAIN_MODEL", "claude-haiku-5-5")
MAX_PER_HOUR = 30

SYSTEM = (
    "You explain water-quality alerts from a coastal monitoring buoy in the port of Aveiro, Portugal, "
    "to a port operator who is not a data scientist. You only get the detector's verdict in words, no "
    "readings. Write at most 50 words in 2 or 3 short sentences of plain English: what happened, the most likely cause (a sensor or data-feed fault, or a real change in "
    "the water) and why, and one concrete thing to do. Use only what you are given, say 'likely' "
    "when unsure, and don't quote numbers. No greeting, no headings, no markdown."
)

# How this buoy behaves, in words only (the numbers stay in the detector).
NORMAL = (
    "How this buoy normally behaves: pH stays in a very narrow band and moves gently with the tide; "
    "salinity and temperature change slowly with the tide and the time of day; turbidity always follows "
    "the wind exactly, so turbidity that does not match the wind means sediment or a discharge; bio-loading "
    "on the sensor grows steadily; a new reading arrives about twice a minute. Events (strong wind, high "
    "turbidity, warm water, cold water, low salinity) mean the data is fine but the water or weather really "
    "changed. Every other alert is a fault: the data looks wrong."
)

NAMES = {"temp": "water temperature", "ph": "pH", "sal": "salinity", "turb": "turbidity",
         "wind": "wind speed", "wdir": "wind direction", "bio": "bio-loading", "feed": "data feed"}

# What each rule means, so the detector's own message (which holds thresholds) never has to be sent.
RULES = {
    "feed_fallback": "the weather part of the feed switched to fixed default values",
    "turbidity_mismatch": "turbidity no longer matches the wind",
    "out_of_range": "the value is outside anything this buoy has ever measured",
    "spike": "the value jumped in a single reading",
    "fast_change": "the value changed within a quarter of an hour much faster than it ever does normally",
    "drift": "the value has been creeping away from normal over the last two hours",
    "stuck": "the value has not changed at all for a long time, while it normally keeps moving",
    "gap": "no new readings are arriving",
    "strong_wind": "the wind has been strong for the last half hour",
    "high_turbidity": "the water has been murky for the last half hour",
    "warm_water": "the water has been warm for the last half hour",
    "cold_water": "the water has been cold for the last half hour",
    "low_salinity": "salinity has been low for the last half hour",
}

# (lowest ever, low event, high event, highest ever) from the history; used here only to pick a word.
LEVELS = {"temp": (14.9, 15.5, 21, 22.1), "ph": (8.03, None, None, 8.07), "sal": (32.8, 33.5, None, 36.7)}


def _level(key, v):
    lo, lo_event, hi_event, hi = LEVELS[key]
    if v < lo:
        return "below its normal range"
    if v > hi:
        return "above its normal range"
    if lo_event is not None and v <= lo_event:
        return "low"
    if hi_event is not None and v >= hi_event:
        return "high"
    return "normal"


def _snapshot(latest):
    """Each sensor as one word or phrase: the only view of the data Claude gets."""
    parts = [f"{NAMES[k]} {_level(k, latest[k])}" for k in LEVELS if latest.get(k) is not None]
    wind, turb = latest.get("wind"), latest.get("turb")
    if wind is not None:
        parts.append("wind strong" if wind >= 20 else "wind calm to moderate")
    if wind is not None and turb is not None:
        diff = turb - round(1.2 + 0.04 * wind, 1)
        parts.append("turbidity higher than the wind explains" if diff >= 0.15
                     else "turbidity lower than the wind explains" if diff <= -0.15
                     else "turbidity matches the wind")
    return ", ".join(parts) or "no current readings"


_client = None
_results: dict[str, dict] = {}  # incident key -> {"status": "pending"|"done"|"failed", "text": ...}
_calls: list[float] = []         # times of recent API calls, for the hourly cap


def enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        # Short timeout and one retry: an explanation that arrives late is worth little.
        _client = AsyncAnthropic(timeout=20.0, max_retries=1)
    return _client


def incident_key(anomaly, payload):
    """Same key the dashboard uses to merge repeated reports of one incident."""
    at = anomaly.get("since") or payload.get("reading_time") or payload.get("checked_at")
    return f"{anomaly['type']}|{anomaly['measure']}|{at}"


def _summary(anomaly, payload, latest):
    others = [f"{a['type'].replace('_', ' ')} on {NAMES.get(a['measure'], a['measure'])}"
              for a in payload.get("anomalies", []) if a is not anomaly]
    text = (
        f"Alert: {anomaly['type'].replace('_', ' ')} on {NAMES.get(anomaly['measure'], anomaly['measure'])}: "
        f"{RULES.get(anomaly['type'], 'unusual data')}.\n"
        f"Sensors now: {_snapshot(latest)}.\n"
        f"Other active alerts: {', '.join(others) if others else 'none'}.\n"
        f"{NORMAL}"
    )
    if re.search(r"\d", text):  # a number would be partner data: never send it
        raise ValueError("summary contains a digit")
    return text


async def _explain(key, anomaly, payload, latest):
    try:
        import anthropic

        resp = await _get_client().messages.create(
            model=MODEL,
            max_tokens=4000,  # room for Haiku's thinking plus the short answer, so it never gets cut off
            system=SYSTEM,
            output_config={"effort": "low"},  # short answers; low effort keeps it fast
            messages=[{"role": "user", "content": _summary(anomaly, payload, latest)}],
        )
        text = " ".join(b.text for b in resp.content if b.type == "text").strip()
        if resp.stop_reason == "max_tokens" and "." in text:
            text = text[: text.rfind(".") + 1]  # never show a sentence cut off mid-word
        if resp.stop_reason == "refusal" or not text:
            _results[key] = {"status": "failed"}
        else:
            _results[key] = {"status": "done", "text": text}
    except anthropic.RateLimitError:
        _results[key] = {"status": "failed"}
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        print(f"explain: {type(e).__name__}: {e}")
        _results[key] = {"status": "failed"}
    except Exception as e:  # a background task must never take the server down
        print(f"explain: unexpected {type(e).__name__}: {e}")
        _results[key] = {"status": "failed"}


def request(payload, latest):
    """Start explanations for the payload's incidents that haven't been explained yet."""
    if not enabled():
        return
    now = time.monotonic()
    _calls[:] = [t for t in _calls if now - t < 3600]
    explained = set()
    for anomaly in payload.get("anomalies", []):
        # One explanation per sensor: a pH spike and pH out of range are the same story.
        if anomaly["measure"] in explained:
            continue
        explained.add(anomaly["measure"])
        key = incident_key(anomaly, payload)
        if key in _results:
            continue
        if len(_calls) >= MAX_PER_HOUR:
            _results[key] = {"status": "skipped"}
            continue
        _calls.append(now)
        _results[key] = {"status": "pending"}
        asyncio.get_running_loop().create_task(_explain(key, anomaly, payload, latest))


def results():
    """Explanations for the dashboard: key -> {"status", "text"?}. Empty when off."""
    return _results if enabled() else {}
