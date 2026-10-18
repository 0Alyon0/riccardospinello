"""Server web: riceve i messaggi WhatsApp da Twilio e avvia lo scheduler proattivo.

Avvio: uvicorn app.main:app --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import Response

from . import agente, config, memoria, proattivo, whatsapp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TWIML_VUOTO = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@asynccontextmanager
async def lifespan(_: FastAPI):
    memoria.init()
    scheduler = proattivo.avvia()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


def _gestisci(testo: str) -> None:
    with proattivo.blocco_conversazione:
        try:
            risposta = agente.rispondi(testo)
        except Exception:
            log.exception("Errore nel generare la risposta")
            risposta = "Ho avuto un problema tecnico, riprova tra poco."
    if risposta:
        whatsapp.invia(risposta)


@app.post("/whatsapp")
async def webhook_whatsapp(request: Request, tasks: BackgroundTasks):
    form = dict(await request.form())

    if config.TWILIO_AUTH_TOKEN:
        url = config.PUBLIC_WEBHOOK_URL or str(request.url)
        if not whatsapp.firma_valida(url, form, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(status_code=403, detail="Firma Twilio non valida")

    # l'agente risponde solo al proprietario
    if form.get("From") != config.OWNER_WHATSAPP:
        log.warning("Messaggio ignorato da %s", form.get("From"))
        return Response(TWIML_VUOTO, media_type="application/xml")

    testo = (form.get("Body") or "").strip()
    if testo:
        # Twilio vuole una risposta entro 15 secondi: il lavoro va in background
        tasks.add_task(_gestisci, testo)
    return Response(TWIML_VUOTO, media_type="application/xml")


@app.post("/proattivo")
async def forza_controllo(tasks: BackgroundTasks):
    """Utile per i test: lancia subito un controllo proattivo."""
    tasks.add_task(proattivo.controllo_proattivo, "controllo manuale")
    return {"ok": True}


@app.get("/")
async def stato():
    return {"agente": config.AGENT_NAME, "fatti_in_memoria": len(memoria.tutti_i_fatti())}
