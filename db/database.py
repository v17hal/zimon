"""SQLite database layer for ZIMON — users, protocols, experiments, camera assignments."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Optional


_DB_PATH = os.path.join(os.path.expanduser("~"), ".zimon", "zimon.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables and seed default admin if first run."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS camera_assignments (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL UNIQUE,
                label    TEXT NOT NULL DEFAULT 'unassigned',
                role     TEXT NOT NULL DEFAULT 'unassigned'
            );

            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT NOT NULL UNIQUE,
                email     TEXT NOT NULL UNIQUE,
                password  TEXT NOT NULL,
                role      TEXT NOT NULL DEFAULT 'researcher',
                created   REAL NOT NULL,
                active    INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS protocols (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT,
                steps       TEXT NOT NULL DEFAULT '[]',
                category    TEXT NOT NULL DEFAULT 'both',
                created_by  INTEGER,
                created     REAL NOT NULL,
                updated     REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                exp_id        TEXT NOT NULL UNIQUE,
                name          TEXT NOT NULL,
                protocol_id   INTEGER,
                protocol_name TEXT,
                status        TEXT NOT NULL DEFAULT 'running',
                mode          TEXT,
                camera        TEXT,
                duration_sec  REAL,
                storage_path  TEXT,
                events_log    TEXT DEFAULT '[]',
                created_by    INTEGER,
                started       REAL NOT NULL,
                finished      REAL
            );
        """)
        # Seed admin user on first run
        row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if not row:
            _insert_user(conn, "admin", "admin@zimon.lab", "zimon2024", "admin")


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _insert_user(conn, username: str, email: str, password: str, role: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, email, password, role, created) VALUES (?,?,?,?,?)",
        (username, email, _hash(password), role, time.time()),
    )
    return cur.lastrowid


# ── Auth ────────────────────────────────────────────────────────────────────

def login(email_or_username: str, password: str) -> Optional[dict]:
    """Return user dict on success or None on failure."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE (email=? OR username=?) AND active=1",
            (email_or_username, email_or_username),
        ).fetchone()
        if row and row["password"] == _hash(password):
            return dict(row)
        return None


# ── User management (admin only) ─────────────────────────────────────────────

def create_user(username: str, email: str, password: str, role: str = "researcher") -> dict:
    with _get_conn() as conn:
        uid = _insert_user(conn, username, email, password, role)
        return {"id": uid, "username": username, "email": email, "role": role}


def list_users() -> list[dict]:
    with _get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT id,username,email,role,active,created FROM users ORDER BY id").fetchall()]


def update_user(uid: int, *, email: str | None = None, role: str | None = None,
                password: str | None = None, active: bool | None = None) -> bool:
    sets, vals = [], []
    if email is not None:
        sets.append("email=?"); vals.append(email)
    if role is not None:
        sets.append("role=?"); vals.append(role)
    if password is not None:
        sets.append("password=?"); vals.append(_hash(password))
    if active is not None:
        sets.append("active=?"); vals.append(1 if active else 0)
    if not sets:
        return False
    vals.append(uid)
    with _get_conn() as conn:
        conn.execute(f"UPDATE users SET {','.join(sets)} WHERE id=?", vals)
    return True


def delete_user(uid: int) -> bool:
    with _get_conn() as conn:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (uid,))
    return True


# ── Protocols ─────────────────────────────────────────────────────────────────

def save_protocol(name: str, description: str, steps: list, created_by: int,
                  protocol_id: int | None = None, category: str = "both") -> int:
    now = time.time()
    steps_json = json.dumps(steps)
    with _get_conn() as conn:
        if protocol_id:
            conn.execute(
                "UPDATE protocols SET name=?,description=?,steps=?,category=?,updated=? WHERE id=?",
                (name, description, steps_json, category, now, protocol_id),
            )
            return protocol_id
        else:
            cur = conn.execute(
                "INSERT INTO protocols (name,description,steps,category,created_by,created,updated)"
                " VALUES (?,?,?,?,?,?,?)",
                (name, description, steps_json, category, created_by, now, now),
            )
            return cur.lastrowid


def list_protocols(category: str | None = None) -> list[dict]:
    """List protocols, optionally filtered by category ('larval','adult','both')."""
    with _get_conn() as conn:
        if category and category != "both":
            rows = conn.execute(
                "SELECT * FROM protocols WHERE category=? OR category='both' ORDER BY updated DESC",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM protocols ORDER BY updated DESC").fetchall()


        result = []
        for r in rows:
            d = dict(r)
            d["steps"] = json.loads(d["steps"])
            result.append(d)
        return result


def get_protocol(protocol_id: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM protocols WHERE id=?", (protocol_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["steps"] = json.loads(d["steps"])
        return d


def delete_protocol(protocol_id: int) -> bool:
    with _get_conn() as conn:
        conn.execute("DELETE FROM protocols WHERE id=?", (protocol_id,))
    return True


# ── Experiments ───────────────────────────────────────────────────────────────

def create_experiment(name: str, protocol_id: int | None, protocol_name: str,
                      mode: str, camera: str, storage_path: str, created_by: int) -> dict:
    now = time.time()
    exp_id = f"EXP_{int(now)}"
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO experiments
               (exp_id,name,protocol_id,protocol_name,mode,camera,storage_path,created_by,started)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (exp_id, name, protocol_id, protocol_name, mode, camera, storage_path, created_by, now),
        )
        return {"id": cur.lastrowid, "exp_id": exp_id, "name": name, "started": now}


def finish_experiment(exp_id: str, duration_sec: float, status: str = "complete",
                      events_log: list | None = None) -> bool:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE experiments SET status=?,duration_sec=?,finished=?,events_log=? WHERE exp_id=?",
            (status, duration_sec, time.time(), json.dumps(events_log or []), exp_id),
        )
    return True


def list_experiments(limit: int = 50) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM experiments ORDER BY started DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["events_log"] = json.loads(d.get("events_log") or "[]")
            result.append(d)
        return result


# ── Camera Assignments ────────────────────────────────────────────────────────

def save_camera_assignment(camera_id: str, label: str, role: str) -> None:
    """Upsert a camera assignment (role: larval_machine_vision | adult_top | adult_side | unassigned)."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO camera_assignments (camera_id, label, role) VALUES (?,?,?) "
            "ON CONFLICT(camera_id) DO UPDATE SET label=excluded.label, role=excluded.role",
            (camera_id, label, role)
        )


def get_camera_assignments() -> dict:
    """Returns {camera_id: {label, role}} dict."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT camera_id, label, role FROM camera_assignments").fetchall()
        return {r["camera_id"]: {"label": r["label"], "role": r["role"]} for r in rows}


def get_camera_for_role(role: str) -> Optional[str]:
    """Returns camera_id assigned to this role, or None."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT camera_id FROM camera_assignments WHERE role=? LIMIT 1", (role,)
        ).fetchone()
        return row["camera_id"] if row else None
