"""Prova l'agente dal terminale, senza WhatsApp.

    python -m scripts.chat_locale            # chat
    python -m scripts.chat_locale --proattivo  # simula un controllo proattivo
"""
import sys

from app import agente, memoria, proattivo


def main() -> None:
    memoria.init()
    if "--proattivo" in sys.argv:
        messaggio = agente.pensa_proattivamente(proattivo._contesto())
        print(messaggio or "(l'agente ha deciso di non scrivere)")
        return
    print("Scrivi un messaggio (Ctrl+C per uscire)")
    while True:
        testo = input("\nTu: ").strip()
        if testo:
            print(f"\nAgente: {agente.rispondi(testo)}")


if __name__ == "__main__":
    main()
