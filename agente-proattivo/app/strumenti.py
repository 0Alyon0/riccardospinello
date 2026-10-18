"""Strumenti che Claude può usare: memoria, promemoria, Calendar, Gmail, ricerca web."""
import json
from datetime import datetime

from . import config, memoria
from .integrazioni import google

STRUMENTI_MEMORIA = [
    {
        "name": "ricorda",
        "description": (
            "Salva nella memoria a lungo termine un fatto duraturo sul proprietario: persone, "
            "progetti, clienti, preferenze, abitudini, viaggi, scadenze, obiettivi. Usalo ogni "
            "volta che emerge un'informazione che potrebbe servire in futuro, senza chiedere il "
            "permesso. Un fatto per chiamata, scritto in modo autosufficiente (con date assolute)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "es. persona, progetto, preferenza, viaggio, lavoro, salute, obiettivo",
                },
                "contenuto": {"type": "string"},
            },
            "required": ["categoria", "contenuto"],
        },
    },
    {
        "name": "aggiorna_ricordo",
        "description": "Corregge o aggiorna un fatto già memorizzato (usa l'id tra parentesi quadre).",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "contenuto": {"type": "string"}},
            "required": ["id", "contenuto"],
        },
    },
    {
        "name": "dimentica",
        "description": "Elimina un fatto non più vero o che il proprietario chiede di dimenticare.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    },
    {
        "name": "cerca_nelle_conversazioni",
        "description": (
            "Cerca nello storico completo delle conversazioni passate (anche mesi fa). "
            "Usa parole chiave semplici."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "crea_promemoria",
        "description": "Programma un messaggio WhatsApp da inviare al proprietario a una data/ora precisa.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quando": {
                    "type": "string",
                    "description": "Data e ora ISO 8601 con fuso, es. 2026-10-20T15:30:00+02:00",
                },
                "testo": {"type": "string"},
            },
            "required": ["quando", "testo"],
        },
    },
]

STRUMENTI_GOOGLE = [
    {
        "name": "calendario_eventi",
        "description": "Legge gli eventi di Google Calendar in un intervallo, con filtro testuale opzionale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "da": {"type": "string", "description": "ISO 8601 con fuso"},
                "a": {"type": "string", "description": "ISO 8601 con fuso"},
                "query": {"type": "string", "description": "testo da cercare (opzionale)"},
            },
            "required": ["da", "a"],
        },
    },
    {
        "name": "calendario_crea_evento",
        "description": "Crea un evento su Google Calendar. Chiedi conferma prima, salvo richiesta esplicita.",
        "input_schema": {
            "type": "object",
            "properties": {
                "titolo": {"type": "string"},
                "inizio": {"type": "string", "description": "ISO 8601 con fuso"},
                "fine": {"type": "string", "description": "ISO 8601 con fuso"},
                "luogo": {"type": "string"},
            },
            "required": ["titolo", "inizio", "fine"],
        },
    },
    {
        "name": "gmail_cerca",
        "description": (
            "Cerca email con la sintassi di Gmail (es. 'treno from:trenitalia newer_than:30d', "
            "'is:unread', 'subject:prenotazione Torino'). Restituisce mittente, oggetto, anteprima."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "gmail_leggi",
        "description": "Legge il testo completo di un'email dato il suo id (ottenuto da gmail_cerca).",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
]

# Strumenti eseguiti dai server Anthropic: nessun codice da scrivere
STRUMENTI_SERVER = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
]


def elenco() -> list[dict]:
    strumenti = list(STRUMENTI_MEMORIA)
    if google.disponibile():
        strumenti += STRUMENTI_GOOGLE
    return strumenti + STRUMENTI_SERVER


def _data(valore: str) -> datetime:
    d = datetime.fromisoformat(valore)
    return d if d.tzinfo else d.replace(tzinfo=config.TIMEZONE)


def esegui(nome: str, dati: dict) -> str:
    """Esegue uno strumento e restituisce il risultato come testo."""
    if nome == "ricorda":
        return f"Memorizzato con id {memoria.salva_fatto(dati['categoria'], dati['contenuto'])}."
    if nome == "aggiorna_ricordo":
        return "Aggiornato." if memoria.aggiorna_fatto(dati["id"], dati["contenuto"]) else "Id non trovato."
    if nome == "dimentica":
        return "Eliminato." if memoria.elimina_fatto(dati["id"]) else "Id non trovato."
    if nome == "cerca_nelle_conversazioni":
        righe = memoria.cerca_messaggi(dati["query"])
        if not righe:
            return "Nessun risultato."
        return "\n".join(f"[{r['creato']}] {r['ruolo']}: {r['testo'][:400]}" for r in righe)
    if nome == "crea_promemoria":
        quando = _data(dati["quando"])
        pid = memoria.crea_promemoria(quando, dati["testo"])
        return f"Promemoria {pid} programmato per {quando.isoformat()}."
    if nome == "calendario_eventi":
        return json.dumps(
            google.eventi(_data(dati["da"]), _data(dati["a"]), dati.get("query")), ensure_ascii=False
        )
    if nome == "calendario_crea_evento":
        link = google.crea_evento(
            dati["titolo"], _data(dati["inizio"]), _data(dati["fine"]), dati.get("luogo")
        )
        return f"Evento creato: {link}"
    if nome == "gmail_cerca":
        return json.dumps(google.cerca_email(dati["query"]), ensure_ascii=False)
    if nome == "gmail_leggi":
        return google.leggi_email(dati["id"])
    raise ValueError(f"Strumento sconosciuto: {nome}")
