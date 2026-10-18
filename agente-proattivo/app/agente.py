"""Il cervello: loop di Claude con strumenti, memoria e personalità."""
import logging
from datetime import datetime

import anthropic

from . import config, memoria, strumenti

log = logging.getLogger(__name__)
client = anthropic.Anthropic()

MAX_GIRI_STRUMENTI = 15

PERSONALITA = f"""Sei {config.AGENT_NAME}, l'assistente personale di {config.OWNER_NAME}. Vivi nella sua chat \
WhatsApp e lo aiuti nel lavoro e nella vita di tutti i giorni.

Come lavori:
- Scrivi come in una chat WhatsApp: messaggi brevi, diretti, in italiano, niente titoli markdown. \
Puoi usare *grassetto* e liste semplici. Al massimo un'emoji quando aiuta.
- Hai una memoria a lungo termine. Il blocco "COSA SAI" qui sotto contiene i fatti che hai salvato: \
usali sempre, senza farti ripetere le cose.
- Ogni volta che emerge un'informazione duratura (persone, clienti, progetti, preferenze, viaggi, \
scadenze, abitudini, obiettivi) salvala subito con lo strumento `ricorda`, senza annunciarlo. \
Se un fatto cambia, aggiornalo con `aggiorna_ricordo` invece di duplicarlo.
- Se ti serve qualcosa detto in passato che non è in "COSA SAI", cercalo con `cerca_nelle_conversazioni`.
- Per orari, viaggi, appuntamenti e prenotazioni controlla calendario ed email prima di rispondere \
(es. biglietti del treno, conferme di hotel). Non inventare mai orari o indirizzi: se non li trovi, dillo.
- Usa la ricerca web per notizie, idee, dati aggiornati.
- Prima di azioni con effetti esterni (creare eventi) chiedi conferma, salvo richiesta esplicita.
- Quando la richiesta richiede un po' di lavoro, fallo tutto e porta il risultato, non un piano.
"""

ISTRUZIONI_PROATTIVE = """Questo è un CONTROLLO PROATTIVO: nessuno ti ha scritto. Decidi se vale la pena \
scrivere tu a {owner} adesso.

Scrivigli solo se hai qualcosa di davvero utile e tempestivo, per esempio:
- un impegno imminente con informazioni pratiche (orario del treno, indirizzo dell'alloggio, cosa portare);
- un'email importante che richiede attenzione o una risposta;
- una scadenza o un conflitto in agenda;
- un'idea, una notizia o uno spunto concreto legato ai suoi progetti e obiettivi (cerca sul web se serve);
- un follow-up su qualcosa di cui avete parlato e che è rimasto in sospeso.

Non ripetere cose già dette nella conversazione recente. Niente saluti generici o messaggi di riempimento.
Puoi usare gli strumenti per verificare e approfondire prima di decidere.

Se non c'è niente di valore, rispondi esattamente: NIENTE
Altrimenti rispondi solo con il testo del messaggio WhatsApp da inviare."""


def _system() -> list[dict]:
    adesso = datetime.now(config.TIMEZONE)
    return [
        # parte stabile, in cache tra una richiesta e l'altra
        {"type": "text", "text": PERSONALITA, "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": (
                f"COSA SAI di {config.OWNER_NAME}:\n{memoria.fatti_come_testo()}\n\n"
                f"Adesso è {adesso.strftime('%A %d %B %Y, %H:%M')} ({config.TIMEZONE.key}). "
                f"ISO: {adesso.isoformat(timespec='minutes')}"
            ),
        },
    ]


def _chiama(messaggi: list[dict]):
    return client.beta.messages.create(
        model=config.MODEL,
        max_tokens=16000,
        system=_system(),
        messages=messaggi,
        tools=strumenti.elenco(),
        thinking={"type": "adaptive"},
        output_config={"effort": config.EFFORT},
        # se un filtro di sicurezza rifiuta, l'API riprova su un altro modello
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )


def esegui(messaggi: list[dict]) -> str:
    """Fa girare Claude con gli strumenti finché non produce la risposta finale."""
    for _ in range(MAX_GIRI_STRUMENTI):
        risposta = _chiama(messaggi)

        if risposta.stop_reason == "refusal":
            return "Su questo non posso aiutarti, scusa."

        messaggi.append({"role": "assistant", "content": risposta.content})

        if risposta.stop_reason == "pause_turn":
            continue  # una ricerca web lunga: rimanda e lascia continuare
        if risposta.stop_reason != "tool_use":
            return "".join(b.text for b in risposta.content if b.type == "text").strip()

        risultati = []
        for blocco in risposta.content:
            if blocco.type != "tool_use":
                continue
            try:
                esito = strumenti.esegui(blocco.name, blocco.input)
                risultati.append({"type": "tool_result", "tool_use_id": blocco.id, "content": esito})
            except Exception as errore:  # l'errore torna a Claude, che può adattarsi
                log.exception("Errore nello strumento %s", blocco.name)
                risultati.append({
                    "type": "tool_result",
                    "tool_use_id": blocco.id,
                    "content": f"Errore: {errore}",
                    "is_error": True,
                })
        messaggi.append({"role": "user", "content": risultati})

    return "Ci sto mettendo troppo: riprova con una richiesta più semplice."


def rispondi(testo_utente: str) -> str:
    """Risposta a un messaggio WhatsApp del proprietario."""
    memoria.salva_messaggio("user", testo_utente)
    risposta = esegui(memoria.storico_recente(config.HISTORY_TURNS))
    if risposta:
        memoria.salva_messaggio("assistant", risposta)
    return risposta


def pensa_proattivamente(contesto: str) -> str | None:
    """Controllo proattivo: restituisce un messaggio da inviare, o None."""
    recenti = memoria.storico_recente(20)
    trascrizione = "\n".join(
        f"{'Lui' if m['role'] == 'user' else 'Tu'}: {m['content']}" for m in recenti
    ) or "(nessuna conversazione recente)"

    richiesta = (
        ISTRUZIONI_PROATTIVE.format(owner=config.OWNER_NAME)
        + f"\n\n--- CONVERSAZIONE RECENTE ---\n{trascrizione}"
        + f"\n\n--- CONTESTO ---\n{contesto}"
    )
    testo = esegui([{"role": "user", "content": richiesta}])
    if not testo or testo.strip().upper().startswith("NIENTE"):
        return None
    memoria.salva_messaggio("assistant", testo, proattivo=True)
    return testo
