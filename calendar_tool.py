"""Google Calendar helpers used by the voice agent's tools."""
import datetime as dt
import os
import re
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_FILE = "token.json"
MEETING_MINUTES = 30
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _tz() -> ZoneInfo:
    return ZoneInfo(os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata"))


def _calendar_id() -> str:
    return os.getenv("HOST_CALENDAR_ID", "primary")


def _service():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError("Calendar not authorized yet. Open /auth/login first.")
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _parse(iso: str) -> dt.datetime:
    """Parse an ISO 8601 string; assume the default timezone if none is given."""
    d = dt.datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=_tz())


def _events_between(service, start: dt.datetime, end: dt.datetime) -> list:
    result = service.events().list(
        calendarId=_calendar_id(),
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def check_availability(date_iso: str) -> str:
    """List busy slots for the whole day that contains date_iso."""
    try:
        service = _service()
        day = _parse(date_iso).astimezone(_tz())
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + dt.timedelta(days=1)
        events = _events_between(service, start, end)

        label = start.strftime("%A, %d %B %Y")
        if not events:
            return f"The calendar is completely free on {label}."

        lines = []
        for e in events:
            s = e["start"].get("dateTime", e["start"].get("date"))
            en = e["end"].get("dateTime", e["end"].get("date"))
            lines.append(f"- Busy from {s} to {en}")
        return f"Busy slots on {label}:\n" + "\n".join(lines)
    except Exception as exc:  # report to the model, don't crash the server
        return f"Could not check availability: {exc}"


def book_meeting(title: str, date_time_iso: str, guest_email: str = "") -> str:
    """Create a 30-minute event, refusing if it overlaps an existing one."""
    try:
        service = _service()
        start = _parse(date_time_iso)
        end = start + dt.timedelta(minutes=MEETING_MINUTES)

        # Server-side double-booking guard (does not rely on the model remembering).
        clashes = _events_between(service, start, end)
        if clashes:
            return "That slot is already taken. Please ask for another time."

        body = {
            "summary": (title or "Meeting")[:200],
            "description": "Booked by the voice assistant.",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        if guest_email and EMAIL_RE.match(guest_email):
            body["attendees"] = [{"email": guest_email}]

        # sendUpdates="none": a misheard email address should not email a stranger.
        created = service.events().insert(
            calendarId=_calendar_id(), body=body, sendUpdates="none"
        ).execute()
        return f"Booked '{body['summary']}' at {start.strftime('%A %d %B, %I:%M %p')}. Link: {created.get('htmlLink')}"
    except Exception as exc:
        return f"Could not book the meeting: {exc}"
