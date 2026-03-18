import os
import requests
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


if __name__ == "__main__":
    if not ACCESS_TOKEN:
        raise SystemExit("STRAVA_ACCESS_TOKEN not set. Copy .env.example to .env and fill in your credentials.")

    profile = get_athlete_profile()
    print("=== Strava Profile ===")
    print_profile(profile)

    stats = get_athlete_stats(profile["id"])
    print_stats(stats)
