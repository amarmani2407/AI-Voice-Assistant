"""Single local server: serves the UI, handles Google OAuth, and exposes the calendar tools.

Everything runs on one origin (http://localhost:8000), so no CORS is needed.
Tool endpoints require a random token that is generated every time the server starts.
"""
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request
from google_auth_oauthlib.flow import Flow

from calendar_tool import SCOPES, TOKEN_FILE, book_meeting, check_availability

load_dotenv()

# Plain HTTP is only acceptable because this runs on localhost.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

PORT = int(os.getenv("PORT", "8000"))
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"http://localhost:{PORT}/auth/callback")
API_TOKEN = secrets.token_urlsafe(32)

app = Flask(__name__)
_oauth = {}  # holds the in-flight OAuth flow (single local user)


def _flow() -> Flow:
    config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, redirect_uri=REDIRECT_URI)


def _require_token():
    supplied = request.headers.get("X-API-Token", "")
    if not secrets.compare_digest(supplied, API_TOKEN):
        abort(403)


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.route("/")
def index():
    return render_template(
        "index.html",
        api_token=API_TOKEN,
        calendar_ready=os.path.exists(TOKEN_FILE),
    )


@app.route("/auth/login")
def auth_login():
    flow = _flow()
    url, state = flow.authorization_url(prompt="consent", access_type="offline")
    _oauth["flow"], _oauth["state"] = flow, state
    return redirect(url)


@app.route("/auth/callback")
def auth_callback():
    flow = _oauth.pop("flow", None)
    state = _oauth.pop("state", None)
    if flow is None or request.args.get("state") != state:
        abort(400, "Invalid OAuth state. Start again from /auth/login.")
    flow.fetch_token(authorization_response=request.url)
    with open(TOKEN_FILE, "w") as f:
        f.write(flow.credentials.to_json())
    return redirect("/")


@app.route("/api/check_availability", methods=["POST"])
def api_check_availability():
    _require_token()
    data = request.get_json(silent=True) or {}
    return jsonify(result=check_availability(data.get("date", "")))


@app.route("/api/book_meeting", methods=["POST"])
def api_book_meeting():
    _require_token()
    data = request.get_json(silent=True) or {}
    return jsonify(
        result=book_meeting(
            title=data.get("title", "Meeting"),
            date_time_iso=data.get("date_time", ""),
            guest_email=data.get("guest_email", ""),
        )
    )


if __name__ == "__main__":
    print(f"Open http://localhost:{PORT}  (bound to 127.0.0.1 only)")
    app.run(host="127.0.0.1", port=PORT, debug=False)
