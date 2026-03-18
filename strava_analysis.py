import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

STRAVA_API_BASE = "https://www.strava.com/api/v3"
ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")


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


def meters_to_km(m):
    return m / 1000.0


def seconds_to_hms(s):
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s"


def pace_min_per_km(distance_m, moving_time_s):
    if distance_m == 0:
        return None
    km = distance_m / 1000.0
    min_per_km = (moving_time_s / 60.0) / km
    m = int(min_per_km)
    s = int((min_per_km - m) * 60)
    return f"{m}:{s:02d} min/km"


def speed_kmh(distance_m, moving_time_s):
    if moving_time_s == 0:
        return 0
    return (distance_m / 1000.0) / (moving_time_s / 3600.0)


def analyze(activities):
    by_type = defaultdict(list)
    for a in activities:
        sport = a.get("sport_type") or a.get("type", "Other")
        by_type[sport].append(a)

    monthly = defaultdict(lambda: defaultdict(lambda: {"count": 0, "distance": 0, "time": 0}))
    for a in activities:
        date = datetime.fromisoformat(a["start_date_local"].replace("Z", "+00:00"))
        key = date.strftime("%Y-%m")
        sport = a.get("sport_type") or a.get("type", "Other")
        monthly[key][sport]["count"] += 1
        monthly[key][sport]["distance"] += a.get("distance", 0)
        monthly[key][sport]["time"] += a.get("moving_time", 0)

    return by_type, monthly


def print_separator(char="=", width=60):
    print(char * width)


def print_section(title):
    print_separator()
    print(f"  {title}")
    print_separator()


def print_overall_summary(activities):
    print_section("GESAMTUEBERSICHT")
    if not activities:
        print("Keine Aktivitaeten gefunden.")
        return

    total_dist = sum(a.get("distance", 0) for a in activities)
    total_time = sum(a.get("moving_time", 0) for a in activities)
    total_elev = sum(a.get("total_elevation_gain", 0) for a in activities)

    dates = [datetime.fromisoformat(a["start_date_local"].replace("Z", "+00:00")) for a in activities]
    oldest = min(dates)
    newest = max(dates)

    print(f"  Aktivitaeten gesamt : {len(activities)}")
    print(f"  Distanz gesamt      : {meters_to_km(total_dist):.1f} km")
    print(f"  Bewegungszeit       : {seconds_to_hms(total_time)}")
    print(f"  Hoehengewinn        : {total_elev:.0f} m")
    print(f"  Zeitraum            : {oldest.strftime('%d.%m.%Y')} – {newest.strftime('%d.%m.%Y')}")


def print_by_sport(by_type):
    print_section("NACH SPORTART")
    for sport, acts in sorted(by_type.items(), key=lambda x: -len(x[1])):
        dist = sum(a.get("distance", 0) for a in acts)
        time = sum(a.get("moving_time", 0) for a in acts)
        elev = sum(a.get("total_elevation_gain", 0) for a in acts)
        print(f"\n  [{sport}]  ({len(acts)} Aktivitaeten)")
        print(f"    Distanz     : {meters_to_km(dist):.1f} km")
        print(f"    Zeit        : {seconds_to_hms(time)}")
        print(f"    Hoehengewinn: {elev:.0f} m")
        if dist > 0:
            avg_pace = pace_min_per_km(dist / len(acts), time / len(acts))
            avg_speed = speed_kmh(dist, time)
            if sport.lower() in ("run", "trailrun", "virtualrun"):
                print(f"    Ø Pace      : {avg_pace}")
            else:
                print(f"    Ø Tempo     : {avg_speed:.1f} km/h")


def print_recent_activities(activities, n=10):
    print_section(f"LETZTE {n} AKTIVITAETEN")
    recent = sorted(activities, key=lambda a: a["start_date_local"], reverse=True)[:n]
    for a in recent:
        date = datetime.fromisoformat(a["start_date_local"].replace("Z", "+00:00"))
        sport = a.get("sport_type") or a.get("type", "?")
        dist = meters_to_km(a.get("distance", 0))
        time = seconds_to_hms(a.get("moving_time", 0))
        name = a.get("name", "Unbekannt")
        print(f"  {date.strftime('%d.%m.%Y')}  {sport:<12}  {dist:6.1f} km  {time:<12}  {name}")


