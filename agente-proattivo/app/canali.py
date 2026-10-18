"""Sceglie su quale chat scrivere: WhatsApp o Telegram.

Le risposte tornano sul canale da cui è arrivata la domanda. I messaggi proattivi vanno
sull'ultimo canale che hai usato (o su CANALE_PREDEFINITO se non hai ancora scritto).
"""
from . import config, memoria, telegram, whatsapp

CANALI = {"whatsapp": whatsapp.invia, "telegram": telegram.invia}


def ricorda_canale(canale: str) -> None:
    memoria.imposta("ultimo_canale", canale)


def invia(testo: str, canale: str | None = None) -> None:
    canale = canale or memoria.leggi("ultimo_canale") or config.CANALE_PREDEFINITO
    CANALI[canale](testo)
