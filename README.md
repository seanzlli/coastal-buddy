# Coastal Buddy: Aveiro coastal water monitor

Live anomaly detection for the VLE Global sensor buoy SP-02 in the port of Aveiro (Portugal).
Built in one day at the **AI for Water hackathon** (UvA / AISO), **VLE Global challenge**.

**Live demo: https://aveiro-water-monitor.onrender.com/** (free hosting: the first load after a quiet period can take up to a minute)

It watches the live feed and sorts what it finds into two kinds:
- **Faults** (red): the data is wrong. A broken or stuck sensor, a failing weather feed, or a water incident the normal pattern can't explain (chemical spill, sediment discharge, warm-water discharge).
- **Events** (orange): the data is fine, but the port should know. Strong wind, high turbidity, warm or cold water, low salinity.

Each alert says what happened, since when, and which rule caught it. That makes it easy to explain to an operator.

## Team
- Sean Zhu Liong Li
- Lucas De Miranda Sloot
- Ronald Koning
- Michiel Kamphuis

## How it works

```
VLE live API ──> backend (FastAPI) ──> dashboard (React)
                  │       ▲
                  ▼       │ JSON per check
              detector/live.py (rules)  ·  predictor/ (LSTM, Telemanom)
```

- **`backend/`** passes the VLE API through to the dashboard: it renames fields, averages long ranges down for the charts, and caches. It also stores the detectors' results (`POST /api/detector`).
- **`detector/`** is the rule-based detector. Every threshold comes from the 117k readings in the history, set with a margin above the largest normal change.
- **`predictor/`** is an LSTM forecaster (Telemanom). It flags readings whose prediction error is unusually large.
- **`frontend/`** is the dashboard:
  - a status bar
  - a large chart for the selected sensor, showing the prediction and the anomalies
  - a sensor list with last-hour trends
  - an anomaly feed, a wind compass and a bio-fouling gauge (with maintenance levels and when cleaning is due)
  - a **demo sandbox**: inject a fake incident (acid spill, dredging, sewage overflow, stuck sensor…) into the live feed and watch the detector catch it. The backend applies it to the data itself, so the detector really has to find it.
  - **AI explanations** (optional): with `ANTHROPIC_API_KEY` set, Claude Haiku 5.5 writes 2–3 plain-language sentences per new incident (what happened, likely cause, what to do). Only the detector's verdict in words is sent (which rule fired, and whether each sensor is low, normal or high): no readings, numbers or timestamps, and the code refuses any summary containing a digit. Each incident is explained once, at most 30 per hour, and without a key the alerts keep their rule text.

### What we learned from the data
The feed is a clean simulation, and that is why simple rules work so well:
- pH follows a 12.4 h tide and stays between 8.03 and 8.07.
- Turbidity is **exactly** `1.2 + 0.04 × wind`, rounded, in 100% of normal readings.
- Bio-loading grows a steady 1.2 kg/m² per day.
- The only real fault is 937 rows where the weather feed falls back to defaults (wind 10, direction 180, turbidity 1.6).

### The rules (`detector/rules.py`)
| Rule | Catches | Threshold (largest normal value seen) |
|---|---|---|
| Feed fallback | Weather feed failure | wind 10 + direction 180 + turbidity 1.6 |
| Turbidity mismatch | Sediment or discharge without a storm | ≥ 0.15 NTU off the formula (normal: 0) |
| Out of range | Impossible values, e.g. a pH drop | pH outside 8.0–8.1, salinity 30–38, temp 10–28 °C |
| Spike | One-reading glitch | temp > 1.0 °C, pH > 0.03, salinity > 0.5 PSU (normal max 0.78 / 0.01 / 0.2) |
| Fast change | Discharge, fresh-water pulse | temp > 0.8 °C or salinity > 0.5 PSU in 15 min (normal max 0.31 / 0.20) |
| Drift | Calibration drift | salinity > 0.9 PSU or pH > 0.05 in 2 h (normal max 0.5 / 0.02) |
| Stuck | Frozen sensor | temperature unchanged for 20 readings (normal max 11) |
| Gap | Feed stops | no reading for 5 min (normal max 3 min) |
| Events | Strong wind, turbidity, warm/cold water, low salinity | 30-min median: wind ≥ 20 km/h, turbidity ≥ 2.0, temp ≥ 21 or ≤ 15.5, salinity ≤ 33.5 |

## How we checked it
The real history contains only one fault type. So we injected **32 realistic incidents** into the last 10 days (`detector/inject.py`), 4 of each of 8 types:
- **easy:** acid spill, spike, gap
- **medium:** dredging, fresh-water pulse, stuck sensor
- **hard:** warm-water discharge, drift