def print_monthly_trend(monthly):
    print_section("MONATLICHE ENTWICKLUNG (letzte 12 Monate)")
    sorted_months = sorted(monthly.keys())[-12:]
    for month in sorted_months:
        sports = monthly[month]
        total_dist = sum(v["distance"] for v in sports.values())
        total_count = sum(v["count"] for v in sports.values())
        bar_len = int(meters_to_km(total_dist) / 5)
        bar = "#" * min(bar_len, 40)
        print(f"  {month}  {bar:<40}  {meters_to_km(total_dist):6.1f} km  ({total_count} Akt.)")


def print_personal_bests(by_type):
    print_section("PERSOENLICHE BESTLEISTUNGEN")
    for sport in ("Run", "Ride", "Swim", "TrailRun", "VirtualRide"):
        acts = by_type.get(sport, [])
        if not acts:
            continue
        print(f"\n  [{sport}]")
        longest = max(acts, key=lambda a: a.get("distance", 0))
        fastest = min(
            [a for a in acts if a.get("distance", 0) > 0 and a.get("moving_time", 0) > 0],
            key=lambda a: a.get("moving_time", 0) / a.get("distance", 1),
            default=None,
        )
        highest = max(acts, key=lambda a: a.get("total_elevation_gain", 0))

        print(f"    Laengste Aktivitaet : {meters_to_km(longest.get('distance', 0)):.1f} km  ({longest.get('name', '')})")
        if fastest and sport.lower() in ("run", "trailrun", "virtualrun"):
            print(f"    Schnellste Pace     : {pace_min_per_km(fastest.get('distance', 0), fastest.get('moving_time', 0))}  ({fastest.get('name', '')})")
        elif fastest:
            print(f"    Hoechstes Tempo     : {speed_kmh(fastest.get('distance', 0), fastest.get('moving_time', 0)):.1f} km/h  ({fastest.get('name', '')})")
        print(f"    Groesster Hoehengewinn: {highest.get('total_elevation_gain', 0):.0f} m  ({highest.get('name', '')})")


def print_heartrate_analysis(by_type):
    print_section("HERZFREQUENZ-ANALYSE")
    found = False
    for sport, acts in by_type.items():
        hr_acts = [a for a in acts if a.get("average_heartrate")]
        if not hr_acts:
            continue
        found = True
        avg_hr = sum(a["average_heartrate"] for a in hr_acts) / len(hr_acts)
        max_hr = max(a.get("max_heartrate", 0) for a in hr_acts)
        print(f"  [{sport}]  Ø {avg_hr:.0f} bpm  |  Max {max_hr:.0f} bpm  ({len(hr_acts)} Aktivitaeten mit HF-Daten)")
    if not found:
        print("  Keine Herzfrequenzdaten verfuegbar.")


def main():
    if not ACCESS_TOKEN:
        sys.exit("STRAVA_ACCESS_TOKEN nicht gesetzt. Bitte .env.example zu .env kopieren und Token eintragen.")

    print("\nVerbinde mit Strava...")
    athlete = fetch_athlete()
    print(f"Eingeloggt als: {athlete.get('firstname')} {athlete.get('lastname')} (@{athlete.get('username')})\n")

    print("Lade Aktivitaeten (das kann einen Moment dauern)...")
    activities = fetch_activities()
    print(f"{len(activities)} Aktivitaeten geladen.\n")

    if not activities:
        print("Keine Aktivitaeten gefunden.")
        return

    by_type, monthly = analyze(activities)

    print_overall_summary(activities)
    print()
    print_by_sport(by_type)
    print()
    print_monthly_trend(monthly)
    print()
    print_personal_bests(by_type)
    print()
    print_heartrate_analysis(by_type)
    print()
    print_recent_activities(activities)
    print()
    print_separator()
    print("  Analyse abgeschlossen.")
    print_separator()


if __name__ == "__main__":
    main()
