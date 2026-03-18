"""
Strava Race Report – Tabernas Desert Ultra 2026
Analysiert Strava-Daten und erstellt einen personalisierten Trainingsplan als HTML-Report.
"""
import os
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
STRAVA_API_BASE = "https://www.strava.com/api/v3"
RACE_DATE = datetime(2026, 5, 18)
TODAY = datetime.now()
WEEKS_TO_RACE = max(1, (RACE_DATE - TODAY).days // 7)


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


def pace(dist_m, time_s):
    if not dist_m: return "–"
    mpk = (time_s / 60) / (dist_m / 1000)
    return f"{int(mpk)}:{int((mpk % 1) * 60):02d} /km"


def analyze_strava(activities):
    run_types = {"Run", "TrailRun", "VirtualRun", "Hike"}
    runs = [a for a in activities if (a.get("sport_type") or a.get("type", "")) in run_types]

    # Last 8 weeks weekly stats
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

    # Recent 12 weeks avg
    recent_weeks = [weekly[i] for i in range(8) if weekly[i]["count"] > 0]
    avg_weekly_km = sum(w["dist"] for w in recent_weeks) / max(1, len(recent_weeks)) / 1000
    avg_weekly_elev = sum(w["elev"] for w in recent_weeks) / max(1, len(recent_weeks))
    max_long_run = max((w["long"] for w in recent_weeks), default=0) / 1000

    # All-time stats
    total_runs = len(runs)
    total_dist = sum(a.get("distance", 0) for a in runs)
    total_elev = sum(a.get("total_elevation_gain", 0) for a in runs)

    # Last 10 activities
    recent = sorted(activities, key=lambda a: a["start_date_local"], reverse=True)[:10]

    # HR data
    hr_runs = [a for a in runs if a.get("average_heartrate")]
    avg_hr = sum(a["average_heartrate"] for a in hr_runs) / len(hr_runs) if hr_runs else None
    max_hr = max((a.get("max_heartrate", 0) for a in hr_runs), default=None)

    # Sport breakdown
    by_type = defaultdict(lambda: {"count": 0, "dist": 0, "elev": 0})
    for a in activities:
        sport = a.get("sport_type") or a.get("type", "Other")
        by_type[sport]["count"] += 1
        by_type[sport]["dist"] += a.get("distance", 0)
        by_type[sport]["elev"] += a.get("total_elevation_gain", 0)

    return {
        "total_runs": total_runs,
        "total_dist": total_dist / 1000,
        "total_elev": total_elev,
        "avg_weekly_km": avg_weekly_km,
        "avg_weekly_elev": avg_weekly_elev,
        "max_long_run": max_long_run,
        "weekly": weekly,
        "recent": recent,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "by_type": dict(by_type),
    }


def fitness_level(avg_km):
    if avg_km < 20: return ("Einsteiger", "#e67e22")
    if avg_km < 40: return ("Fortgeschrittener", "#f1c40f")
    if avg_km < 70: return ("Erfahren", "#2ecc71")
    return ("Ultra-Erfahren", "#27ae60")


def generate_training_plan(stats):
    base_km = stats["avg_weekly_km"]
    base_elev = stats["avg_weekly_elev"]
    # Target: 4-day race, ~33km/day, 400m elev/day
    # Build to back-to-back long days
    # 8 weeks plan

    plan = []
    week_templates = [
        # Week, focus, km_mult, elev_mult, long_run_km, back2back, notes
        (1, "Basisaufbau", 1.0, 1.0, min(base_km * 0.5, 22), False,
         "Gleichmaessige Laeufe, Ruecksack tragen (3–5 kg), Schrittfrequenz optimieren"),
        (2, "Ausdauer", 1.1, 1.1, min(base_km * 0.6, 26), False,
         "Langer Lauf am Wochenende, Ernaehrungsstrategie testen, Hitzeanpassung beginnen"),
        (3, "Intensitaet", 1.15, 1.2, min(base_km * 0.7, 30), False,
         "Tempolaeufe, Bergintervals, Ausruestung vollstaendig testen"),
        (4, "Entlastung", 0.75, 0.8, min(base_km * 0.55, 24), False,
         "Erholungswoche – aktive Regeneration, Dehnen, Schlaf priorisieren"),
        (5, "Spezifisch", 1.2, 1.3, min(base_km * 0.8, 35), True,
         "Erste Back-to-Back-Tage! 2 Tage hintereinander je 25–30 km, Ruecksack voll beladen"),
        (6, "Peak", 1.25, 1.4, min(base_km * 0.9, 38), True,
         "Haerteste Woche: 3 konsekutive Tage laufen, Hitzetraining, mentale Staerke"),
        (7, "Tapering", 0.6, 0.65, 20, False,
         "Umfang reduzieren, Qualitaet halten, letzte Ausruestungschecks, Mentale Vorbereitung"),
        (8, "Race Week", 0, 0, 0, False,
         "Anreise Mo/Di, kurze Aktivierungslaeufe, gut schlafen, hydratisieren"),
    ]

    for i, (wnum, focus, km_m, elev_m, long_km, b2b, note) in enumerate(week_templates):
        week_start = TODAY + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        planned_km = round(max(base_km * km_m, 10)) if km_m > 0 else 0
        planned_elev = round(max(base_elev * elev_m, 200)) if elev_m > 0 else 0
        plan.append({
            "week": wnum,
            "focus": focus,
            "km": planned_km,
            "elev": planned_elev,
            "long": round(long_km, 1),
            "b2b": b2b,
            "note": note,
            "date_range": f"{week_start.strftime('%d.%m.')} – {week_end.strftime('%d.%m.')}",
        })
    return plan


def render_html(athlete, stats, plan, total_activities):
    level, level_color = fitness_level(stats["avg_weekly_km"])
    race_gap_days = (RACE_DATE - TODAY).days

    # Weekly chart data
    chart_bars = ""
    max_km = max((stats["weekly"][i]["dist"] / 1000 for i in range(8) if stats["weekly"][i]["count"] > 0), default=1)
    for i in range(7, -1, -1):
        w = stats["weekly"][i]
        wkm = w["dist"] / 1000
        date = (TODAY - timedelta(weeks=i)).strftime("KW%V")
        pct = (wkm / max(max_km, 1)) * 100
        chart_bars += f"""
        <div class="bar-wrap">
          <div class="bar-label">{wkm:.0f} km</div>
          <div class="bar" style="height:{max(pct,3):.0f}%; background: {'#e74c3c' if i == 0 else '#3498db'}"></div>
          <div class="bar-date">{date}</div>
        </div>"""

    # Recent activities rows
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

    # Training plan rows
    plan_rows = ""
    colors = {"Basisaufbau": "#3498db", "Ausdauer": "#2980b9", "Intensitaet": "#e67e22",
               "Entlastung": "#27ae60", "Spezifisch": "#8e44ad", "Peak": "#e74c3c",
               "Tapering": "#16a085", "Race Week": "#c0392b"}
    for p in plan:
        c = colors.get(p["focus"], "#95a5a6")
        b2b = '<span class="badge">Back-to-Back</span>' if p["b2b"] else ""
        km_str = f"{p['km']} km" if p["km"] else "🏁 RENNEN"
        elev_str = f"{p['elev']} m" if p["elev"] else "–"
        long_str = f"{p['long']} km" if p["long"] else "–"
        plan_rows += f"""
        <tr>
          <td><strong>Woche {p['week']}</strong><br><small>{p['date_range']}</small></td>
          <td><span class="focus-tag" style="background:{c}">{p['focus']}</span> {b2b}</td>
          <td><strong>{km_str}</strong></td>
          <td>{long_str}</td>
          <td>{elev_str}</td>
          <td>{p['note']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Tabernas Desert Ultra 2026 – Race Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1923; color: #ecf0f1; }}
  .hero {{
    background: linear-gradient(135deg, #1a0a00 0%, #3d1500 40%, #8b3a00 70%, #c9601a 100%);
    padding: 60px 40px 40px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }}
  .hero::before {{
    content: '';
    position: absolute; inset: 0;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Ccircle cx='50' cy='50' r='40' fill='none' stroke='rgba(255,255,255,0.03)' stroke-width='1'/%3E%3C/svg%3E") repeat;
  }}
  .hero h1 {{ font-size: 2.8em; font-weight: 900; letter-spacing: -1px; text-shadow: 0 2px 20px rgba(0,0,0,0.5); }}
  .hero .sub {{ font-size: 1.2em; color: #f39c12; margin-top: 8px; font-weight: 300; letter-spacing: 3px; text-transform: uppercase; }}
  .hero .countdown {{ margin-top: 20px; font-size: 3.5em; font-weight: 900; color: #f39c12; }}
  .hero .countdown-label {{ font-size: 0.9em; color: rgba(255,255,255,0.6); letter-spacing: 2px; }}
  .race-info {{ display: flex; gap: 20px; justify-content: center; margin-top: 30px; flex-wrap: wrap; }}
  .race-chip {{
    background: rgba(255,255,255,0.1); backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 30px; padding: 8px 20px; font-size: 0.9em;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
  .section {{ margin-bottom: 50px; }}
  .section-title {{
    font-size: 1.4em; font-weight: 700; margin-bottom: 20px;
    display: flex; align-items: center; gap: 12px;
    border-bottom: 2px solid #2c3e50; padding-bottom: 10px;
  }}
  .section-title .icon {{ font-size: 1.3em; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
  .card {{
    background: #1e2d3d; border-radius: 16px; padding: 24px;
    border: 1px solid #2c3e50;
    transition: transform 0.2s;
  }}
  .card:hover {{ transform: translateY(-3px); }}
  .card .value {{ font-size: 2.2em; font-weight: 900; color: #f39c12; }}
  .card .label {{ font-size: 0.8em; color: #7f8c8d; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }}
  .level-badge {{
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-size: 0.85em; font-weight: 700; color: #fff;
    background: {level_color};
  }}
  .chart-container {{
    background: #1e2d3d; border-radius: 16px; padding: 30px;
    border: 1px solid #2c3e50;
  }}
  .bars {{
    display: flex; align-items: flex-end; gap: 10px; height: 180px;
    margin-top: 20px;
  }}
  .bar-wrap {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; justify-content: flex-end; }}
  .bar {{ width: 100%; border-radius: 6px 6px 0 0; min-height: 4px; transition: height 0.3s; }}
  .bar-label {{ font-size: 0.75em; color: #7f8c8d; }}
  .bar-date {{ font-size: 0.7em; color: #5d6d7e; margin-top: 4px; }}
  .location-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .location-card {{
    background: #1e2d3d; border-radius: 16px; padding: 24px;
    border: 1px solid #2c3e50;
  }}
  .location-card h3 {{ color: #f39c12; margin-bottom: 12px; }}
  .location-card ul {{ list-style: none; }}
  .location-card li {{ padding: 6px 0; border-bottom: 1px solid #2c3e50; font-size: 0.9em; }}
  .location-card li:last-child {{ border: none; }}
  .location-card li strong {{ color: #e74c3c; }}
  .warning-box {{
    background: linear-gradient(135deg, #2c1810, #3d1a00);
    border: 1px solid #e74c3c; border-radius: 12px; padding: 20px;
    margin-top: 20px;
  }}
  .warning-box h4 {{ color: #e74c3c; margin-bottom: 10px; }}
  .warning-box ul {{ list-style: none; }}
  .warning-box li {{ padding: 4px 0; font-size: 0.9em; }}
  .warning-box li::before {{ content: "⚠️ "; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #16213e; padding: 12px 16px; text-align: left; font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px; color: #7f8c8d; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #1e2d3d; font-size: 0.9em; vertical-align: middle; }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .tag {{ background: #2c3e50; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; }}
  .badge {{ background: #8e44ad; padding: 2px 10px; border-radius: 10px; font-size: 0.75em; margin-left: 6px; }}
  .focus-tag {{ padding: 4px 12px; border-radius: 12px; font-size: 0.82em; color: #fff; font-weight: 600; }}
  .table-wrap {{ background: #1e2d3d; border-radius: 16px; overflow: hidden; border: 1px solid #2c3e50; }}
  .gear-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
  .gear-card {{ background: #1e2d3d; border-radius: 12px; padding: 20px; border: 1px solid #2c3e50; }}
  .gear-card h4 {{ color: #3498db; margin-bottom: 10px; }}
  .gear-card li {{ font-size: 0.85em; padding: 3px 0; list-style: none; }}
  .gear-card li::before {{ content: "✓ "; color: #27ae60; }}
  .footer {{ text-align: center; padding: 40px; color: #5d6d7e; font-size: 0.85em; }}
  @media (max-width: 700px) {{
    .location-grid {{ grid-template-columns: 1fr; }}
    .hero h1 {{ font-size: 1.8em; }}
    .hero .countdown {{ font-size: 2.5em; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="sub">Race Preparation Report</div>
  <h1>Tabernas Desert Ultra</h1>
  <div class="sub">130 km · 1.600 hm · 4 Tage · Solo Unsupported · 18.–22. Mai 2026</div>
  <div class="countdown">{race_gap_days}</div>
  <div class="countdown-label">Tage bis zum Start</div>
  <div class="race-info">
    <span class="race-chip">📍 Tabernas, Almería, Spanien</span>
    <span class="race-chip">🌡️ 20–30°C Tageshitze</span>
    <span class="race-chip">☀️ 13+ Sonnenstunden</span>
    <span class="race-chip">🏜️ Europas einzige Wüste</span>
    <span class="race-chip">🎒 {athlete.get('firstname', 'Philipp')} {athlete.get('lastname', 'Jäger')}</span>
  </div>
</div>

<div class="container">

  <!-- AKTUELLE FITNESS -->
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Aktuelle Ausgangssituation</div>
    <div style="margin-bottom:12px">Fitnesslevel: <span class="level-badge">{level}</span></div>
    <div class="cards">
      <div class="card">
        <div class="value">{stats['avg_weekly_km']:.0f} km</div>
        <div class="label">Ø Wochenumfang (8W)</div>
      </div>
      <div class="card">
        <div class="value">{stats['max_long_run']:.0f} km</div>
        <div class="label">Laengster Lauf (8W)</div>
      </div>
      <div class="card">
        <div class="value">{stats['avg_weekly_elev']:.0f} m</div>
        <div class="label">Ø Hoehengewinn/Woche</div>
      </div>
      <div class="card">
        <div class="value">{stats['total_dist']:.0f} km</div>
        <div class="label">Gesamt-Distanz</div>
      </div>
      <div class="card">
        <div class="value">{stats['total_runs']}</div>
        <div class="label">Aktivitaeten Laufen</div>
      </div>
      <div class="card">
        <div class="value">{f"{stats['avg_hr']:.0f}" if stats['avg_hr'] else '–'} bpm</div>
        <div class="label">Ø Herzfrequenz</div>
      </div>
    </div>
  </div>

  <!-- WOCHENUMFANG CHART -->
  <div class="section">
    <div class="section-title"><span class="icon">📈</span> Trainingsumfang letzte 8 Wochen</div>
    <div class="chart-container">
      <div style="color:#7f8c8d; font-size:0.85em">Wochenkilometer (aktuellste Woche in Rot)</div>
      <div class="bars">
        {chart_bars}
      </div>
    </div>
  </div>

  <!-- LOCATION ANALYSE -->
  <div class="section">
    <div class="section-title"><span class="icon">🏜️</span> Location-Analyse: Tabernas Desert</div>
    <div class="location-grid">
      <div class="location-card">
        <h3>Geographie</h3>
        <ul>
          <li>Europas einzige echte Wüste (280 km²)</li>
          <li>Provinz Almería, Andalusien, Spanien</li>
          <li>Höhe: 400–800 m ü. NN</li>
          <li>Badlands-Terrain: Marl, Sandstein, Erosionsschluchten</li>
          <li>Ramblas (Trockenflussbetten) als typische Wegabschnitte</li>
          <li>Sierra Filabres (N) & Sierra Alhamilla (S)</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Klima im Mai</h3>
        <ul>
          <li>🌡️ Tageshitze: <strong>20–30°C</strong> (Spitzen bis 35°C)</li>
          <li>🌙 Naechte: 12–16°C</li>
          <li>☀️ Sonnenstunden: 13+ h/Tag</li>
          <li>💧 Niederschlag: minimal (&lt;20mm/Monat)</li>
          <li>💨 Levante-Wind (trocken, warm)</li>
          <li>🔆 UV-Index: Sehr Hoch bis Extrem</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Renndaten</h3>
        <ul>
          <li>Gesamt-Distanz: <strong>130 km</strong></li>
          <li>Hoehengewinn: <strong>1.600 m</strong></li>
          <li>Etappen: <strong>4 Tage</strong> (~32,5 km/Tag)</li>
          <li>Ø Hoehengewinn/Tag: <strong>~400 m</strong></li>
          <li>Format: Solo Unsupported</li>
          <li>Etappenziel/Nacht: Biwak/Camp</li>
        </ul>
      </div>
      <div class="location-card">
        <h3>Anforderungsprofil</h3>
        <ul>
          <li>Losen, steinigen Untergrund</li>
          <li>Kein Schatten über weite Strecken</li>
          <li>Eigene Wasserversorgung kritisch</li>
          <li>Orientierung in kahlster Landschaft</li>
          <li>Schlafsystem für 12–16°C Naechte</li>
          <li>Gesamtgewicht Rucksack: 7–10 kg</li>
        </ul>
      </div>
    </div>
    <div class="warning-box">
      <h4>Kritische Faktoren</h4>
      <ul>
        <li>Hitzemanagement: Fruehstart (05:00–06:00 Uhr), Siesta 12–15 Uhr, Abendmarsch</li>
        <li>Wasser: Mind. 2–3L Kapazität, Wasserquellen vorher rekognoszieren</li>
        <li>Sonnenschutz: Langarmshirt, Wüstentuch, Sonnenbrille Kategorie 4, SPF50+</li>
        <li>Navigation: GPX-Track auf Garmin/Suunto + Backup auf Smartphone (offline Maps)</li>
        <li>Erste Hilfe: Blasenpflege ab Tag 1 entscheidend, Schlangenbiss-Protokoll kennen</li>
      </ul>
    </div>
  </div>

  <!-- TRAININGSPLAN -->
  <div class="section">
    <div class="section-title"><span class="icon">📅</span> 8-Wochen-Trainingsplan</div>
    <div style="color:#7f8c8d; font-size:0.85em; margin-bottom:16px">
      Personalisiert basierend auf deinen Strava-Daten · Ausgangsbasis: {stats['avg_weekly_km']:.0f} km/Woche · Rennen in {WEEKS_TO_RACE} Wochen
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Woche</th>
            <th>Fokus</th>
            <th>Umfang</th>
            <th>Langer Lauf</th>
            <th>Hoehengewinn</th>
            <th>Schwerpunkt</th>
          </tr>
        </thead>
        <tbody>
          {plan_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- GEAR EMPFEHLUNGEN -->
  <div class="section">
    <div class="section-title"><span class="icon">🎒</span> Ausrüstung (Solo Unsupported)</div>
    <div class="gear-grid">
      <div class="gear-card">
        <h4>Bekleidung</h4>
        <ul>
          <li>Langarm UV-Shirt (UPF 50+)</li>
          <li>Trailshorts mit Einlage</li>
          <li>Wüstentuch / Buff</li>
          <li>Sonnenbrille Kat. 4</li>
          <li>Wüstenkappe mit Nackenschutz</li>
          <li>Gamaschen gegen Sand</li>
          <li>Wärmejacke für Nächte</li>
        </ul>
      </div>
      <div class="gear-card">
        <h4>Schuhe & Füße</h4>
        <ul>
          <li>Trailschuhe mit Sandschutz</li>
          <li>Dünne + dicke Wechselsocken</li>
          <li>Leukoplast / Blasenpflaster</li>
          <li>Schmiercreme (Anti-Chafe)</li>
          <li>Schuhbänder doppelt sichern</li>
        </ul>
      </div>
      <div class="gear-card">
        <h4>Navigation & Sicherheit</h4>
        <ul>
          <li>GPS-Uhr mit GPX-Track</li>
          <li>Smartphone (offline Karte)</li>
          <li>Notfallpfeife</li>
          <li>Survival-Rettungsdecke</li>
          <li>Stirnlampe + Ersatzbatterien</li>
          <li>Notfallkontakt hinterlegen</li>
        </ul>
      </div>
      <div class="gear-card">
        <h4>Ernährung & Wasser</h4>
        <ul>
          <li>Wasserreservoir 2L + 1L Flasche</li>
          <li>Wasserfilter / Tabs (Backup)</li>
          <li>Gels, Riegel: ~300 kcal/h</li>
          <li>Salztabletten (Natrium!)</li>
          <li>Reisnahrung für Abende</li>
          <li>2.500–3.000 kcal/Tag</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- LETZTE AKTIVITÄTEN -->
  <div class="section">
    <div class="section-title"><span class="icon">🏃</span> Letzte 10 Aktivitaeten</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Datum</th><th>Sport</th><th>Name</th><th>Distanz</th><th>Zeit</th><th>Höhe</th><th>Herzfrequenz</th></tr>
        </thead>
        <tbody>
          {activity_rows}
        </tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">
  Generiert am {TODAY.strftime('%d.%m.%Y')} · Basierend auf Strava-Daten von {athlete.get('firstname', '')} {athlete.get('lastname', '')} · Tabernas Desert Ultra 2026
</div>

</body>
</html>"""
    return html


def main():
    if not ACCESS_TOKEN:
        sys.exit("STRAVA_ACCESS_TOKEN nicht gesetzt.")

    print("Verbinde mit Strava...")
    athlete = fetch_athlete()
    print(f"Eingeloggt als: {athlete.get('firstname')} {athlete.get('lastname')}")

    print("Lade Aktivitaeten...")
    activities = fetch_activities()
    print(f"{len(activities)} Aktivitaeten geladen.")

    print("Analysiere Daten...")
    stats = analyze_strava(activities)
    plan = generate_training_plan(stats)

    print("Generiere Report...")
    html = render_html(athlete, stats, plan, len(activities))

    out = os.path.join(os.path.expanduser("~"), "Downloads", "tabernas_race_report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nReport gespeichert: {out}")
    print("Öffne Browser...")
    webbrowser.open(f"file://{out}")
    print("Fertig!")


if __name__ == "__main__":
    main()
