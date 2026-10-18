"""Invio e verifica dei messaggi WhatsApp tramite Twilio."""
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
