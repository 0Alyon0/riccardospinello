"""Google Calendar e Gmail (in sola lettura per Gmail).

Si attiva solo se esiste il token creato con scripts/google_auth.py.
"""
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .. import config

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def disponibile() -> bool:
    return config.GOOGLE_TOKEN_PATH.exists()


def _credenziali() -> Credentials:
    creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        config.GOOGLE_TOKEN_PATH.write_text(creds.to_json())
    return creds


def _servizio(nome: str, versione: str):
    return build(nome, versione, credentials=_credenziali(), cache_discovery=False)


# --- Calendar --------------------------------------------------------------

def eventi(da: datetime, a: datetime, query: str | None = None) -> list[dict]:
    risposta = (
        _servizio("calendar", "v3")
        .events()
        .list(
            calendarId="primary",
            timeMin=da.isoformat(),
            timeMax=a.isoformat(),
            q=query,
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
    )
    return [
        {
            "titolo": e.get("summary", "(senza titolo)"),
            "inizio": e["start"].get("dateTime", e["start"].get("date")),
            "fine": e["end"].get("dateTime", e["end"].get("date")),
            "luogo": e.get("location"),
            "descrizione": (e.get("description") or "")[:500],
        }
        for e in risposta.get("items", [])
    ]


def prossimi_eventi(ore: int = 36) -> list[dict]:
    adesso = datetime.now(config.TIMEZONE)
    return eventi(adesso, adesso + timedelta(hours=ore))


def crea_evento(titolo: str, inizio: datetime, fine: datetime, luogo: str | None = None) -> str:
    corpo = {
        "summary": titolo,
        "start": {"dateTime": inizio.isoformat()},
        "end": {"dateTime": fine.isoformat()},
    }
    if luogo:
        corpo["location"] = luogo
    evento = _servizio("calendar", "v3").events().insert(calendarId="primary", body=corpo).execute()
    return evento.get("htmlLink", "")


# --- Gmail -----------------------------------------------------------------

def cerca_email(query: str, massimo: int = 10) -> list[dict]:
    gmail = _servizio("gmail", "v1")
    risposta = gmail.users().messages().list(userId="me", q=query, maxResults=massimo).execute()
    risultati = []
    for m in risposta.get("messages", []):
        dettaglio = (
            gmail.users()
            .messages()
            .get(userId="me", id=m["id"], format="metadata",
                 metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        intestazioni = {h["name"]: h["value"] for h in dettaglio["payload"]["headers"]}
        risultati.append({
            "id": m["id"],
            "da": intestazioni.get("From"),
            "oggetto": intestazioni.get("Subject"),
            "data": intestazioni.get("Date"),
            "anteprima": dettaglio.get("snippet"),
        })
    return risultati


def leggi_email(email_id: str) -> str:
    """Testo completo di un'email (solo parti text/plain)."""
    import base64

    messaggio = _servizio("gmail", "v1").users().messages().get(
        userId="me", id=email_id, format="full"
    ).execute()

    def estrai(parte) -> str:
        if parte.get("mimeType") == "text/plain" and parte.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(parte["body"]["data"]).decode("utf-8", "replace")
        return "".join(estrai(p) for p in parte.get("parts", []))

    return estrai(messaggio["payload"])[:8000] or messaggio.get("snippet", "")
