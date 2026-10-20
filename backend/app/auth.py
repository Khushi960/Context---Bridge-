"""User accounts and login sessions.

- Passwords are never stored. Only a salted PBKDF2-SHA256 hash (Python standard library, no extra packages).
- Logging in gives the browser a random session token in an HttpOnly cookie. The database keeps only a SHA-256
  hash of that token, so a copied database file cannot be used to log in as anyone.
- Every packet belongs to one user. One user can never read, change or delete another user's packets.
- Repeated wrong passwords for the same username are slowed down (a short lockout).
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Cookie, HTTPException

from . import db
from .schemas import User

COOKIE = "cb_session"
SESSION_DAYS = 30
ITERATIONS = 200_000
USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8

# Lockout after too many wrong passwords: MAX_FAILS within WINDOW seconds locks that username for WINDOW seconds.
MAX_FAILS = 5
WINDOW = 15 * 60
_fails: Dict[str, List[float]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (ITERATIONS, salt.hex(), dk.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, want = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), want)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user(r: sqlite3.Row) -> User:
    return User(id=r["id"], username=r["username"], created=r["created"])


# ---------- accounts ----------

def register(username: str, password: str) -> User:
    username = username.strip()
    if not USERNAME.match(username):
        raise HTTPException(400, "Username must be 3 to 32 characters: letters, numbers, dot, dash or underscore.")
    if len(password) < MIN_PASSWORD:
        raise HTTPException(400, "Password must be at least %d characters." % MIN_PASSWORD)
    if password.lower() == username.lower():
        raise HTTPException(400, "Password cannot be the same as the username.")
    uid, t = secrets.token_hex(6), _now().isoformat()
    try:
        with closing(db.conn()) as c, c:
            c.execute("INSERT INTO users (id, username, pw_hash, created) VALUES (?, ?, ?, ?)",
                      (uid, username, hash_password(password), t))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That username is already taken.")
    return User(id=uid, username=username, created=t)


def authenticate(username: str, password: str) -> User:
    key = username.strip().lower()
    now = time.time()
    recent = [x for x in _fails.get(key, []) if now - x < WINDOW]
    _fails[key] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, "Too many wrong passwords. Try again in 15 minutes.")
    with closing(db.conn()) as c:
        r = c.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)).fetchone()
    # Same message for "no such user" and "wrong password", so nobody can probe which usernames exist.
    if not r or not verify_password(password, r["pw_hash"]):
        recent.append(now)
        raise HTTPException(401, "Wrong username or password.")
    _fails.pop(key, None)
    return _user(r)


# ---------- sessions ----------

def start_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    with closing(db.conn()) as c, c:
        c.execute("DELETE FROM sessions WHERE expires < ?", (now.isoformat(),))
        c.execute("INSERT INTO sessions (token_hash, user_id, created, expires) VALUES (?, ?, ?, ?)",
                  (_token_hash(token), user.id, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat()))
    return token


def end_session(token: Optional[str]) -> None:
    if token:
        with closing(db.conn()) as c, c:
            c.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


def user_for_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    with closing(db.conn()) as c:
        r = c.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires > ?",
            (_token_hash(token), _now().isoformat())).fetchone()
    return _user(r) if r else None


def current_user(cb_session: Optional[str] = Cookie(default=None)) -> User:
    """FastAPI dependency: the logged-in user, or 401."""
    u = user_for_token(cb_session)
    if not u:
        raise HTTPException(401, "Please log in.")
    return u
