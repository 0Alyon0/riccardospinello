"""Trascrizione dei messaggi vocali.

Per impostazione predefinita usa Whisper in locale (faster-whisper): gratis e l'audio non
esce dal server. Se imposti TRASCRIZIONE_API_URL usa invece un servizio esterno compatibile
con l'API di OpenAI (OpenAI o Groq), utile su hosting con poca memoria.
"""
import json
import logging
import tempfile
import threading
import urllib.request
import uuid

from . import config

log = logging.getLogger(__name__)

_modello = None
_blocco_modello = threading.Lock()


def _locale(audio: bytes, nome_file: str) -> str:
    global _modello
    with _blocco_modello:
        if _modello is None:
            from faster_whisper import WhisperModel  # import lento: solo se serve

            log.info("Carico il modello Whisper '%s'...", config.WHISPER_MODELLO)
            _modello = WhisperModel(config.WHISPER_MODELLO, device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(suffix="-" + nome_file) as file:
            file.write(audio)
            file.flush()
            segmenti, _ = _modello.transcribe(file.name, language=config.TRASCRIZIONE_LINGUA,
                                              vad_filter=True)
            return " ".join(s.text.strip() for s in segmenti).strip()


def _remota(audio: bytes, nome_file: str) -> str:
    confine = uuid.uuid4().hex
    campi = {"model": config.TRASCRIZIONE_API_MODELLO, "language": config.TRASCRIZIONE_LINGUA}
    corpo = b"".join(
        f'--{confine}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valore}\r\n'.encode()
        for nome, valore in campi.items()
    )
    corpo += (
        f'--{confine}\r\nContent-Disposition: form-data; name="file"; filename="{nome_file}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + audio + f"\r\n--{confine}--\r\n".encode()

    richiesta = urllib.request.Request(
        config.TRASCRIZIONE_API_URL,
        data=corpo,
        headers={
            "Authorization": f"Bearer {config.TRASCRIZIONE_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={confine}",
        },
    )
    with urllib.request.urlopen(richiesta, timeout=120) as risposta:
        return json.loads(risposta.read())["text"].strip()


def trascrivi(audio: bytes, nome_file: str = "vocale.ogg") -> str:
    if config.TRASCRIZIONE_API_URL:
        return _remota(audio, nome_file)
    return _locale(audio, nome_file)
