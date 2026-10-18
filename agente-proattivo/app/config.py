"""Configurazione letta dalle variabili d'ambiente (file .env)."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# Claude
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("CLAUDE_EFFORT", "medium")

# Identità dell'agente e del proprietario
AGENT_NAME = os.getenv("AGENT_NAME", "Fiuto")
OWNER_NAME = os.getenv("OWNER_NAME", "Riccardo")
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Europe/Rome"))

# WhatsApp via Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
# Unico numero autorizzato a parlare con l'agente, es. whatsapp:+393331234567
OWNER_WHATSAPP = os.getenv("OWNER_WHATSAPP", "")
# URL pubblico del webhook, serve per verificare la firma Twilio
PUBLIC_WEBHOOK_URL = os.getenv("PUBLIC_WEBHOOK_URL", "")

# Telegram (bot creato con @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Unica chat autorizzata: il tuo id Telegram (il bot te lo dice se gli scrivi /start)
TELEGRAM_OWNER_CHAT_ID = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
# Se vuoto si usa il polling, che non richiede un URL pubblico
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

# Dove arrivano i messaggi proattivi prima che tu abbia mai scritto: whatsapp | telegram
CANALE_PREDEFINITO = os.getenv("CANALE_PREDEFINITO", "whatsapp")

# Memoria
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "memoria.db"))
HISTORY_TURNS = _int("HISTORY_TURNS", 40)

# Google (Calendar + Gmail), opzionale
GOOGLE_TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", BASE_DIR / "data" / "google_token.json"))
GOOGLE_CLIENT_SECRET_PATH = Path(
    os.getenv("GOOGLE_CLIENT_SECRET_PATH", BASE_DIR / "data" / "google_client_secret.json")
)

# Proattività
PROACTIVE_EVERY_MINUTES = _int("PROACTIVE_EVERY_MINUTES", 120)
PROACTIVE_START_HOUR = _int("PROACTIVE_START_HOUR", 8)
PROACTIVE_END_HOUR = _int("PROACTIVE_END_HOUR", 21)
PROACTIVE_MAX_PER_DAY = _int("PROACTIVE_MAX_PER_DAY", 4)
MORNING_BRIEF_HOUR = _int("MORNING_BRIEF_HOUR", 7)
MORNING_BRIEF_MINUTE = _int("MORNING_BRIEF_MINUTE", 45)
