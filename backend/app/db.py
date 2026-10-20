"""Tiny SQLite store. Each packet is one JSON blob so the schema never needs migrations.

Every packet has an owner (user_id). All packet functions take the user id and only ever touch that user's rows.
"""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List, Optional

from .schemas import Packet, PacketIn, new_id, now_iso

DB_PATH = Path(os.getenv("CONTEXT_BRIDGE_DB", str(Path(__file__).resolve().parents[1] / "contextbridge.db")))


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


_conn = conn


def init() -> None:
    with closing(conn()) as c, c:
        c.execute("CREATE TABLE IF NOT EXISTS packets (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated TEXT NOT NULL)")
        cols = [r["name"] for r in c.execute("PRAGMA table_info(packets)")]
        if "user_id" not in cols:  # databases made before login existed
            c.execute("ALTER TABLE packets ADD COLUMN user_id TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS packets_user ON packets (user_id, updated)")
        c.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                  "pw_hash TEXT NOT NULL, created TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                  "created TEXT NOT NULL, expires TEXT NOT NULL)")


def user_count() -> int:
    with closing(conn()) as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def claim_orphans(uid: str) -> int:
    """Give packets saved before login existed to the first account, so no old work is lost."""
    with closing(conn()) as c, c:
        return c.execute("UPDATE packets SET user_id = ? WHERE user_id IS NULL", (uid,)).rowcount


def _row(r: sqlite3.Row) -> Packet:
    return Packet(**json.loads(r["data"]))


def list_packets(uid: str) -> List[Packet]:
    with closing(conn()) as c:
        return [_row(r) for r in c.execute("SELECT * FROM packets WHERE user_id = ? ORDER BY updated DESC", (uid,))]


def get(uid: str, pid: str) -> Optional[Packet]:
    with closing(conn()) as c:
        r = c.execute("SELECT * FROM packets WHERE id = ? AND user_id = ?", (pid, uid)).fetchone()
        return _row(r) if r else None


def create(uid: str, p: PacketIn) -> Packet:
    t = now_iso()
    pkt = Packet(id=new_id(), created=t, updated=t, **p.model_dump())
    with closing(conn()) as c, c:
        c.execute("INSERT INTO packets (id, data, updated, user_id) VALUES (?, ?, ?, ?)",
                  (pkt.id, pkt.model_dump_json(), pkt.updated, uid))
    return pkt


def update(uid: str, pid: str, p: PacketIn) -> Optional[Packet]:
    old = get(uid, pid)
    if not old:
        return None
    pkt = Packet(id=pid, created=old.created, updated=now_iso(), **p.model_dump())
    with closing(conn()) as c, c:
        c.execute("UPDATE packets SET data = ?, updated = ? WHERE id = ? AND user_id = ?",
                  (pkt.model_dump_json(), pkt.updated, pid, uid))
    return pkt


def delete(uid: str, pid: str) -> bool:
    with closing(conn()) as c, c:
        return c.execute("DELETE FROM packets WHERE id = ? AND user_id = ?", (pid, uid)).rowcount > 0


def count(uid: str) -> int:
    with closing(conn()) as c:
        return c.execute("SELECT COUNT(*) FROM packets WHERE user_id = ?", (uid,)).fetchone()[0]