Injected values are rounded like the real sensors, so they can't be spotted by their decimals.

| Test | Result |
|---|---|
| Real history: feed faults caught | **933 / 933** |
| Real history: real 10 m/s wind wrongly flagged | **0 / 772** |
| Real history: other alarms in 41 days | **0** |
| Injected incidents caught | **32 / 32** |
| False alarms in the 10-day test period | **0** |
| Median time to alarm | < 3 min for most types; stuck 10 min; drift ~95 min |

Reproduce these numbers with:

```bash
.venv/bin/python -m detector.evaluate
```

### Rules vs. a learned model (LSTM)
We also trained an LSTM forecaster in the style of NASA's Telemanom (`predictor/Telemanom/`). It was scored on its own injected benchmark: 80 events per type and size, with sizes in standard deviations of each channel.

| Detector | Spikes (1σ / 3σ / 6σ) | Drift (4 h) | Stuck (4 h) | Overall | False alarms |
|---|---|---|---|---|---|
| LSTM (Telemanom) | 65% / 78% / 100% | 0% | 0% | 40% | 9 |
| Persistence ("next = last value") | 57% / 94% / 100% | 1% | 0% | 42% | 26 |

The LSTM catches sudden spikes and raises fewer false alarms than the naive baseline. But it **follows slow drift and frozen sensors**: it predicts each next value from the recent ones, so a slow change never looks surprising.

Our explicit rules (rate of change over 15 min / 2 h, run length) catch these by design. **That's why the live system uses the rules, and the LSTM stays a research track.**

The two detectors were scored on different injected benchmarks, so compare them per anomaly type rather than by the overall percentage.

The test set is built from VLE Global's history, so it isn't included here (see [`data/README.md`](data/README.md)). With the data in place, `python -m detector.inject` rebuilds it and `python -m detector.evaluate` scores the rules.

## How to run
You need Python 3.11+ and Node 18+. From the repo root:

```bash
./start.sh
```

The script installs everything on its first run, then starts the backend (port 8000), the live detector and the dashboard. Open **http://localhost:5173**. Ctrl+C stops all three.

To start the parts by hand instead, use three terminals:

```bash
.venv/bin/uvicorn backend.main:app --port 8000
.venv/bin/python -m detector.live
cd frontend && npm run dev
```

### Deploying (Render)
The repo includes a `Dockerfile` and a `render.yaml`. They build **one** web service: FastAPI serves the API and the built dashboard, and runs the detector in a background thread (`RUN_DETECTOR=1`).

To deploy, go to Render → **New → Blueprint** and pick this repo.

On the free plan the service sleeps after 15 min without visitors. Open it a few minutes before a demo; the detector refills its 3-hour buffer as it starts.

### Plugging in another detector
A detector sends one JSON per check to `POST /api/detector`. `anomalies` is an empty list when nothing is wrong:

```json
{
  "checked_at": "2026-10-28 11:02:34",
  "reading_time": "2026-10-28 11:02:30",
  "error": { "temp": 4.62, "turb": 0.0 },
  "anomalies": [
    { "measure": "temp", "type": "spike", "message": "Temperature sensor may be broken", "since": "2026-10-28 11:02:30" }
  ]
}
```

- `error` is measured − predicted, in the measure's own unit. The dashboard draws the prediction line from it.
- `checked_at` is when the detector ran; `reading_time` is the time of the reading it checked.

## Limitations
- **The data is simulated.** Real sensors are noisier, so the thresholds would need re-tuning on real data.
- **Our labels are our own.** The injected incidents are our guess at realistic failures, not official ground truth.
- **Drift is the slowest to detect** (~95 min). That's where a learned model can add value.
- **Our own cut-offs.** Wind is in km/h (confirmed by the organizers, although the CSV column is named `_ms`). The bio-loading cut-offs and event thresholds are our own choices.
- **Short memory after a restart.** The live detector keeps 3 h of history, so for an event that started earlier it shows the detector's start time as "since".

## Data
- Live data comes from the VLE Global simulated feed, `https://sp02.aveiro.vle.global` (no key needed).
- VLE Global's historical record is their data and is not included; see [`data/README.md`](data/README.md).

## Prepared before the hackathon
- An empty repository skeleton (folders, requirements, git setup), made on 27 Oct.
- Everything else was built on the day.

## Team
Built at the AI for Water hackathon (UvA / AISO, 28 October 2026), where it won third place, by Sean Zhu Liong Li, Lucas De Miranda Sloot, Ronald Koning and Michiel Kamphuis.

## License
[PolyForm Noncommercial 1.0.0](LICENSE.md): you may use, change and share this code for any noncommercial purpose, such as research, education, personal projects, and nonprofit or government organisations. Commercial use, including selling it, needs our permission.
