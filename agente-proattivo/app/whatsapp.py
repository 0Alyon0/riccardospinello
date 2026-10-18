"""Invio e verifica dei messaggi WhatsApp tramite Twilio."""
import requests
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from . import config

LIMITE_CARATTERI = 1500  # Twilio accetta al massimo 1600 caratteri per messaggio

_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN) if config.TWILIO_ACCOUNT_SID else None
_validatore = RequestValidator(config.TWILIO_AUTH_TOKEN)


def _spezza(testo: str) -> list[str]:
    parti, corrente = [], ""
    for paragrafo in testo.split("\n"):
        if len(corrente) + len(paragrafo) + 1 > LIMITE_CARATTERI and corrente:
            parti.append(corrente)
            corrente = ""
        corrente = f"{corrente}\n{paragrafo}" if corrente else paragrafo
        while len(corrente) > LIMITE_CARATTERI:
            parti.append(corrente[:LIMITE_CARATTERI])
            corrente = corrente[LIMITE_CARATTERI:]
    if corrente:
        parti.append(corrente)
    return parti


def invia(testo: str, a: str | None = None) -> None:
    destinatario = a or config.OWNER_WHATSAPP
    if _client is None:
        print(f"[WhatsApp simulato -> {destinatario}]\n{testo}\n")
        return
    for parte in _spezza(testo):
        _client.messages.create(from_=config.TWILIO_WHATSAPP_FROM, to=destinatario, body=parte)


def firma_valida(url: str, parametri: dict, firma: str) -> bool:
    return _validatore.validate(url, parametri, firma)


def vocale_in_arrivo(form: dict) -> str | None:
    """URL del primo allegato audio di un messaggio Twilio, se c'è."""
    for i in range(int(form.get("NumMedia") or 0)):
        if (form.get(f"MediaContentType{i}") or "").startswith("audio/"):
            return form.get(f"MediaUrl{i}")
    return None


def scarica_media(url: str) -> tuple[bytes, str]:
    """Scarica un allegato; restituisce (contenuto, nome del file)."""
    # requests toglie le credenziali quando Twilio reindirizza al suo archivio file
    risposta = requests.get(url, auth=(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN), timeout=60)
    risposta.raise_for_status()
    estensione = risposta.headers.get("Content-Type", "audio/ogg").split("/")[-1].split(";")[0]
    return risposta.content, f"vocale.{estensione}"
