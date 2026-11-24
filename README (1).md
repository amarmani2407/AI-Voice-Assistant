# Voice Booking Assistant (Gemini Live + Google Calendar)

Talk to an AI by voice. It checks your Google Calendar and books a 30-minute meeting.

**How it works:** the browser streams your microphone to the Gemini Live API over a WebSocket.
When Gemini wants to check or book, the browser calls this local Flask server, which talks to Google Calendar.
One server, one port (8000), bound to 127.0.0.1 only.

## Setup

1. Create a virtual environment and install packages
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # macOS / Linux
   pip install -r requirements.txt
   ```
2. Google Cloud Console: enable the **Google Calendar API**, then create an **OAuth client ID** (type: Web application).
   - Authorized redirect URI: `http://localhost:8000/auth/callback`
   - OAuth consent screen: add your own Google account under **Test users**.
3. Copy `.env.example` to `.env` and fill in the client ID and secret.
4. Get a Gemini API key from Google AI Studio.

## Run

```bash
python app.py
```

1. Open http://localhost:8000 in Chrome.
2. Click **Authorize it** once to connect Google Calendar (creates `token.json`).
3. Paste your Gemini API key, click **Connect**, tap the mic, and say:
   "Check if I'm free tomorrow afternoon and book a demo at 3 PM."

## Safety notes

- Tool endpoints need a random token created at each server start, so other websites cannot call them.
- Your Gemini key stays in the browser tab; it is never sent to the Flask server.
- Bookings are refused server-side if the slot overlaps an existing event.
- Invites are not emailed automatically (`sendUpdates="none"`), so a misheard address cannot email a stranger.
- Never commit `.env` or `token.json`. If they leak, revoke access at myaccount.google.com/permissions.

## Troubleshooting

- Connection closes right away: check the API key, and check that `MODEL` in `templates/index.html` is a current Gemini Live model name.
- No mic: use `localhost` (not an IP address) so Chrome allows microphone access.
