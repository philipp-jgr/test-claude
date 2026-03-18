import os
import requests
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

STRAVA_API_BASE = "https://www.strava.com/api/v3"
ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")


def get_headers():
    return {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def get_athlete_profile():
    response = requests.get(f"{STRAVA_API_BASE}/athlete", headers=get_headers())
    response.raise_for_status()
    return response.json()


def get_athlete_stats(athlete_id):
    response = requests.get(
        f"{STRAVA_API_BASE}/athletes/{athlete_id}/stats", headers=get_headers()
    )
    response.raise_for_status()
    return response.json()


def get_activities(per_page=200):
    """Fetch all activities (paginated)."""
    activities = []
    page = 1
    while True:
        response = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers=get_headers(),
            params={"per_page": per_page, "page": page},
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        activities.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return activities


def print_profile(profile):
    print(f"Name:     {profile.get('firstname')} {profile.get('lastname')}")
    print(f"Username: {profile.get('username')}")
    print(f"City:     {profile.get('city')}, {profile.get('country')}")
    print(f"Follower: {profile.get('follower_count')}")
    print(f"Friends:  {profile.get('friend_count')}")
    print(f"Profile:  https://www.strava.com/athletes/{profile.get('id')}")


def print_stats(stats):
    ytd = stats.get("ytd_run_totals", {})
    all_time = stats.get("all_run_totals", {})
    print("\n--- YTD Run Stats ---")
    print(f"  Distance: {ytd.get('distance', 0) / 1000:.1f} km")
    print(f"  Runs:     {ytd.get('count', 0)}")
    print(f"  Time:     {ytd.get('moving_time', 0) // 3600}h {(ytd.get('moving_time', 0) % 3600) // 60}m")
    print("\n--- All-Time Run Stats ---")
    print(f"  Distance: {all_time.get('distance', 0) / 1000:.1f} km")
    print(f"  Runs:     {all_time.get('count', 0)}")


def analyze_activities(activities):
    if not activities:
        print("\nKeine Aktivitäten gefunden.")
        return

    # Group by sport type
    by_type = defaultdict(list)
    for a in activities:
        by_type[a.get("sport_type", a.get("type", "Unknown"))].append(a)

    print(f"\n=== Aktivitäten-Übersicht ({len(activities)} gesamt) ===")
    for sport, acts in sorted(by_type.items(), key=lambda x: -len(x[1])):
        total_dist = sum(a.get("distance", 0) for a in acts) / 1000
        total_time = sum(a.get("moving_time", 0) for a in acts)
        print(f"\n  {sport}: {len(acts)} Aktivitäten, {total_dist:.1f} km, "
              f"{total_time // 3600}h {(total_time % 3600) // 60}m")

    # Monthly breakdown for current year
    current_year = datetime.now(timezone.utc).year
    monthly = defaultdict(lambda: {"count": 0, "distance": 0.0})
    for a in activities:
        date_str = a.get("start_date_local", "")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.year == current_year:
            key = dt.strftime("%Y-%m")
            monthly[key]["count"] += 1
            monthly[key]["distance"] += a.get("distance", 0) / 1000

    if monthly:
        print(f"\n--- Monatliche Aktivitäten {current_year} ---")
        for month in sorted(monthly.keys()):
            m = monthly[month]
            bar = "#" * min(m["count"], 30)
            print(f"  {month}: {bar} {m['count']} Aktivitäten, {m['distance']:.1f} km")

    # Top 5 longest activities
    runs = [a for a in activities if a.get("sport_type", a.get("type", "")) == "Run"]
    if runs:
        top5 = sorted(runs, key=lambda a: a.get("distance", 0), reverse=True)[:5]
        print("\n--- Top 5 längste Läufe ---")
        for i, a in enumerate(top5, 1):
            dist = a.get("distance", 0) / 1000
            pace_sec = (a.get("moving_time", 0) / (a.get("distance", 1) / 1000)) if a.get("distance") else 0
            pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d} /km"
            date = a.get("start_date_local", "")[:10]
            print(f"  {i}. {a.get('name', 'Unbekannt')} — {dist:.1f} km @ {pace} ({date})")

    # PRs / best efforts summary
    pr_count = sum(
        len(a.get("best_efforts", [])) for a in activities
    )
    kudos_total = sum(a.get("kudos_count", 0) for a in activities)
    print(f"\n--- Sonstiges ---")
    print(f"  Kudos erhalten: {kudos_total}")
    print(f"  Beste Leistungen (best efforts): {pr_count}")


if __name__ == "__main__":
    if not ACCESS_TOKEN:
        raise SystemExit("STRAVA_ACCESS_TOKEN not set. Copy .env.example to .env and fill in your credentials.")

    profile = get_athlete_profile()
    print("=== Strava Profil ===")
    print_profile(profile)

    stats = get_athlete_stats(profile["id"])
    print_stats(stats)

    print("\nLade alle Aktivitäten...")
    activities = get_activities()
    analyze_activities(activities)
