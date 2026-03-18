"""
Strava OAuth Flow – holt einen Access Token mit activity:read_all Berechtigung
und speichert ihn in der .env Datei.
"""
import http.server
import os
import threading
import urllib.parse
import webbrowser

import requests

CLIENT_ID = "213446"
CLIENT_SECRET = "9b56faed7fb43b7eecb9dee740714fb854d9cc02"
REDIRECT_URI = "http://localhost:8765"
SCOPE = "activity:read_all,read"

auth_code = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>Erfolgreich! Du kannst dieses Fenster schliessen.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Fehler: Kein Code erhalten.")

    def log_message(self, *args):
        pass


def main():
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&approval_prompt=force"
        f"&scope={SCOPE}"
    )

    server = http.server.HTTPServer(("localhost", 8765), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Browser wird geoeffnet – bitte Strava-Zugriff bestaetigen...")
    webbrowser.open(auth_url)

    thread.join(timeout=120)

    if not auth_code:
        print("Fehler: Kein Code erhalten (Timeout oder Abbruch).")
        return

    print("Code erhalten, tausche gegen Access Token...")
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
        },
    )
    r.raise_for_status()
    token_data = r.json()
    access_token = token_data["access_token"]
    athlete = token_data.get("athlete", {})

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w") as f:
        f.write(f"STRAVA_ACCESS_TOKEN={access_token}\n")
        f.write(f"STRAVA_CLIENT_SECRET={CLIENT_SECRET}\n")

    print(f"\nErfolgreich eingeloggt als: {athlete.get('firstname')} {athlete.get('lastname')}")
    print(f"Access Token gespeichert in: {env_path}")
    print("\nStarte jetzt die Analyse mit:")
    print("  python3 strava_analysis.py")


if __name__ == "__main__":
    main()
