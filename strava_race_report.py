"""
Strava Race Report – Tabernas Desert Ultra 2026
Analysiert Strava-Daten und erstellt einen personalisierten Trainingsplan als HTML-Report.
"""
import json
import math
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_API_BASE = "https://www.strava.com/api/v3"
STAGE_COLORS = ["#3498db", "#e67e22", "#e74c3c", "#8e44ad"]
RACE_DATE = datetime(2026, 5, 18)
TODAY = datetime.now()
WEEKS_TO_RACE = max(1, (RACE_DATE - TODAY).days // 7)

# ─────────────────────────────────────────────────────────────
# 8-WOCHEN TAG-FÜR-TAG TRAININGSPLAN  (Basis: 40–70 km/Woche)
# Typen: rest | easy | tempo | hills | long | b2b | active
# ─────────────────────────────────────────────────────────────
WEEKLY_PLAN = [
    {
        "num": 1, "focus": "Basisaufbau", "color": "#3498db",
        "total_km": 46, "total_elev": 750,
        "note": "Ruecksack einführen, Ausrüstung testen, Pace bewusst drosseln",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Mobilität 20 min · Dehnen"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 8,  "elev": 80,  "note": "Rucksack 3 kg · Kadenz 180"},
            {"d": "Mi", "type": "hills",  "name": "Hügelläufe",       "km": 10, "elev": 220, "note": "4 × 2 min bergauf · locker zurück"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Yoga oder Foam-Roll"},
            {"d": "Fr", "type": "easy",   "name": "Easy Run",         "km": 8,  "elev": 70,  "note": "Sehr locker · Beine frei"},
            {"d": "Sa", "type": "long",   "name": "Langer Lauf",      "km": 18, "elev": 350, "note": "Rucksack 4 kg · 2 L Wasser · Wüstenpace"},
            {"d": "So", "type": "active", "name": "Aktiv-Erholung",   "km": 2,  "elev": 30,  "note": "Spaziergang · Dehnen"},
        ],
    },
    {
        "num": 2, "focus": "Ausdauer", "color": "#2980b9",
        "total_km": 51, "total_elev": 870,
        "note": "Ernährungsstrategie testen, Hitzeanpassung starten (Sauna/warme Kleidung)",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Schlaf priorisieren"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 9,  "elev": 100, "note": "Rucksack 4 kg · Gels testen"},
            {"d": "Mi", "type": "tempo",  "name": "Tempolauf",        "km": 12, "elev": 120, "note": "2 × 15 min bei 75 % HFmax"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Kontrastdusche / Eisbad"},
            {"d": "Fr", "type": "easy",   "name": "Easy Run",         "km": 8,  "elev": 80,  "note": "Sehr locker · Beine schütteln"},
            {"d": "Sa", "type": "long",   "name": "Langer Lauf",      "km": 22, "elev": 500, "note": "Rucksack 5 kg · Hügelstrecke · volle Ernährung"},
            {"d": "So", "type": "active", "name": "Aktiv-Erholung",   "km": 0,  "elev": 0,   "note": "Schwimmen oder Spazieren · kein Laufen"},
        ],
    },
    {
        "num": 3, "focus": "Intensität", "color": "#e67e22",
        "total_km": 58, "total_elev": 1090,
        "note": "Erster Back-to-Back am Wochenende – Sonntag bewusst müde laufen!",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Schlaf · Ernährung"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 10, "elev": 100, "note": "Locker · lockerer Schritt"},
            {"d": "Mi", "type": "hills",  "name": "Bergintervals",    "km": 12, "elev": 350, "note": "6 × 200 hm bergauf · Marschtechnik bergab"},
            {"d": "Do", "type": "easy",   "name": "Recovery Run",     "km": 8,  "elev": 80,  "note": "Sehr locker · keine Intensität"},
            {"d": "Fr", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Füße pflegen · schlafen"},
            {"d": "Sa", "type": "long",   "name": "Langer Lauf",      "km": 22, "elev": 480, "note": "Rucksack 6 kg · Mittagshitze testen"},
            {"d": "So", "type": "b2b",    "name": "Back-to-Back #1",  "km": 6,  "elev": 80,  "note": "Erster B2B! Sehr locker · müde Beine akzeptieren"},
        ],
    },
    {
        "num": 4, "focus": "Entlastung", "color": "#27ae60",
        "total_km": 37, "total_elev": 530,
        "note": "Erholungswoche – Qualität vor Quantität, Körper adaptiert jetzt",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Massage oder Physio"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 7,  "elev": 70,  "note": "Sehr locker · kein Druck"},
            {"d": "Mi", "type": "easy",   "name": "Easy Run",         "km": 8,  "elev": 120, "note": "Lockere Hügel · Technik"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Ernährung · Schlaf 8+ h"},
            {"d": "Fr", "type": "easy",   "name": "Easy Run",         "km": 7,  "elev": 60,  "note": "Locker · Ausrüstung prüfen"},
            {"d": "Sa", "type": "long",   "name": "Medium Long Run",  "km": 15, "elev": 280, "note": "Entspannt · Race-Pace testen"},
            {"d": "So", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Passiv erholen · früh schlafen"},
        ],
    },
    {
        "num": 5, "focus": "Spezifisch", "color": "#8e44ad",
        "total_km": 62, "total_elev": 1190,
        "note": "Wochenende = Race-Simulation: Rucksack komplett bepackt, voller Gear-Test",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Vorbereitung Wochenend-Block"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 9,  "elev": 90,  "note": "Rucksack 6 kg · locker"},
            {"d": "Mi", "type": "hills",  "name": "Wüsten-Spezial",   "km": 11, "elev": 300, "note": "Langer Bergabschnitt + Aufstieg · Sandtechnik"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Beine schonen vor B2B-WE"},
            {"d": "Fr", "type": "easy",   "name": "Aktivierung",      "km": 7,  "elev": 80,  "note": "Locker · Darmstadium vorbereiten"},
            {"d": "Sa", "type": "long",   "name": "Race-Simulation 1","km": 19, "elev": 450, "note": "Rucksack 7–8 kg · Mittagshitze · volle Race-Ernährung"},
            {"d": "So", "type": "b2b",    "name": "Back-to-Back #2",  "km": 16, "elev": 270, "note": "Müde Beine! Pace egal · durchbeißen"},
        ],
    },
    {
        "num": 6, "focus": "Peak", "color": "#e74c3c",
        "total_km": 69, "total_elev": 1400,
        "note": "Härteste Woche – mentale Stärke trainieren, Schmerz als Info werten",
        "days": [
            {"d": "Mo", "type": "active", "name": "Aktiv-Erholung",   "km": 0,  "elev": 0,   "note": "Spazieren · Beine hochlegen"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 10, "elev": 120, "note": "Rucksack 6 kg · locker"},
            {"d": "Mi", "type": "hills",  "name": "Bergintervals",    "km": 12, "elev": 350, "note": "Schwere Beine tolerieren · Technik"},
            {"d": "Do", "type": "easy",   "name": "Recovery Run",     "km": 7,  "elev": 80,  "note": "Sehr locker · mentale Vorbereitung"},
            {"d": "Fr", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Schlafen · Ernährung optimieren"},
            {"d": "Sa", "type": "long",   "name": "Race-Simulation 2","km": 22, "elev": 500, "note": "Tag 1 Etappe! Komplett ausgerüstet · Start 06:00 Uhr"},
            {"d": "So", "type": "b2b",    "name": "Back-to-Back #3",  "km": 18, "elev": 350, "note": "Tag 2 Etappe! Kompletter Race-Mode · kein Abkürzen"},
        ],
    },
    {
        "num": 7, "focus": "Tapering", "color": "#16a085",
        "total_km": 40, "total_elev": 650,
        "note": "Umfang runter, Intensität kurz halten – Ausrüstung finalisieren",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Erholen · Physio falls nötig"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 8,  "elev": 80,  "note": "Locker · Körpergefühl"},
            {"d": "Mi", "type": "tempo",  "name": "Kurztempo",        "km": 10, "elev": 120, "note": "2 × 10 min Tempo · Beine erinnern"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Packliste abhaken"},
            {"d": "Fr", "type": "easy",   "name": "Easy Run",         "km": 7,  "elev": 70,  "note": "Rucksack 4 kg · letzter Gear-Check"},
            {"d": "Sa", "type": "long",   "name": "Medium Long Run",  "km": 15, "elev": 380, "note": "Wüstenpace · Ausrüstung vollständig testen"},
            {"d": "So", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Vollständige Ruhe · früh schlafen"},
        ],
    },
    {
        "num": 8, "focus": "Finaler Taper", "color": "#95a5a6",
        "total_km": 22, "total_elev": 260,
        "note": "Beine frisch halten – niemals neue Schuhe oder Ausrüstung ausprobieren!",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Ausrüstung packen · Rucksack wiegen"},
            {"d": "Di", "type": "easy",   "name": "Easy Run",         "km": 6,  "elev": 60,  "note": "Sehr locker · 30 min max"},
            {"d": "Mi", "type": "easy",   "name": "Easy Run",         "km": 5,  "elev": 50,  "note": "Locker · Beine freihalten"},
            {"d": "Do", "type": "rest",   "name": "Ruhetag",          "km": 0,  "elev": 0,   "note": "Mentale Vorbereitung · Visualisieren"},
            {"d": "Fr", "type": "easy",   "name": "Aktivierung",      "km": 5,  "elev": 70,  "note": "20 min locker · kein Stress"},
            {"d": "Sa", "type": "easy",   "name": "Letzter Lauf",     "km": 6,  "elev": 80,  "note": "30 min Aktivierung · alles gut fühlen"},
            {"d": "So", "type": "rest",   "name": "Reise-Vorbereitung","km": 0, "elev": 0,   "note": "Früh schlafen · An-/Abreise planen"},
        ],
    },
    {
        "num": 9, "focus": "Race Week", "color": "#c0392b",
        "total_km": 130, "total_elev": 1600,
        "note": "18.–22. Mai 2026 · Start 06:00 Uhr · Solo Unsupported · Du bist bereit!",
        "days": [
            {"d": "Mo", "type": "rest",   "name": "Anreisetag",        "km": 0,  "elev": 0,   "note": "Anreise Tabernas · Akklimatisierung"},
            {"d": "Di", "type": "easy",   "name": "Kurze Aktivierung", "km": 4,  "elev": 40,  "note": "20 min locker · letzte Ausrüstungs-Checks"},
            {"d": "Mi", "type": "rest",   "name": "Ruhetag",           "km": 0,  "elev": 0,   "note": "Ausruhen · gut essen · früh schlafen"},
            {"d": "Do", "type": "easy",   "name": "Aktivierung",       "km": 3,  "elev": 30,  "note": "15 min locker · kein Stress"},
            {"d": "Fr", "type": "rest",   "name": "Race-Briefing",     "km": 0,  "elev": 0,   "note": "Letzte Vorbereitung · Schlafen!"},
            {"d": "Sa", "type": "race",   "name": "RENNEN TAG 1",      "km": 33, "elev": 400, "note": "Start 06:00 · Pace halten · Wasser!"},
            {"d": "So", "type": "race",   "name": "RENNEN TAG 2",      "km": 33, "elev": 400, "note": "Früh starten · Siesta 12–15 Uhr"},
        ],
    },
]


def get_headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def fetch_athlete():
    r = requests.get(f"{STRAVA_API_BASE}/athlete", headers=get_headers())
    r.raise_for_status()
    return r.json()


def fetch_activities(per_page=200, max_pages=5):
    activities = []
    for page in range(1, max_pages + 1):
        r = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=get_headers(),
            params={"per_page": per_page, "page": page},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        activities.extend(batch)
        if len(batch) < per_page:
            break
    return activities


def km(m): return m / 1000


def hms(s):
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {sec:02d}s"


def analyze_strava(activities):
    run_types = {"Run", "TrailRun", "VirtualRun", "Hike"}
    runs = [a for a in activities if (a.get("sport_type") or a.get("type", "")) in run_types]

    weekly = defaultdict(lambda: {"dist": 0, "elev": 0, "count": 0, "time": 0, "long": 0})
    for a in runs:
        date = datetime.fromisoformat(a["start_date_local"].replace("Z", "+00:00")).replace(tzinfo=None)
        weeks_ago = (TODAY - date).days // 7
        if weeks_ago < 8:
            w = weekly[weeks_ago]
            d = a.get("distance", 0)
            w["dist"] += d
            w["elev"] += a.get("total_elevation_gain", 0)
            w["count"] += 1
            w["time"] += a.get("moving_time", 0)
            w["long"] = max(w["long"], d)

    recent_weeks = [weekly[i] for i in range(8) if weekly[i]["count"] > 0]
    avg_weekly_km = sum(w["dist"] for w in recent_weeks) / max(1, len(recent_weeks)) / 1000
    avg_weekly_elev = sum(w["elev"] for w in recent_weeks) / max(1, len(recent_weeks))
    max_long_run = max((w["long"] for w in recent_weeks), default=0) / 1000

    total_runs = len(runs)
    total_dist = sum(a.get("distance", 0) for a in runs)

    recent = sorted(activities, key=lambda a: a["start_date_local"], reverse=True)[:10] if activities else []

    hr_runs = [a for a in runs if a.get("average_heartrate")]
    avg_hr = sum(a["average_heartrate"] for a in hr_runs) / len(hr_runs) if hr_runs else None

    return {
        "total_runs": total_runs,
        "total_dist": total_dist / 1000,
        "avg_weekly_km": avg_weekly_km,
        "avg_weekly_elev": avg_weekly_elev,
        "max_long_run": max_long_run,
        "weekly": weekly,
        "recent": recent,
        "avg_hr": avg_hr,
    }


def fitness_level(avg_km):
    if avg_km < 20: return ("Einsteiger", "#e67e22")
    if avg_km < 40: return ("Fortgeschrittener", "#f1c40f")
    if avg_km < 70: return ("Erfahren", "#2ecc71")
    return ("Ultra-Erfahren", "#27ae60")


# ─────────────────────────────────────────────────────────────
# GPX PARSING & ROUTE ANALYSIS
# ─────────────────────────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_gpx(path):
    tree = ET.parse(path)
    root = tree.getroot()
    m = re.match(r'\{.*?\}', root.tag)
    ns = m.group(0) if m else ''

    raw = []
    for trkpt in root.iter(f'{ns}trkpt'):
        lat = float(trkpt.get('lat'))
        lon = float(trkpt.get('lon'))
        ele_el = trkpt.find(f'{ns}ele')
        ele = float(ele_el.text) if ele_el is not None else 0.0
        raw.append((lat, lon, ele))

    if len(raw) < 2:
        return None

    # Cumulative distance
    cum_dist = [0.0]
    total_elev_gain = 0.0
    for i in range(1, len(raw)):
        d = haversine(raw[i - 1][0], raw[i - 1][1], raw[i][0], raw[i][1])
        cum_dist.append(cum_dist[-1] + d)
        if raw[i][2] > raw[i - 1][2]:
            total_elev_gain += raw[i][2] - raw[i - 1][2]

    total_m = cum_dist[-1]
    total_km = total_m / 1000

    # Split into 4 equal stages by distance
    boundaries = [total_m * i / 4 for i in range(5)]
    stage_indices = [[] for _ in range(4)]
    current_stage = 0
    for i, d in enumerate(cum_dist):
        while current_stage < 3 and d >= boundaries[current_stage + 1]:
            current_stage += 1
        stage_indices[current_stage].append(i)

    stages = []
    stage_map_pts = []
    stage_chart_pts = []

    for si, idxs in enumerate(stage_indices):
        if not idxs:
            stages.append({"km": 0, "elev": 0})
            stage_map_pts.append([])
            stage_chart_pts.append([])
            continue

        # Map points: downsample to max 800 per stage
        step_m = max(1, len(idxs) // 800)
        pts_map = [[raw[i][0], raw[i][1]] for i in idxs[::step_m]]

        # Chart points: downsample to max 150 per stage
        step_c = max(1, len(idxs) // 150)
        pts_chart = [[round(cum_dist[i] / 1000, 2), round(raw[i][2], 1)] for i in idxs[::step_c]]

        # Stage elevation gain
        elev_gain = 0.0
        for k in range(1, len(idxs)):
            de = raw[idxs[k]][2] - raw[idxs[k - 1]][2]
            if de > 0:
                elev_gain += de

        stage_km = (cum_dist[idxs[-1]] - cum_dist[idxs[0]]) / 1000
        stages.append({"km": stage_km, "elev": elev_gain})
        stage_map_pts.append(pts_map)
        stage_chart_pts.append(pts_chart)

    lats = [p[0] for p in raw]
    lons = [p[1] for p in raw]
    bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]

    return {
        "total_km": total_km,
        "total_elev": total_elev_gain,
        "stages": stages,
        "stage_map_pts": stage_map_pts,
        "stage_chart_pts": stage_chart_pts,
        "bounds": bounds,
    }


def update_race_week_from_gpx(gpx_data):
    """Update race week (WEEKLY_PLAN[8]) with actual GPX stage data."""
    race_week = WEEKLY_PLAN[8]
    race_week["total_km"] = round(gpx_data["total_km"])
    race_week["total_elev"] = round(gpx_data["total_elev"])
    race_week["note"] = (
        f"GPX-Route: {gpx_data['total_km']:.1f} km · "
        f"▲ {gpx_data['total_elev']:.0f} m · "
        "18.–22. Mai 2026 · Solo Unsupported"
    )
    stages = gpx_data["stages"]
    race_days = [d for d in race_week["days"] if d["type"] == "race"]
    for i, day in enumerate(race_days):
        if i < len(stages):
            s = stages[i]
            day["km"] = round(s["km"], 1)
            day["elev"] = round(s["elev"])
            day["note"] = f"Etappe {i + 1}: {s['km']:.1f} km · ▲ {s['elev']:.0f} m · Start 06:00"


def render_gpx_section(gpx_data):
    """Render interactive map + elevation chart + stage stats as HTML."""
    stage_colors_js = json.dumps(STAGE_COLORS)
    stage_map_js = json.dumps(gpx_data["stage_map_pts"])
    stage_chart_js = json.dumps(gpx_data["stage_chart_pts"])
    bounds_js = json.dumps(gpx_data["bounds"])
    stage_labels_js = json.dumps([f"Etappe {i + 1}" for i in range(4)])

    total_km = gpx_data["total_km"]
    total_elev = gpx_data["total_elev"]
    stages = gpx_data["stages"]

    stage_stats_html = ""
    for i, s in enumerate(stages):
        color = STAGE_COLORS[i]
        stage_stats_html += f"""
        <div class="stage-stat-card" style="border-top:3px solid {color}">
          <div class="stage-num" style="color:{color}">Etappe {i + 1}</div>
          <div class="stage-km">{s['km']:.1f} km</div>
          <div class="stage-elev">▲ {s['elev']:.0f} m</div>
        </div>"""

    return f"""
  <!-- GPX ROUTE -->
  <div class="section">
    <div class="section-title">🗺️ Routenanalyse – Tabernas Desert Ultra</div>

    <div class="route-summary">
      <div class="route-stat"><span class="route-val">{total_km:.1f} km</span><span class="route-lbl">Gesamtdistanz</span></div>
      <div class="route-stat"><span class="route-val">▲ {total_elev:.0f} m</span><span class="route-lbl">Gesamtanstieg</span></div>
      <div class="route-stat"><span class="route-val">4</span><span class="route-lbl">Etappen</span></div>
      <div class="route-stat"><span class="route-val">{total_km / 4:.1f} km</span><span class="route-lbl">Ø pro Etappe</span></div>
    </div>

    <div class="stage-stats">{stage_stats_html}</div>

    <div id="route-map" style="height:450px;border-radius:12px;overflow:hidden;margin:20px 0;border:1px solid #2c3e50;"></div>

    <div class="chart-container" style="margin-top:0">
      <div style="color:#7f8c8d;font-size:.85em;margin-bottom:12px">Höhenprofil nach Etappen</div>
      <canvas id="elevation-chart" height="100"></canvas>
    </div>
  </div>

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script>
  (function() {{
    var stageMapPts = {stage_map_js};
    var stageChartPts = {stage_chart_js};
    var stageColors = {stage_colors_js};
    var bounds = {bounds_js};
    var stageLabels = {stage_labels_js};

    // Leaflet map
    var map = L.map('route-map').fitBounds(bounds, {{padding: [20, 20]}});
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '© OpenStreetMap · © CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }}).addTo(map);

    stageMapPts.forEach(function(pts, idx) {{
      L.polyline(pts, {{color: stageColors[idx], weight: 4, opacity: 0.9}})
        .addTo(map).bindPopup('Etappe ' + (idx + 1));
    }});

    // Start marker
    if (stageMapPts[0] && stageMapPts[0].length) {{
      L.circleMarker(stageMapPts[0][0], {{
        radius: 9, color: '#1a8a40', fillColor: '#2ecc71', fillOpacity: 1, weight: 2
      }}).addTo(map).bindPopup('Start');
    }}

    // Finish marker
    var last = stageMapPts[stageMapPts.length - 1];
    if (last && last.length) {{
      L.circleMarker(last[last.length - 1], {{
        radius: 9, color: '#922b21', fillColor: '#e74c3c', fillOpacity: 1, weight: 2
      }}).addTo(map).bindPopup('Ziel');
    }}

    // Stage start markers
    stageMapPts.forEach(function(pts, idx) {{
      if (idx > 0 && pts.length) {{
        L.circleMarker(pts[0], {{
          radius: 6, color: stageColors[idx], fillColor: stageColors[idx], fillOpacity: 0.85, weight: 2
        }}).addTo(map).bindPopup('Etappe ' + (idx + 1) + ' Start');
      }}
    }});

    // Chart.js elevation profile
    var datasets = stageChartPts.map(function(pts, idx) {{
      return {{
        label: stageLabels[idx],
        data: pts.map(function(p) {{ return {{x: p[0], y: p[1]}}; }}),
        borderColor: stageColors[idx],
        backgroundColor: stageColors[idx] + '33',
        fill: true,
        pointRadius: 0,
        borderWidth: 2,
        tension: 0.3
      }};
    }});
    var ctx = document.getElementById('elevation-chart').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{datasets: datasets}},
      options: {{
        responsive: true,
        interaction: {{mode: 'index', intersect: false}},
        plugins: {{
          legend: {{labels: {{color: '#ecf0f1', boxWidth: 14}}}},
          tooltip: {{
            callbacks: {{
              label: function(c) {{ return c.dataset.label + ': ' + c.parsed.y.toFixed(0) + ' m'; }},
              title: function(items) {{ return items[0].parsed.x.toFixed(1) + ' km'; }}
            }}
          }}
        }},
        scales: {{
          x: {{
            type: 'linear',
            title: {{display: true, text: 'Distanz (km)', color: '#7f8c8d'}},
            ticks: {{color: '#7f8c8d'}},
            grid: {{color: '#1e2d3d'}}
          }},
          y: {{
            title: {{display: true, text: 'Höhe (m)', color: '#7f8c8d'}},
            ticks: {{color: '#7f8c8d'}},
            grid: {{color: '#1e2d3d'}}
          }}
        }}
      }}
    }});
  }})();
  </script>"""


TYPE_META = {
    "rest": {
        "bg": "#1a2633", "bar": "#2c3e50", "icon": "😴", "label": "–",
        "hr_zone": "–", "hr_pct": "–", "hr_color": "#2c3e50",
        "rpe_low": 0, "rpe_high": 1, "rpe_label": "Ruhe · keine Belastung",
        "tips": ["Foam-Rolling 15–20 min", "Mobilität & Dehnen", "Schlaf 8+ h", "Ausreichend Wasser trinken", "Beine hochlegen"],
    },
    "easy": {
        "bg": "#0d2818", "bar": "#27ae60", "icon": "🟢", "label": "Easy",
        "hr_zone": "Zone 2", "hr_pct": "60–70 %", "hr_color": "#27ae60",
        "rpe_low": 3, "rpe_high": 4, "rpe_label": "Locker · komfortabel · Gespräch möglich",
        "tips": ["Nasentest: Immer durch die Nase atmen können", "Kadenz 175–180 spm anstreben", "Pace langsamer als gefühlt nötig", "Rucksack wie angegeben tragen", "Gut essen & trinken danach"],
    },
    "tempo": {
        "bg": "#2b1f00", "bar": "#f39c12", "icon": "⚡", "label": "Tempo",
        "hr_zone": "Zone 3–4", "hr_pct": "70–85 %", "hr_color": "#f39c12",
        "rpe_low": 6, "rpe_high": 7, "rpe_label": "Anstrengend · kontrolliert · kein Gespräch",
        "tips": ["Aufwärmen: 15 min locker vor dem Tempo", "Tempoabschnitte nie überpacen", "Abkühlen: 10 min locker ausklingen lassen", "HF im Zielbereich halten – nicht überziehen", "KH-Versorgung während und nach dem Lauf"],
    },
    "hills": {
        "bg": "#2b1200", "bar": "#e67e22", "icon": "⛰️", "label": "Berge",
        "hr_zone": "Zone 3–4", "hr_pct": "72–85 %", "hr_color": "#e67e22",
        "rpe_low": 6, "rpe_high": 8, "rpe_label": "Hart bergauf · Erholung bergab",
        "tips": ["Bergauf: kurze Schritte, Oberkörper leicht vorgelehnt", "Bergab: Bremsen vermeiden, Knie weich", "Auf flachen Abschnitten HF wieder senken", "Power-Hiking bergauf = spart Energie", "Marschtechnik (Stöcke) üben"],
    },
    "long": {
        "bg": "#0a1f3d", "bar": "#2980b9", "icon": "🔵", "label": "Lang",
        "hr_zone": "Zone 2–3", "hr_pct": "60–75 %", "hr_color": "#2980b9",
        "rpe_low": 4, "rpe_high": 5, "rpe_label": "Moderat · nachhaltig · konversationsfähig",
        "tips": ["Erste Hälfte bewusst langsamer als zweite", "Ernährung alle 45–60 min testen", "Hydration: 500 ml/h als Richtwert", "Rucksack vollständig bepacken wie im Rennen", "Mentale Stärke trainieren: Kopfkino positiv halten"],
    },
    "b2b": {
        "bg": "#1e0a2b", "bar": "#8e44ad", "icon": "🔥", "label": "B2B",
        "hr_zone": "Zone 2–3", "hr_pct": "62–76 %", "hr_color": "#8e44ad",
        "rpe_low": 5, "rpe_high": 7, "rpe_label": "Moderat bis hart · müde Beine akzeptieren",
        "tips": ["Ziel: Laufen auf müden Beinen – nicht Pace!", "Keine neuen Schuhe oder Ausrüstung testen", "Zwischen Tag 1 und 2: gut essen, Beine kühlen", "HF kann höher sein als normal – das ist okay", "Recovery-Protokoll nach dem Lauf konsequent"],
    },
    "active": {
        "bg": "#061a18", "bar": "#16a085", "icon": "🌿", "label": "Aktiv",
        "hr_zone": "Zone 1", "hr_pct": "< 60 %", "hr_color": "#16a085",
        "rpe_low": 1, "rpe_high": 2, "rpe_label": "Sehr locker · aktive Erholung",
        "tips": ["Spazieren, Schwimmen oder leichtes Radfahren", "Keine Intensität – Regeneration ist das Ziel", "Bewegung fördert Durchblutung und Erholung", "Dehnen & Mobilität 20–30 min", "Früh schlafen gehen"],
    },
    "race": {
        "bg": "#2b0000", "bar": "#e74c3c", "icon": "🏁", "label": "RACE",
        "hr_zone": "Zone 2–4", "hr_pct": "65–85 %", "hr_color": "#e74c3c",
        "rpe_low": 6, "rpe_high": 8, "rpe_label": "Renntempo · nachhaltig über den Tag",
        "tips": ["Früh starten (06:00) – Hitze meiden", "Siesta 12:00–15:00 Uhr strikt einhalten", "Wasser immer auf > 1,5 L auffüllen", "Ernährung alle 45 min – auch ohne Hunger", "Blasen sofort mit Leukoplast versorgen"],
    },
}


def render_week_card(week, week_idx):
    start_date = TODAY + timedelta(weeks=week_idx)
    # For race week, use actual race date
    if week["num"] == 9:
        start_date = datetime(2026, 5, 11)

    day_cells = ""
    for day in week["days"]:
        m = TYPE_META.get(day["type"], TYPE_META["rest"])
        km_str = f"{day['km']} km" if day["km"] else "–"
        elev_str = f"▲ {day['elev']} m" if day["elev"] else ""
        day_date = start_date + timedelta(days=["Mo","Di","Mi","Do","Fr","Sa","So"].index(day["d"]))
        # Build data payload for modal
        day_data = json.dumps({
            "weekNum": week["num"],
            "weekFocus": week["focus"],
            "weekColor": week["color"],
            "d": day["d"],
            "date": day_date.strftime("%d.%m.%Y"),
            "type": day["type"],
            "name": day["name"],
            "km": day["km"],
            "elev": day["elev"],
            "note": day["note"],
            "icon": m["icon"],
            "bar": m["bar"],
            "hr_zone": m["hr_zone"],
            "hr_pct": m["hr_pct"],
            "hr_color": m["hr_color"],
            "rpe_low": m["rpe_low"],
            "rpe_high": m["rpe_high"],
            "rpe_label": m["rpe_label"],
            "tips": m["tips"],
        }, ensure_ascii=False)
        day_cells += f"""
        <div class="day-cell" style="background:{m['bg']}; border-top: 3px solid {m['bar']}; cursor:pointer"
             onclick="openDayModal(this)" data-day='{day_data.replace("'", "&#39;")}'>
          <div class="day-header">
            <span class="day-name">{day['d']}</span>
            <span class="day-date-num">{day_date.strftime('%d.%m')}</span>
          </div>
          <div class="day-icon">{m['icon']}</div>
          <div class="day-workout">{day['name']}</div>
          <div class="day-km">{km_str}</div>
          {'<div class="day-elev">' + elev_str + '</div>' if elev_str else ''}
          <div class="day-note">{day['note']}</div>
          <div class="day-detail-hint">Details ansehen →</div>
        </div>"""

    is_race = week["num"] == 9
    km_label = f"🏁 130 km Rennen" if is_race else f"{week['total_km']} km · ▲ {week['total_elev']} m"

    return f"""
    <div class="week-card {'race-week-card' if is_race else ''}">
      <div class="week-header" style="border-left: 4px solid {week['color']}">
        <div class="week-header-left">
          <span class="week-num">{'RENNWOCHE' if is_race else 'Woche ' + str(week['num'])}</span>
          <span class="week-dates">{start_date.strftime('%d.%m.')} – {(start_date + timedelta(days=6)).strftime('%d.%m.%Y')}</span>
        </div>
        <div class="week-header-center">
          <span class="week-focus-tag" style="background:{week['color']}">{week['focus']}</span>
        </div>
        <div class="week-header-right">
          <span class="week-total">{km_label}</span>
        </div>
      </div>
      <div class="week-note">{week['note']}</div>
      <div class="week-days">{day_cells}</div>
    </div>"""


def render_html(athlete, stats, gpx_data=None):
    level, level_color = fitness_level(stats["avg_weekly_km"])
    race_gap_days = (RACE_DATE - TODAY).days

    # Weekly chart bars
    chart_bars = ""
    max_km = max((stats["weekly"][i]["dist"] / 1000 for i in range(8) if stats["weekly"][i]["count"] > 0), default=1)
    for i in range(7, -1, -1):
        w = stats["weekly"][i]
        wkm = w["dist"] / 1000
        date_label = (TODAY - timedelta(weeks=i)).strftime("KW%V")
        pct = (wkm / max(max_km, 1)) * 100
        color = "#e74c3c" if i == 0 else "#3498db"
        chart_bars += f"""
        <div class="bar-wrap">
          <div class="bar-label">{wkm:.0f} km</div>
          <div class="bar" style="height:{max(pct,3):.0f}%; background:{color}"></div>
          <div class="bar-date">{date_label}</div>
        </div>"""

    # Recent activities table rows
    activity_rows = ""
    for a in stats["recent"]:
        date = datetime.fromisoformat(a["start_date_local"].replace("Z", "+00:00")).strftime("%d.%m.%Y")
        sport = a.get("sport_type") or a.get("type", "?")
        d = km(a.get("distance", 0))
        t = hms(a.get("moving_time", 0))
        e = a.get("total_elevation_gain", 0)
        name = a.get("name", "–")
        hr = f"{a['average_heartrate']:.0f} bpm" if a.get("average_heartrate") else "–"
        activity_rows += f"""
        <tr>
          <td>{date}</td>
          <td><span class="tag">{sport}</span></td>
          <td>{name}</td>
          <td><strong>{d:.1f} km</strong></td>
          <td>{t}</td>
          <td>{e:.0f} m</td>
          <td>{hr}</td>
        </tr>"""

    # Legend items
    legend = "".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{v["bar"]}"></span>{k.capitalize()}</span>'
        for k, v in TYPE_META.items()
    )

    # All week cards
    week_cards = "".join(render_week_card(w, i) for i, w in enumerate(WEEKLY_PLAN))
    gpx_section = render_gpx_section(gpx_data) if gpx_data else ""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Tabernas Desert Ultra 2026 – Race Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1923; color: #ecf0f1; line-height: 1.4; }}

  /* ── HERO ────────────────────────── */
  .hero {{
    background: linear-gradient(135deg, #1a0a00 0%, #3d1500 40%, #8b3a00 70%, #c9601a 100%);
    padding: 60px 40px 45px; text-align: center; position: relative; overflow: hidden;
  }}
  .hero::before {{
    content:''; position:absolute; inset:0;
    background:repeating-linear-gradient(45deg,transparent,transparent 40px,rgba(255,255,255,.02) 40px,rgba(255,255,255,.02) 80px);
  }}
  .hero h1 {{ font-size:3em; font-weight:900; letter-spacing:-1px; text-shadow:0 2px 20px rgba(0,0,0,.5); position:relative; }}
  .hero .sub {{ font-size:1.1em; color:#f39c12; margin-top:8px; font-weight:300; letter-spacing:3px; text-transform:uppercase; }}
  .hero .countdown {{ margin-top:20px; font-size:4em; font-weight:900; color:#f39c12; }}
  .hero .countdown-label {{ font-size:.85em; color:rgba(255,255,255,.55); letter-spacing:2px; }}
  .race-info {{ display:flex; gap:12px; justify-content:center; margin-top:28px; flex-wrap:wrap; }}
  .race-chip {{
    background:rgba(255,255,255,.1); backdrop-filter:blur(10px);
    border:1px solid rgba(255,255,255,.15); border-radius:30px; padding:7px 18px; font-size:.88em;
  }}

  /* ── LAYOUT ──────────────────────── */
  .container {{ max-width:1280px; margin:0 auto; padding:40px 20px; }}
  .section {{ margin-bottom:56px; }}
  .section-title {{
    font-size:1.35em; font-weight:700; margin-bottom:20px;
    display:flex; align-items:center; gap:12px;
    border-bottom:2px solid #2c3e50; padding-bottom:10px;
  }}

  /* ── STAT CARDS ──────────────────── */
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; }}
  .card {{
    background:#1e2d3d; border-radius:14px; padding:22px 20px;
    border:1px solid #2c3e50; transition:transform .2s;
  }}
  .card:hover {{ transform:translateY(-3px); }}
  .card .value {{ font-size:2.1em; font-weight:900; color:#f39c12; }}
  .card .label {{ font-size:.76em; color:#7f8c8d; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }}
  .level-badge {{ display:inline-block; padding:4px 14px; border-radius:20px; font-size:.85em; font-weight:700; color:#fff; background:{level_color}; }}

  /* ── CHART ───────────────────────── */
  .chart-container {{ background:#1e2d3d; border-radius:16px; padding:30px; border:1px solid #2c3e50; }}
  .bars {{ display:flex; align-items:flex-end; gap:10px; height:180px; margin-top:20px; }}
  .bar-wrap {{ flex:1; display:flex; flex-direction:column; align-items:center; gap:5px; height:100%; justify-content:flex-end; }}
  .bar {{ width:100%; border-radius:6px 6px 0 0; min-height:4px; }}
  .bar-label {{ font-size:.72em; color:#7f8c8d; }}
  .bar-date {{ font-size:.68em; color:#5d6d7e; margin-top:4px; }}

  /* ── LOCATION ────────────────────── */
  .location-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
  .location-card {{ background:#1e2d3d; border-radius:14px; padding:22px; border:1px solid #2c3e50; }}
  .location-card h3 {{ color:#f39c12; margin-bottom:12px; font-size:1em; }}
  .location-card ul {{ list-style:none; }}
  .location-card li {{ padding:5px 0; border-bottom:1px solid #2c3e50; font-size:.88em; }}
  .location-card li:last-child {{ border:none; }}
  .location-card li strong {{ color:#e74c3c; }}
  .warning-box {{ background:linear-gradient(135deg,#2c1810,#3d1a00); border:1px solid #e74c3c; border-radius:12px; padding:20px; margin-top:18px; }}
  .warning-box h4 {{ color:#e74c3c; margin-bottom:10px; }}
  .warning-box li {{ padding:4px 0; font-size:.88em; list-style:none; }}
  .warning-box li::before {{ content:"⚠️ "; }}

  /* ── LEGEND ──────────────────────── */
  .legend {{ display:flex; flex-wrap:wrap; gap:14px; margin-bottom:20px; }}
  .legend-item {{ display:flex; align-items:center; gap:6px; font-size:.82em; color:#95a5a6; }}
  .legend-dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0; }}

  /* ── WEEK CARD ───────────────────── */
  .week-card {{
    background:#141e2b; border-radius:16px; overflow:hidden;
    border:1px solid #2c3e50; margin-bottom:24px;
  }}
  .race-week-card {{ border-color:#e74c3c; box-shadow:0 0 30px rgba(231,76,60,.15); }}
  .week-header {{
    display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap;
    padding:16px 22px; background:#1a2535; gap:10px;
  }}
  .week-header-left {{ display:flex; flex-direction:column; gap:3px; }}
  .week-num {{ font-size:1em; font-weight:800; color:#ecf0f1; }}
  .week-dates {{ font-size:.78em; color:#7f8c8d; }}
  .week-header-center {{ }}
  .week-focus-tag {{ padding:5px 14px; border-radius:20px; font-size:.82em; font-weight:700; color:#fff; }}
  .week-header-right {{ }}
  .week-total {{ font-size:.85em; color:#bdc3c7; }}
  .week-note {{ padding:10px 22px; font-size:.82em; color:#95a5a6; background:#111c29; border-bottom:1px solid #2c3e50; font-style:italic; }}

  /* ── DAY GRID ────────────────────── */
  .week-days {{
    display:grid;
    grid-template-columns:repeat(7,1fr);
  }}
  .day-cell {{
    padding:14px 10px; border-right:1px solid #1e2d3d;
    display:flex; flex-direction:column; gap:5px; min-height:140px;
  }}
  .day-cell:last-child {{ border-right:none; }}
  .day-header {{ display:flex; justify-content:space-between; align-items:center; }}
  .day-name {{ font-size:.75em; font-weight:800; color:#7f8c8d; text-transform:uppercase; letter-spacing:1px; }}
  .day-date-num {{ font-size:.7em; color:#4a5a6a; }}
  .day-icon {{ font-size:1.3em; margin:2px 0; }}
  .day-workout {{ font-size:.82em; font-weight:700; color:#ecf0f1; line-height:1.2; }}
  .day-km {{ font-size:1em; font-weight:900; color:#f39c12; margin-top:2px; }}
  .day-elev {{ font-size:.75em; color:#3498db; }}
  .day-note {{ font-size:.72em; color:#7f8c8d; margin-top:auto; line-height:1.3; }}

  /* ── TABLES ──────────────────────── */
  .table-wrap {{ background:#1e2d3d; border-radius:16px; overflow:hidden; border:1px solid #2c3e50; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#16213e; padding:11px 15px; text-align:left; font-size:.78em; text-transform:uppercase; letter-spacing:1px; color:#7f8c8d; }}
  td {{ padding:11px 15px; border-bottom:1px solid #111c29; font-size:.88em; vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:rgba(255,255,255,.02); }}
  .tag {{ background:#2c3e50; padding:3px 10px; border-radius:12px; font-size:.8em; }}

  /* ── GEAR ────────────────────────── */
  .gear-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; }}
  .gear-card {{ background:#1e2d3d; border-radius:12px; padding:20px; border:1px solid #2c3e50; }}
  .gear-card h4 {{ color:#3498db; margin-bottom:10px; font-size:.95em; }}
  .gear-card li {{ font-size:.83em; padding:3px 0; list-style:none; }}
  .gear-card li::before {{ content:"✓ "; color:#27ae60; }}

  /* ── GPX ROUTE ───────────────────── */
  .route-summary {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:16px; }}
  .route-stat {{
    flex:1; min-width:130px; background:#1e2d3d; border-radius:12px;
    padding:18px 20px; border:1px solid #2c3e50; display:flex; flex-direction:column; gap:4px;
  }}
  .route-val {{ font-size:1.8em; font-weight:900; color:#f39c12; }}
  .route-lbl {{ font-size:.73em; color:#7f8c8d; text-transform:uppercase; letter-spacing:1px; }}
  .stage-stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }}
  .stage-stat-card {{
    background:#1e2d3d; border-radius:10px; padding:16px;
    border:1px solid #2c3e50; text-align:center;
  }}
  .stage-num {{ font-size:.8em; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; }}
  .stage-km {{ font-size:1.4em; font-weight:900; color:#ecf0f1; }}
  .stage-elev {{ font-size:.82em; color:#3498db; margin-top:3px; }}

  .footer {{ text-align:center; padding:40px; color:#5d6d7e; font-size:.83em; }}

  /* ── DAY DETAIL HINT ─────────────── */
  .day-detail-hint {{
    font-size:.65em; color:#3498db; margin-top:auto; opacity:0;
    transition: opacity .2s;
    text-align:right; padding-top:4px;
  }}
  .day-cell:hover .day-detail-hint {{ opacity:1; }}
  .day-cell:hover {{ box-shadow: inset 0 0 0 1px rgba(52,152,219,.4); }}

  /* ── DAY MODAL ───────────────────── */
  .day-modal-overlay {{
    display:none; position:fixed; inset:0; background:rgba(0,0,0,.75);
    z-index:1000; align-items:center; justify-content:center; padding:20px;
  }}
  .day-modal-overlay.open {{ display:flex; }}
  .day-modal {{
    background:#141e2b; border-radius:20px; max-width:540px; width:100%;
    border:1px solid #2c3e50; overflow:hidden; position:relative;
    animation: modalIn .2s ease;
  }}
  @keyframes modalIn {{ from {{ transform:scale(.94); opacity:0; }} to {{ transform:scale(1); opacity:1; }} }}
  .day-modal-header {{
    padding:22px 26px 18px; display:flex; align-items:flex-start; gap:14px;
    border-bottom:1px solid #1e2d3d;
  }}
  .day-modal-icon {{ font-size:2.4em; line-height:1; }}
  .day-modal-title {{ flex:1; }}
  .day-modal-title h2 {{ font-size:1.25em; font-weight:800; color:#ecf0f1; }}
  .day-modal-title .day-modal-meta {{
    font-size:.78em; color:#7f8c8d; margin-top:3px; display:flex; gap:12px; flex-wrap:wrap;
  }}
  .day-modal-close {{
    background:none; border:none; color:#7f8c8d; font-size:1.6em; cursor:pointer;
    line-height:1; padding:0 4px; transition:color .15s;
  }}
  .day-modal-close:hover {{ color:#ecf0f1; }}
  .day-modal-body {{ padding:22px 26px; display:flex; flex-direction:column; gap:18px; }}

  /* HR Zone */
  .modal-section-label {{
    font-size:.7em; text-transform:uppercase; letter-spacing:1.5px; color:#7f8c8d; margin-bottom:8px;
  }}
  .hr-zone-bar {{
    display:flex; gap:3px; height:10px; border-radius:6px; overflow:hidden; margin-bottom:8px;
  }}
  .hr-zone-seg {{ flex:1; }}
  .hr-zone-info {{ display:flex; justify-content:space-between; align-items:center; }}
  .hr-zone-badge {{
    padding:4px 12px; border-radius:20px; font-size:.78em; font-weight:700; color:#fff;
  }}
  .hr-zone-pct {{ font-size:.78em; color:#bdc3c7; }}

  /* RPE */
  .rpe-track {{
    display:flex; gap:3px; margin-bottom:8px;
  }}
  .rpe-dot {{
    flex:1; height:10px; border-radius:3px; background:#1e2d3d;
    transition: background .15s;
  }}
  .rpe-info {{ display:flex; justify-content:space-between; align-items:center; }}
  .rpe-label {{ font-size:.78em; color:#bdc3c7; }}
  .rpe-num {{ font-size:.78em; color:#7f8c8d; }}

  /* Workout stats row */
  .modal-stats {{ display:flex; gap:10px; }}
  .modal-stat {{
    flex:1; background:#1e2d3d; border-radius:10px; padding:12px;
    text-align:center; border:1px solid #2c3e50;
  }}
  .modal-stat .val {{ font-size:1.3em; font-weight:900; color:#f39c12; }}
  .modal-stat .lbl {{ font-size:.65em; color:#7f8c8d; text-transform:uppercase; letter-spacing:1px; margin-top:2px; }}

  /* Tips */
  .modal-tips {{ list-style:none; }}
  .modal-tips li {{
    font-size:.84em; padding:6px 0; border-bottom:1px solid #1e2d3d; color:#bdc3c7;
    display:flex; gap:8px; align-items:flex-start;
  }}
  .modal-tips li:last-child {{ border-bottom:none; }}
  .modal-tips li::before {{ content:"→"; color:#3498db; flex-shrink:0; }}

  /* Note */
  .modal-note {{
    background:#111c29; border-radius:10px; padding:12px 16px;
    font-size:.83em; color:#95a5a6; border-left:3px solid #2c3e50; font-style:italic;
  }}

  @media(max-width:900px) {{
    .location-grid {{ grid-template-columns:1fr; }}
    .week-days {{ grid-template-columns:repeat(4,1fr); }}
    .stage-stats {{ grid-template-columns:repeat(2,1fr); }}
  }}
  @media(max-width:600px) {{
    .hero h1 {{ font-size:1.9em; }}
    .hero .countdown {{ font-size:2.8em; }}
    .week-days {{ grid-template-columns:repeat(2,1fr); }}
    .stage-stats {{ grid-template-columns:1fr 1fr; }}
  }}
</style>
</head>
<body>

<!-- DAY DETAIL MODAL -->
<div class="day-modal-overlay" id="dayModalOverlay" onclick="closeDayModal(event)">
  <div class="day-modal" id="dayModal">
    <div class="day-modal-header">
      <div class="day-modal-icon" id="modalIcon"></div>
      <div class="day-modal-title">
        <h2 id="modalTitle"></h2>
        <div class="day-modal-meta">
          <span id="modalDate"></span>
          <span id="modalWeek"></span>
        </div>
      </div>
      <button class="day-modal-close" onclick="document.getElementById('dayModalOverlay').classList.remove('open')">✕</button>
    </div>
    <div class="day-modal-body">
      <!-- Stats -->
      <div id="modalStats" class="modal-stats"></div>
      <!-- HR Zone -->
      <div id="modalHrSection">
        <div class="modal-section-label">Herzfrequenz-Zone</div>
        <div class="hr-zone-bar" id="modalHrBar">
          <div class="hr-zone-seg" style="background:#1e6b2e"></div>
          <div class="hr-zone-seg" style="background:#27ae60"></div>
          <div class="hr-zone-seg" style="background:#f39c12"></div>
          <div class="hr-zone-seg" style="background:#e67e22"></div>
          <div class="hr-zone-seg" style="background:#e74c3c"></div>
        </div>
        <div class="hr-zone-info">
          <span class="hr-zone-badge" id="modalHrBadge"></span>
          <span class="hr-zone-pct" id="modalHrPct"></span>
        </div>
        <div style="font-size:.7em; color:#4a5a6a; margin-top:6px">Z1 &lt;60% · Z2 60–70% · Z3 70–80% · Z4 80–90% · Z5 &gt;90% HFmax</div>
      </div>
      <!-- RPE -->
      <div>
        <div class="modal-section-label">RPE – Belastungsempfinden (1–10)</div>
        <div class="rpe-track" id="modalRpeTrack"></div>
        <div class="rpe-info">
          <span class="rpe-label" id="modalRpeLabel"></span>
          <span class="rpe-num" id="modalRpeNum"></span>
        </div>
      </div>
      <!-- Note -->
      <div class="modal-note" id="modalNote"></div>
      <!-- Tips -->
      <div>
        <div class="modal-section-label">Trainings-Tipps</div>
        <ul class="modal-tips" id="modalTips"></ul>
      </div>
    </div>
  </div>
</div>
<script>
function openDayModal(el) {{
  var d = JSON.parse(el.getAttribute('data-day'));
  document.getElementById('modalIcon').textContent = d.icon;
  document.getElementById('modalTitle').textContent = d.name;
  document.getElementById('modalDate').textContent = d.d + ', ' + d.date;
  document.getElementById('modalWeek').textContent = 'Woche ' + d.weekNum + ' – ' + d.weekFocus;

  // Stats
  var statsHtml = '';
  if (d.km > 0) statsHtml += '<div class="modal-stat"><div class="val">' + d.km + ' km</div><div class="lbl">Distanz</div></div>';
  if (d.elev > 0) statsHtml += '<div class="modal-stat"><div class="val">▲ ' + d.elev + ' m</div><div class="lbl">Anstieg</div></div>';
  if (d.hr_zone !== '–') statsHtml += '<div class="modal-stat"><div class="val" style="color:' + d.hr_color + '">' + d.hr_zone + '</div><div class="lbl">HF-Zone</div></div>';
  if (d.rpe_high > 0) statsHtml += '<div class="modal-stat"><div class="val">' + (d.rpe_low === d.rpe_high ? d.rpe_low : d.rpe_low + '–' + d.rpe_high) + ' / 10</div><div class="lbl">RPE</div></div>';
  document.getElementById('modalStats').innerHTML = statsHtml;

  // HR Zone bar highlight
  var hrBar = document.getElementById('modalHrBar');
  var segs = hrBar.querySelectorAll('.hr-zone-seg');
  var zoneColors = ['#1e6b2e','#27ae60','#f39c12','#e67e22','#e74c3c'];
  var dimColors  = ['#0d2e14','#163d20','#2b1f00','#1e1000','#200000'];
  segs.forEach(function(s, i) {{
    s.style.background = dimColors[i];
  }});
  var zoneMap = {{'Zone 1':0,'Zone 2':1,'Zone 3':2,'Zone 3–4':[2,3],'Zone 4':3,'Zone 5':4,'Zone 2–3':[1,2],'Zone 2–4':[1,2,3]}};
  var active = zoneMap[d.hr_zone];
  if (active !== undefined) {{
    if (!Array.isArray(active)) active = [active];
    active.forEach(function(idx) {{ segs[idx].style.background = zoneColors[idx]; }});
  }}
  document.getElementById('modalHrBadge').textContent = d.hr_zone;
  document.getElementById('modalHrBadge').style.background = d.hr_color;
  document.getElementById('modalHrPct').textContent = d.hr_pct + ' HFmax';
  var hrSection = document.getElementById('modalHrSection');
  hrSection.style.display = (d.hr_zone === '–') ? 'none' : 'block';

  // RPE track
  var rpeTrack = document.getElementById('modalRpeTrack');
  rpeTrack.innerHTML = '';
  for (var i = 1; i <= 10; i++) {{
    var dot = document.createElement('div');
    dot.className = 'rpe-dot';
    var active_rpe = (i >= d.rpe_low && i <= d.rpe_high);
    var rpe_color = i <= 3 ? '#27ae60' : i <= 5 ? '#f1c40f' : i <= 7 ? '#e67e22' : '#e74c3c';
    dot.style.background = active_rpe ? rpe_color : '#1e2d3d';
    rpeTrack.appendChild(dot);
  }}
  document.getElementById('modalRpeLabel').textContent = d.rpe_label;
  document.getElementById('modalRpeNum').textContent = 'RPE ' + (d.rpe_low === d.rpe_high ? d.rpe_low : d.rpe_low + '–' + d.rpe_high) + ' / 10';

  // Note
  document.getElementById('modalNote').textContent = d.note;

  // Tips
  var tips = d.tips || [];
  document.getElementById('modalTips').innerHTML = tips.map(function(t) {{
    return '<li>' + t + '</li>';
  }}).join('');

  document.getElementById('dayModalOverlay').classList.add('open');
}}
function closeDayModal(e) {{
  if (e.target === document.getElementById('dayModalOverlay')) {{
    document.getElementById('dayModalOverlay').classList.remove('open');
  }}
}}
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') document.getElementById('dayModalOverlay').classList.remove('open');
}});
</script>

<div class="hero">
  <div class="sub">Race Preparation Report</div>
  <h1>Tabernas Desert Ultra</h1>
  <div class="sub">130 km · 1.600 hm · 4 Tage · Solo Unsupported · 18.–22. Mai 2026</div>
  <div class="countdown">{race_gap_days}</div>
  <div class="countdown-label">Tage bis zum Start</div>
  <div class="race-info">
    <span class="race-chip">📍 Tabernas, Almería · Spanien</span>
    <span class="race-chip">🌡️ 20–30 °C Tageshitze</span>
    <span class="race-chip">☀️ 13+ Sonnenstunden/Tag</span>
    <span class="race-chip">🏜️ Europas einzige Wüste</span>
    <span class="race-chip">🎒 {athlete.get('firstname','Philipp')} {athlete.get('lastname','')}</span>
  </div>
</div>

<div class="container">

  <!-- AUSGANGSSITUATION -->
  <div class="section">
    <div class="section-title">📊 Aktuelle Ausgangssituation</div>
    <div style="margin-bottom:14px">Fitnesslevel: <span class="level-badge">{level}</span></div>
    <div class="cards">
      <div class="card"><div class="value">{stats['avg_weekly_km']:.0f} km</div><div class="label">Ø Wochenumfang (8W)</div></div>
      <div class="card"><div class="value">{stats['max_long_run']:.0f} km</div><div class="label">Längster Lauf (8W)</div></div>
      <div class="card"><div class="value">{stats['avg_weekly_elev']:.0f} m</div><div class="label">Ø Höhengewinn/Woche</div></div>
      <div class="card"><div class="value">{stats['total_dist']:.0f} km</div><div class="label">Gesamt-Distanz</div></div>
      <div class="card"><div class="value">{stats['total_runs']}</div><div class="label">Laufaktivitäten</div></div>
      <div class="card"><div class="value">{f"{stats['avg_hr']:.0f}" if stats['avg_hr'] else '–'} bpm</div><div class="label">Ø Herzfrequenz</div></div>
    </div>
  </div>

  <!-- CHART -->
  <div class="section">
    <div class="section-title">📈 Trainingsumfang letzte 8 Wochen</div>
    <div class="chart-container">
      <div style="color:#7f8c8d;font-size:.85em">Wochenkilometer · aktuelle Woche in Rot</div>
      <div class="bars">{chart_bars}</div>
    </div>
  </div>

  <!-- LOCATION -->
  <div class="section">
    <div class="section-title">🏜️ Location-Analyse: Tabernas Desert</div>
    <div class="location-grid">
      <div class="location-card">
        <h3>Geographie & Terrain</h3>
        <ul>
          <li>Europas einzige echte Wüste (280 km²)</li>
          <li>Provinz Almería, Andalusien, Spanien</li>
          <li>Höhe: 400–800 m ü. NN</li>
          <li>Badlands: Marl, Sandstein, Erosionsschluchten</li>
          <li>Ramblas (Trockenflussbetten) · lose Felsen</li>
          <li>Kein Schatten auf weiten Abschnitten</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Klima im Mai</h3>
        <ul>
          <li>🌡️ Tagestemperatur: <strong>20–30 °C</strong> (Spitzen 35 °C)</li>
          <li>🌙 Nächte: 12–16 °C</li>
          <li>☀️ Sonnenstunden: 13+ h/Tag</li>
          <li>💧 Niederschlag: &lt; 20 mm/Monat</li>
          <li>💨 Levante-Wind: trocken &amp; warm</li>
          <li>🔆 UV-Index: Sehr Hoch bis Extrem</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Renndaten</h3>
        <ul>
          <li>Gesamt-Distanz: <strong>130 km</strong></li>
          <li>Höhengewinn: <strong>1.600 m</strong></li>
          <li>Etappen: <strong>4 Tage</strong> (≈ 32,5 km/Tag)</li>
          <li>Ø Höhengewinn/Tag: <strong>≈ 400 m</strong></li>
          <li>Format: Solo Unsupported</li>
          <li>Rucksack-Gewicht: 7–10 kg</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Tages-Strategie</h3>
        <ul>
          <li>⏰ Start täglich 05:30–06:00 Uhr</li>
          <li>🌞 Siesta 12:00–15:00 Uhr (Hitze!)</li>
          <li>🌇 Abendmarsch bis Sonnenuntergang</li>
          <li>💧 Mindest-Wasserkapazität: 3 L</li>
          <li>🗺️ GPX-Track + Offline-Backup</li>
          <li>📊 ≈ 8–10 h Bewegungszeit/Tag</li>
        </ul>
      </div>
    </div>
    <div class="warning-box">
      <h4>Kritische Faktoren</h4>
      <ul>
        <li>Hitzeschlag-Risiko: Körpertemperatur im Auge behalten, bei Schwindel sofort Schatten suchen</li>
        <li>Wasser: Quellen vorab auf Karte markieren, nie mit unter 1,5 L starten</li>
        <li>Sonnenschutz: Langarmshirt UPF50+, Wüstentuch, Sonnenbrille Kat. 4, SPF50+ alle 2 h</li>
        <li>Navigation: Kein Mobilnetz – GPX offline auf Garmin/Coros UND Smartphone</li>
        <li>Blasenpflege ab Tag 1: Leukoplast präventiv kleben, nie warten bis es brennt</li>
      </ul>
    </div>
  </div>

  {gpx_section}

  <!-- TRAININGSPLAN -->
  <div class="section">
    <div class="section-title">📅 8-Wochen-Trainingsplan – Tag für Tag</div>
    <div style="color:#7f8c8d;font-size:.84em;margin-bottom:16px">
      Ausgangsbasis: {stats['avg_weekly_km']:.0f} km/Woche · Ziel: 130 km / 4 Tage · {WEEKS_TO_RACE} Wochen bis zum Start
    </div>
    <div class="legend">{legend}</div>
    {week_cards}
  </div>

  <!-- GEAR -->
  <div class="section">
    <div class="section-title">🎒 Ausrüstung – Solo Unsupported</div>
    <div class="gear-grid">
      <div class="gear-card"><h4>Bekleidung</h4><ul>
        <li>Langarm UV-Shirt UPF 50+</li><li>Trailshorts mit Einlage</li>
        <li>Wüstentuch / Buff</li><li>Kappe mit Nackenschutz</li>
        <li>Sonnenbrille Kat. 4</li><li>Gamaschen gegen Sand</li>
        <li>Dünne Wärmejacke für Nächte</li>
      </ul></div>
      <div class="gear-card"><h4>Schuhe & Füße</h4><ul>
        <li>Trailschuhe mit Sandschutz (getestet!)</li>
        <li>2× Wechselsocken (dünn + dick)</li>
        <li>Leukoplast präventiv</li><li>Schmiercreme Anti-Chafe</li>
        <li>Blasenpflaster (Compeed)</li>
        <li>Nagelschere / Pinzette</li>
      </ul></div>
      <div class="gear-card"><h4>Navigation & Safety</h4><ul>
        <li>GPS-Uhr mit GPX-Track</li>
        <li>Smartphone + Offline-Karte</li>
        <li>Power-Bank (10.000 mAh)</li>
        <li>Notfallpfeife</li><li>Rettungsdecke</li>
        <li>Stirnlampe + Ersatz-Akkus</li>
      </ul></div>
      <div class="gear-card"><h4>Ernährung & Wasser</h4><ul>
        <li>Wasserreservoir 2 L + 1 L Flasche</li>
        <li>Wasserfilter / Tabs (Backup)</li>
        <li>Gels + Riegel: 250–300 kcal/h</li>
        <li>Salztabletten (Natrium!)</li>
        <li>Trekkingnahrung (Abende)</li>
        <li>Gesamtbedarf: 2.500–3.000 kcal/Tag</li>
      </ul></div>
    </div>
  </div>

  <!-- LETZTE AKTIVITÄTEN -->
  <div class="section">
    <div class="section-title">🏃 Letzte 10 Aktivitäten</div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Datum</th><th>Sport</th><th>Name</th><th>Distanz</th><th>Zeit</th><th>Höhe</th><th>HF</th></tr></thead>
        <tbody>{activity_rows}</tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">
  Generiert am {TODAY.strftime('%d.%m.%Y')} · Strava-Daten von {athlete.get('firstname','')} {athlete.get('lastname','')} · Tabernas Desert Ultra 18.–22. Mai 2026
</div>
</body>
</html>"""


def main():
    if not ACCESS_TOKEN:
        sys.exit("STRAVA_ACCESS_TOKEN nicht gesetzt.")

    gpx_path = next((a for a in sys.argv[1:] if a.endswith(".gpx")), None)
    gpx_data = None
    if gpx_path:
        print(f"Lade GPX-Route: {gpx_path}")
        gpx_data = parse_gpx(gpx_path)
        if gpx_data:
            print(f"GPX: {gpx_data['total_km']:.1f} km · ▲ {gpx_data['total_elev']:.0f} m")
            update_race_week_from_gpx(gpx_data)
        else:
            print("GPX konnte nicht gelesen werden, wird übersprungen.")

    print("Verbinde mit Strava...")
    try:
        athlete = fetch_athlete()
        print(f"Eingeloggt als: {athlete.get('firstname')} {athlete.get('lastname')}")
    except Exception as e:
        print(f"Strava-Profil konnte nicht geladen werden: {e}")
        athlete = {"firstname": "Philipp", "lastname": ""}

    print("Lade Aktivitäten...")
    try:
        activities = fetch_activities()
        print(f"{len(activities)} Aktivitäten geladen.")
    except Exception as e:
        print(f"Aktivitäten konnten nicht geladen werden (Token-Scope?): {e}")
        print("Generiere Report ohne Strava-Daten...")
        activities = []

    print("Analysiere Daten...")
    stats = analyze_strava(activities)

    print("Generiere Report...")
    html = render_html(athlete, stats, gpx_data)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tabernas_race_report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport gespeichert: {out}")
    print("Öffne Browser...")
    webbrowser.open(f"file://{out}")
    print("Fertig!")


if __name__ == "__main__":
    main()
