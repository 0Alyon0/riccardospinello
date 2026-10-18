"""La parte proattiva: promemoria, briefing del mattino e controlli periodici."""
import json
import logging
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from . import agente, canali, config, memoria
from .integrazioni import google

log = logging.getLogger(__name__)

# impedisce che una risposta e un controllo proattivo scrivano in contemporanea
blocco_conversazione = threading.Lock()


def _contesto() -> str:
    """Raccoglie ciò che l'agente deve guardare quando decide se scrivere."""
    parti = []
    if google.disponibile():
        try:
            parti.append("Prossimi eventi (36 ore):\n"
                         + json.dumps(google.prossimi_eventi(36), ensure_ascii=False))
            parti.append("Email non lette degli ultimi 2 giorni:\n" + json.dumps(
                google.cerca_email("is:unread newer_than:2d -category:promotions -category:social", 15),
                ensure_ascii=False,
            ))
        except Exception:
            log.exception("Impossibile leggere Google")
            parti.append("(Google Calendar/Gmail momentaneamente non disponibili)")
    else:
        parti.append("(Google Calendar/Gmail non collegati)")

    attivi = memoria.promemoria_attivi()
    if attivi:
        parti.append("Promemoria già programmati:\n"
                     + "\n".join(f"- {p['quando']}: {p['testo']}" for p in attivi))
    parti.append(f"Messaggi proattivi già inviati oggi: {memoria.proattivi_oggi()} "
                 f"(massimo {config.PROACTIVE_MAX_PER_DAY}).")
    return "\n\n".join(parti)


def invia_promemoria_scaduti() -> None:
    for p in memoria.promemoria_scaduti():
        testo = f"⏰ {p['testo']}"
        canali.invia(testo)
        memoria.salva_messaggio("assistant", testo, proattivo=True)
        memoria.segna_promemoria_inviato(p["id"])


def controllo_proattivo(motivo: str = "controllo periodico") -> None:
    ora = datetime.now(config.TIMEZONE).hour
    if not (config.PROACTIVE_START_HOUR <= ora < config.PROACTIVE_END_HOUR):
        return
    if memoria.proattivi_oggi() >= config.PROACTIVE_MAX_PER_DAY:
        return
    with blocco_conversazione:
        try:
            messaggio = agente.pensa_proattivamente(f"Motivo: {motivo}\n\n{_contesto()}")
        except Exception:
            log.exception("Controllo proattivo fallito")
            return
    if messaggio:
        canali.invia(messaggio)


def briefing_mattutino() -> None:
    with blocco_conversazione:
        try:
            messaggio = agente.pensa_proattivamente(
                "Motivo: BRIEFING DEL MATTINO. Prepara un buongiorno utile: impegni di oggi con "
                "orari e spostamenti, email che richiedono azione, una cosa da non dimenticare e, "
                "se pertinente, uno spunto per i suoi progetti. Breve. In questo caso scrivi "
                "sempre, a meno che la giornata sia davvero vuota.\n\n" + _contesto()
            )
        except Exception:
            log.exception("Briefing mattutino fallito")
            return
    if messaggio:
        canali.invia(messaggio)


def avvia() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(invia_promemoria_scaduti, "interval", minutes=1, id="promemoria")
    scheduler.add_job(controllo_proattivo, "interval", minutes=config.PROACTIVE_EVERY_MINUTES,
                      id="proattivo", max_instances=1, coalesce=True)
    scheduler.add_job(briefing_mattutino, "cron", hour=config.MORNING_BRIEF_HOUR,
                      minute=config.MORNING_BRIEF_MINUTE, id="briefing")
    scheduler.start()
    return scheduler
