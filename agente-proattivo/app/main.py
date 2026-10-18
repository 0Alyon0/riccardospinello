"""Server web: riceve i messaggi da WhatsApp (Twilio) e Telegram e avvia lo scheduler proattivo.

Avvio: uvicorn app.main:app --port 8000
"""
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import Response

from . import agente, canali, config, memoria, proattivo, telegram, voce, whatsapp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TWIML_VUOTO = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@asynccontextmanager
async def lifespan(_: FastAPI):
    memoria.init()
    scheduler = proattivo.avvia()
    ferma_polling = None
    if telegram.attivo():
        if config.TELEGRAM_WEBHOOK_URL:
            telegram.configura_webhook()
        else:
            ferma_polling = telegram.avvia_polling(_gestisci_telegram)
    yield
    if ferma_polling:
        ferma_polling.set()
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


def _trascrivi(scarica) -> str | None:
    """Scarica e trascrive un vocale; restituisce il testo da passare all'agente."""
    try:
        audio, nome_file = scarica()
        trascrizione = voce.trascrivi(audio, nome_file)
    except Exception:
        log.exception("Trascrizione del vocale fallita")
        return None
    return f"🎤 (messaggio vocale) {trascrizione}" if trascrizione else None


def _gestisci(testo: str | None, canale: str, scarica_vocale=None) -> None:
    canali.ricorda_canale(canale)
    if canale == "telegram":
        telegram.sta_scrivendo()
    if scarica_vocale:
        testo = _trascrivi(scarica_vocale)
        if not testo:
            canali.invia("Non sono riuscito a capire il vocale, puoi ripetere o scrivermelo?", canale)
            return
    with proattivo.blocco_conversazione:
        try:
            risposta = agente.rispondi(testo)
        except Exception:
            log.exception("Errore nel generare la risposta")
            risposta = "Ho avuto un problema tecnico, riprova tra poco."
    if risposta:
        canali.invia(risposta, canale)


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

    # Twilio vuole una risposta entro 15 secondi: il lavoro va in background
    url_vocale = whatsapp.vocale_in_arrivo(form)
    testo = (form.get("Body") or "").strip()
    if url_vocale:
        tasks.add_task(_gestisci, None, "whatsapp", lambda: whatsapp.scarica_media(url_vocale))
    elif testo:
        tasks.add_task(_gestisci, testo, "whatsapp")
    return Response(TWIML_VUOTO, media_type="application/xml")


@app.post("/telegram")
async def webhook_telegram(request: Request, tasks: BackgroundTasks):
    segreto = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not config.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(segreto, config.TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Segreto Telegram non valido")

    messaggio = telegram.estrai_messaggio(await request.json())
    if messaggio:
        tasks.add_task(_gestisci_telegram, messaggio)
    return {"ok": True}


def _gestisci_telegram(messaggio: dict) -> None:
    if "vocale" not in messaggio:
        _gestisci(messaggio["testo"], "telegram")
    elif messaggio["durata"] > config.DURATA_MASSIMA_VOCALE:
        telegram.invia("Il vocale è troppo lungo per me, prova a dividerlo in parti più corte.")
    else:
        _gestisci(None, "telegram", lambda: telegram.scarica_file(messaggio["vocale"]))


@app.post("/proattivo")
async def forza_controllo(tasks: BackgroundTasks):
    """Utile per i test: lancia subito un controllo proattivo."""
    tasks.add_task(proattivo.controllo_proattivo, "controllo manuale")
    return {"ok": True}


@app.get("/")
async def stato():
    return {"agente": config.AGENT_NAME, "fatti_in_memoria": len(memoria.tutti_i_fatti())}
