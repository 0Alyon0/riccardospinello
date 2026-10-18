"""Memoria a lungo termine su SQLite.

Tre livelli:
- fatti: cose durature sul proprietario (persone, progetti, preferenze, viaggi...).
  Sono sempre inserite nel prompt, quindi l'agente "non dimentica".
- messaggi: lo storico completo della chat, ricercabile con FTS5.
- promemoria: messaggi da inviare a un orario preciso.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS fatti (
    id INTEGER PRIMARY KEY,
    categoria TEXT NOT NULL,
    contenuto TEXT NOT NULL,
    creato TEXT NOT NULL,
    aggiornato TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messaggi (
    id INTEGER PRIMARY KEY,
    ruolo TEXT NOT NULL,          -- user | assistant
    testo TEXT NOT NULL,
    proattivo INTEGER NOT NULL DEFAULT 0,
    creato TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS messaggi_fts USING fts5(
    testo, content='messaggi', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS messaggi_ai AFTER INSERT ON messaggi BEGIN
    INSERT INTO messaggi_fts(rowid, testo) VALUES (new.id, new.testo);
END;
CREATE TABLE IF NOT EXISTS promemoria (
    id INTEGER PRIMARY KEY,
    quando TEXT NOT NULL,         -- ISO 8601 con fuso orario
    testo TEXT NOT NULL,
    inviato INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(config.TIMEZONE).isoformat(timespec="seconds")


@contextmanager
def _db():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with _db() as conn:
        conn.executescript(SCHEMA)


# --- Fatti -----------------------------------------------------------------

def salva_fatto(categoria: str, contenuto: str) -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO fatti (categoria, contenuto, creato, aggiornato) VALUES (?, ?, ?, ?)",
            (categoria, contenuto, _now(), _now()),
        )
        return cur.lastrowid


def aggiorna_fatto(fatto_id: int, contenuto: str) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "UPDATE fatti SET contenuto = ?, aggiornato = ? WHERE id = ?",
            (contenuto, _now(), fatto_id),
        )
        return cur.rowcount > 0


def elimina_fatto(fatto_id: int) -> bool:
    with _db() as conn:
        return conn.execute("DELETE FROM fatti WHERE id = ?", (fatto_id,)).rowcount > 0


def tutti_i_fatti() -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute("SELECT * FROM fatti ORDER BY categoria, id").fetchall()


def fatti_come_testo() -> str:
    righe = [f"[{f['id']}] ({f['categoria']}) {f['contenuto']}" for f in tutti_i_fatti()]
    return "\n".join(righe) if righe else "(ancora nessun fatto memorizzato)"


# --- Messaggi --------------------------------------------------------------

def salva_messaggio(ruolo: str, testo: str, proattivo: bool = False) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO messaggi (ruolo, testo, proattivo, creato) VALUES (?, ?, ?, ?)",
            (ruolo, testo, int(proattivo), _now()),
        )


def storico_recente(limite: int) -> list[dict]:
    """Ultimi messaggi in formato Messages API, alternando user/assistant."""
    with _db() as conn:
        righe = conn.execute(
            "SELECT ruolo, testo, creato FROM messaggi ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    messaggi: list[dict] = []
    for r in reversed(righe):
        # data solo sui messaggi utente, così l'agente non la imita nelle risposte
        testo = r["testo"]
        if r["ruolo"] == "user":
            testo = f"[{r['creato'][:16].replace('T', ' ')}] {testo}"
        # unisce messaggi consecutivi dello stesso ruolo (es. due messaggi proattivi di fila)
        if messaggi and messaggi[-1]["role"] == r["ruolo"]:
            messaggi[-1]["content"] += "\n\n" + testo
        else:
            messaggi.append({"role": r["ruolo"], "content": testo})
    # l'API richiede che la conversazione inizi con un messaggio utente
    while messaggi and messaggi[0]["role"] != "user":
        messaggi.pop(0)
    return messaggi


def cerca_messaggi(query: str, limite: int = 10) -> list[sqlite3.Row]:
    with _db() as conn:
        try:
            return conn.execute(
                """SELECT m.ruolo, m.testo, m.creato FROM messaggi_fts f
                   JOIN messaggi m ON m.id = f.rowid
                   WHERE messaggi_fts MATCH ? ORDER BY rank LIMIT ?""",
                (query, limite),
            ).fetchall()
        except sqlite3.OperationalError:
            # query FTS non valida: ripiega su LIKE
            return conn.execute(
                "SELECT ruolo, testo, creato FROM messaggi WHERE testo LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{query}%", limite),
            ).fetchall()


def proattivi_oggi() -> int:
    oggi = datetime.now(config.TIMEZONE).date().isoformat()
    with _db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM messaggi WHERE proattivo = 1 AND creato LIKE ?", (f"{oggi}%",)
        ).fetchone()[0]


# --- Promemoria ------------------------------------------------------------

def crea_promemoria(quando: datetime, testo: str) -> int:
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO promemoria (quando, testo) VALUES (?, ?)",
            (quando.isoformat(timespec="seconds"), testo),
        )
        return cur.lastrowid


def promemoria_scaduti() -> list[sqlite3.Row]:
    with _db() as conn:
        righe = conn.execute("SELECT * FROM promemoria WHERE inviato = 0").fetchall()
    adesso = datetime.now(config.TIMEZONE)
    return [r for r in righe if datetime.fromisoformat(r["quando"]) <= adesso]


def promemoria_attivi() -> list[sqlite3.Row]:
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM promemoria WHERE inviato = 0 ORDER BY quando"
        ).fetchall()


def segna_promemoria_inviato(promemoria_id: int) -> None:
    with _db() as conn:
        conn.execute("UPDATE promemoria SET inviato = 1 WHERE id = ?", (promemoria_id,))


# --- Impostazioni ----------------------------------------------------------

def imposta(chiave: str, valore: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO impostazioni (chiave, valore) VALUES (?, ?) "
            "ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore",
            (chiave, valore),
        )


def leggi(chiave: str) -> str | None:
    with _db() as conn:
        riga = conn.execute("SELECT valore FROM impostazioni WHERE chiave = ?", (chiave,)).fetchone()
    return riga["valore"] if riga else None
