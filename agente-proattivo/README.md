# Agente proattivo su WhatsApp e Telegram

Un assistente personale che vive nelle tue chat WhatsApp e Telegram, costruito con Claude.
La memoria è una sola: quello che gli dici su Telegram lo sa anche su WhatsApp.
Si ispira all'idea di Instinct, ma il codice è tutto nuovo e scritto da zero.

- **Memoria a lungo termine**: salva da solo i fatti importanti (persone, clienti, viaggi,
  preferenze) e li ha sempre davanti. Lo storico completo delle chat resta ricercabile.
- **Proattivo**: ogni giorno ti manda un briefing al mattino e ogni 2 ore controlla agenda, email
  e progetti. Ti scrive solo se ha qualcosa di utile, con un massimo di messaggi al giorno.
- **Collegato**: Google Calendar (lettura e creazione di eventi), Gmail (sola lettura), ricerca web.
- **Promemoria**: "ricordami domani alle 9 di chiamare Marco" e lui te lo scrive.
- **Messaggi vocali**: su WhatsApp e Telegram puoi parlargli invece di scrivere.

## Come funziona

```
WhatsApp ──► Twilio ──► /whatsapp ─┐
Telegram ──► /telegram o polling ───┴─► Claude + strumenti ──► risposta sulla stessa chat
                                                   │
                         memoria SQLite ◄──────────┤  (fatti, chat, promemoria)
                         Calendar / Gmail ◄────────┤
                         ricerca web ◄─────────────┘

Scheduler ─┬─ ogni minuto: invia i promemoria scaduti
           ├─ 07:45: briefing del mattino
           └─ ogni 2 ore (8-21): "c'è qualcosa che vale la pena dirgli?" → scrive o resta zitto
```

| File | Cosa fa |
|---|---|
| `app/agente.py` | personalità, loop di Claude con gli strumenti, logica del controllo proattivo |
| `app/memoria.py` | database SQLite: fatti, messaggi (con ricerca full-text), promemoria |
| `app/strumenti.py` | strumenti che l'agente può usare |
| `app/proattivo.py` | scheduler: promemoria, briefing, controlli periodici |
| `app/whatsapp.py` | invio dei messaggi e verifica della firma Twilio |
| `app/telegram.py` | bot Telegram: invio, webhook o polling |
| `app/voce.py` | trascrizione dei vocali (Whisper locale o servizio esterno) |
| `app/canali.py` | sceglie la chat: le risposte tornano dove hai scritto, i messaggi proattivi vanno sull'ultima chat usata |
| `app/integrazioni/google.py` | Calendar e Gmail |

## Avvio rapido

```bash
cd agente-proattivo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # inserisci ANTHROPIC_API_KEY e gli altri valori
```

**1. Prova dal terminale** (non serve WhatsApp):

```bash
python -m scripts.chat_locale
python -m scripts.chat_locale --proattivo   # simula un controllo proattivo
```

**2. Collega Google (facoltativo, ma è qui che diventa utile):** segui le istruzioni in
`scripts/google_auth.py`, poi `python -m scripts.google_auth`.

**3. Collega WhatsApp con la sandbox di Twilio:**
1. Crea un account su twilio.com e apri *Messaging → Try it out → Send a WhatsApp message*.
2. Dal tuo telefono manda il codice `join ...` al numero della sandbox.
3. Avvia il server: `uvicorn app.main:app --port 8000`
4. Esponilo su internet (per le prove: `ngrok http 8000`) e incolla `https://.../whatsapp`
   nel campo *When a message comes in* della sandbox. Lo stesso URL va in `PUBLIC_WEBHOOK_URL`.

**4. Collega Telegram (più semplice di WhatsApp, è gratis):**
1. Su Telegram apri @BotFather, scrivi `/newbot` e copia il token in `TELEGRAM_BOT_TOKEN`.
2. Avvia il server (`uvicorn app.main:app --port 8000`) e scrivi `/start` al tuo bot:
   ti risponde con il tuo chat id. Mettilo in `TELEGRAM_OWNER_CHAT_ID` e riavvia.
3. Fatto. Senza altre impostazioni il bot usa il *polling*, quindi funziona anche dal tuo
   computer senza ngrok. In produzione puoi usare il webhook: imposta `TELEGRAM_WEBHOOK_URL`
   (`https://.../telegram`) e una stringa casuale in `TELEGRAM_WEBHOOK_SECRET`.

Puoi usare solo Telegram, solo WhatsApp o entrambi. I messaggi proattivi arrivano sull'ultima
chat in cui hai scritto (all'inizio su `CANALE_PREDEFINITO`).

Per l'uso vero e proprio di WhatsApp: un numero WhatsApp Business approvato su Twilio e il server su un
hosting sempre acceso (Railway, Render, Fly.io, una VPS). Lo scheduler gira dentro il server,
quindi il server deve restare acceso.

## Messaggi vocali

I vocali vengono trascritti e passati all'agente come testo, su WhatsApp e su Telegram.
Hai due modi per trascriverli:

- **Whisper sul tuo server** (predefinito): gratis e l'audio non esce dal server. La prima volta
  scarica il modello (`small` pesa circa 500 MB e vuole circa 1 GB di RAM). Su un hosting
  piccolo usa `WHISPER_MODELLO=base`, più leggero ma meno preciso.
- **Servizio esterno**: imposta `TRASCRIZIONE_API_URL` e `TRASCRIZIONE_API_KEY`. Funziona con
  qualunque servizio compatibile con l'API di trascrizione di OpenAI, per esempio OpenAI o Groq
  (veloce ed economico). Esempio in `.env.example`.

I vocali più lunghi di `DURATA_MASSIMA_VOCALE` secondi (10 minuti) vengono rifiutati. Se la
trascrizione non riesce, l'agente ti chiede di ripetere o di scrivere.

## Sicurezza

- Risponde **solo** al numero in `OWNER_WHATSAPP` e alla chat in `TELEGRAM_OWNER_CHAT_ID`.
  Verifica la firma di ogni richiesta Twilio e il segreto del webhook Telegram.
- Gmail è in sola lettura. Per creare eventi in calendario chiede conferma.
- Non salvare mai password di Instagram/LinkedIn nell'agente: se vuoi farlo agire sui social,
  usa le API ufficiali con token revocabili.
- `.env` e `data/` (database e token Google) sono esclusi da git. Questo repository pubblica il
  sito: non mettere mai lì le chiavi.

## Personalizzare

- **Carattere e regole**: `PERSONALITA` e `ISTRUZIONI_PROATTIVE` in `app/agente.py`.
- **Frequenza e orari**: variabili `PROACTIVE_*` e `MORNING_BRIEF_*` nel `.env`.
- **Nuovi collegamenti** (Slack, Drive, Notion...): aggiungi la definizione in `app/strumenti.py`
  e il caso in `esegui()`.
