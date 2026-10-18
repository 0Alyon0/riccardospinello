"""Invio e ricezione dei messaggi Telegram tramite la Bot API.

Due modi di ricevere i messaggi:
- webhook (POST /telegram), se TELEGRAM_WEBHOOK_URL è impostato;
- polling, altrimenti: non serve un URL pubblico, comodo anche in locale.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from . import config

log = logging.getLogger(__name__)

LIMITE_CARATTERI = 4000  # Telegram accetta al massimo 4096 caratteri per messaggio


def attivo() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN)


def _api(metodo: str, dati: dict, timeout: float = 30) -> dict:
    richiesta = urllib.request.Request(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{metodo}",
        data=json.dumps(dati).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        return json.loads(risposta.read())


def invia(testo: str, chat_id: str | None = None) -> None:
    destinatario = chat_id or config.TELEGRAM_OWNER_CHAT_ID
    if not attivo():
        print(f"[Telegram simulato -> {destinatario}]\n{testo}\n")
        return
    for inizio in range(0, len(testo), LIMITE_CARATTERI):
        _api("sendMessage", {"chat_id": destinatario, "text": testo[inizio:inizio + LIMITE_CARATTERI]})


def sta_scrivendo() -> None:
    """Mostra "sta scrivendo..." mentre l'agente lavora."""
    if attivo():
        try:
            _api("sendChatAction", {"chat_id": config.TELEGRAM_OWNER_CHAT_ID, "action": "typing"})
        except Exception:
            pass


def estrai_messaggio(update: dict) -> dict | None:
    """Messaggio del proprietario: {"testo": ...} oppure {"vocale": file_id, "durata": secondi}."""
    messaggio = update.get("message") or {}
    chat_id = str(messaggio.get("chat", {}).get("id", ""))
    testo = (messaggio.get("text") or "").strip()
    audio = messaggio.get("voice") or messaggio.get("audio")
    if not testo and not audio:
        return None
    if chat_id != config.TELEGRAM_OWNER_CHAT_ID:
        log.warning("Messaggio Telegram ignorato dalla chat %s", chat_id)
        # aiuta a configurare TELEGRAM_OWNER_CHAT_ID la prima volta
        if not config.TELEGRAM_OWNER_CHAT_ID and testo == "/start":
            invia(f"Il tuo chat id è {chat_id}: mettilo in TELEGRAM_OWNER_CHAT_ID.", chat_id)
        return None
    if testo == "/start":
        return None
    if audio:
        return {"vocale": audio["file_id"], "durata": audio.get("duration", 0)}
    return {"testo": testo}


def scarica_file(file_id: str) -> tuple[bytes, str]:
    """Scarica un file inviato al bot; restituisce (contenuto, nome del file)."""
    percorso = _api("getFile", {"file_id": file_id})["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{percorso}"
    with urllib.request.urlopen(url, timeout=60) as risposta:
        return risposta.read(), percorso.rsplit("/", 1)[-1]


def configura_webhook() -> None:
    _api("setWebhook", {
        "url": config.TELEGRAM_WEBHOOK_URL,
        "secret_token": config.TELEGRAM_WEBHOOK_SECRET,
        "allowed_updates": ["message"],
    })


def avvia_polling(gestisci) -> threading.Event:
    """Legge i messaggi in un thread separato; `gestisci(messaggio)` viene chiamata per ognuno."""
    ferma = threading.Event()

    def ciclo() -> None:
        _api("deleteWebhook", {})
        offset = 0
        while not ferma.is_set():
            try:
                risposta = _api("getUpdates", {"offset": offset, "timeout": 25,
                                               "allowed_updates": ["message"]}, timeout=35)
            except (urllib.error.URLError, TimeoutError):
                ferma.wait(5)
                continue
            for update in risposta.get("result", []):
                offset = update["update_id"] + 1
                messaggio = estrai_messaggio(update)
                if messaggio:
                    threading.Thread(target=gestisci, args=(messaggio,), daemon=True).start()

    threading.Thread(target=ciclo, daemon=True, name="telegram-polling").start()
    return ferma
