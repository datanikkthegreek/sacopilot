"""Lakebase (Databricks managed Postgres) persistence for email classifications.

Classifications are stored here instead of being written back as Gmail labels:
the dbexec Google MCP exposes no labels.list/create, so Gmail can't hold the
taxonomy. Lakebase is the system of record — one row per conversation
(thread_id) with the 6-facet taxonomy, the flat label names, and confidence.

Auth: the Postgres password is a short-lived OAuth credential minted by the
Databricks CLI (`databricks postgres generate-database-credential`). Tokens
expire after ~1h, so we cache and refresh. The endpoint host is fetched once.
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from sacopilot.backend import config, taxonomy

# --- Resource coordinates (override via env in config) -----------------------
_PROFILE = config.LAKEBASE_PROFILE
_PROJECT = config.LAKEBASE_PROJECT
_BRANCH = config.LAKEBASE_BRANCH
_ENDPOINT = config.LAKEBASE_ENDPOINT
_DB = config.LAKEBASE_DB

_BRANCH_PATH = f"projects/{_PROJECT}/branches/{_BRANCH}"
_ENDPOINT_PATH = f"{_BRANCH_PATH}/endpoints/{_ENDPOINT}"

# Caches (host is stable; token lives ~1h — refresh well before).
_host: str | None = None
_user: str | None = None
_token: str | None = None
_token_minted_at: float = 0.0
_TOKEN_TTL = 45 * 60  # seconds; refresh before the ~1h expiry


def _cli(args: list[str]) -> Any:
    out = subprocess.run(
        ["databricks", *args, "-p", _PROFILE, "-o", "json"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"databricks {' '.join(args)} failed: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def _get_host() -> str:
    global _host
    if _host is None:
        eps = _cli(["postgres", "list-endpoints", _BRANCH_PATH])
        if not eps:
            raise RuntimeError(f"no endpoints on {_BRANCH_PATH}")
        _host = eps[0]["status"]["hosts"]["host"]
    return _host


def _get_user() -> str:
    global _user
    if _user is None:
        _user = _cli(["current-user", "me"])["userName"]
    return _user


def _get_token() -> str:
    global _token, _token_minted_at
    if _token is None or (time.time() - _token_minted_at) > _TOKEN_TTL:
        _token = _cli(["postgres", "generate-database-credential", _ENDPOINT_PATH])["token"]
        _token_minted_at = time.time()
    return _token


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=_get_host(), port=5432, dbname=_DB,
        user=_get_user(), password=_get_token(), sslmode="require",
    )


# --- Public API --------------------------------------------------------------

def available() -> bool:
    try:
        with _connect() as c:
            c.execute("SELECT 1")
        return True
    except Exception:
        return False


# --- Inbox cache: threads -----------------------------------------------------

def existing_thread_ids(thread_ids: list[str]) -> set[str]:
    """Subset of the given thread ids already in the cache (skip re-fetch)."""
    if not thread_ids:
        return set()
    with _connect() as c:
        rows = c.execute(
            "SELECT thread_id FROM threads WHERE thread_id = ANY(%s)", (thread_ids,)
        ).fetchall()
    return {tid for (tid,) in rows}


def upsert_thread(meta: dict) -> None:
    """Upsert a thread's Gmail metadata (classification/status preserved)."""
    sql = """
        INSERT INTO threads
            (thread_id, subject, sender, snippet, message_count,
             last_internal_date, unread, in_inbox, synced_at)
        VALUES
            (%(thread_id)s, %(subject)s, %(sender)s, %(snippet)s, %(message_count)s,
             %(last_internal_date)s, %(unread)s, TRUE, now())
        ON CONFLICT (thread_id) DO UPDATE SET
            subject=EXCLUDED.subject, sender=EXCLUDED.sender,
            snippet=EXCLUDED.snippet, message_count=EXCLUDED.message_count,
            last_internal_date=EXCLUDED.last_internal_date,
            unread=EXCLUDED.unread, in_inbox=TRUE, synced_at=now();
    """
    with _connect() as c:
        c.execute(sql, meta)
        c.commit()


def upsert_messages(thread_id: str, messages: list[dict]) -> None:
    """Upsert per-message metadata rows (bodies left untouched)."""
    if not messages:
        return
    sql = """
        INSERT INTO messages
            (message_id, thread_id, ordinal, from_addr, to_addr, date_str,
             internal_date, subject, snippet, synced_at)
        VALUES
            (%(message_id)s, %(thread_id)s, %(ordinal)s, %(from_addr)s, %(to_addr)s,
             %(date_str)s, %(internal_date)s, %(subject)s, %(snippet)s, now())
        ON CONFLICT (message_id) DO UPDATE SET
            ordinal=EXCLUDED.ordinal, from_addr=EXCLUDED.from_addr,
            to_addr=EXCLUDED.to_addr, date_str=EXCLUDED.date_str,
            internal_date=EXCLUDED.internal_date, subject=EXCLUDED.subject,
            snippet=EXCLUDED.snippet, synced_at=now();
    """
    rows = [{"thread_id": thread_id, **m} for m in messages]
    with _connect() as c:
        c.cursor().executemany(sql, rows)
        c.commit()


def reconcile_inbox(inbox_ids: list[str]) -> int:
    """Mark cached threads no longer in the inbox as in_inbox=false. Returns the
    count newly archived-away."""
    with _connect() as c:
        n = c.execute(
            "UPDATE threads SET in_inbox=FALSE "
            "WHERE in_inbox=TRUE AND NOT (thread_id = ANY(%s))",
            (inbox_ids,),
        ).rowcount
        c.commit()
    return n


def set_status(thread_id: str, status: str, leave_inbox: bool = False) -> None:
    """Set a conversation's workflow status. leave_inbox drops it from the inbox
    view (used when Completed → archived in Gmail)."""
    sql = ("UPDATE threads SET status=%s" + (", in_inbox=FALSE" if leave_inbox else "") +
           " WHERE thread_id=%s")
    with _connect() as c:
        n = c.execute(sql, (status, thread_id)).rowcount
        c.commit()
    if not n:
        raise RuntimeError(f"thread {thread_id} not in cache")


def set_unread(unread_ids: list[str]) -> None:
    """Bulk-set unread flags for inbox threads from the is:unread id set."""
    with _connect() as c:
        c.execute(
            "UPDATE threads SET unread = (thread_id = ANY(%s)) WHERE in_inbox",
            (unread_ids,),
        )
        c.commit()


def _iso(ms: int | None) -> str | None:
    if not ms:
        return None
    return _dt.datetime.fromtimestamp(ms / 1000, _dt.timezone.utc).astimezone().isoformat()


def _facets(r: dict) -> dict | None:
    if not r.get("classified_at"):
        return None
    return {
        "type": r["type"], "org": r["org"], "prio": r["prio"], "dbx": r["dbx"],
        "bosch": r["bosch"], "bu": r["bu"] or [], "labels": r["labels"] or [],
        "confidence": r["confidence"], "needs_review": r["needs_review"],
        "adjusted": r["adjusted"],
    }


def _thread_row(r: dict) -> dict:
    return {
        "thread_id": r["thread_id"],
        "subject": r["subject"] or "(no subject)",
        "from": r["sender"] or "",
        "snippet": r["snippet"] or "",
        "message_count": r["message_count"] or 1,
        "internal_date": r["last_internal_date"],
        "date": _iso(r["last_internal_date"]),
        "unread": r["unread"],
        "status": r["status"],
        "labels": r["labels"] or [],
        "classified": r["classified_at"] is not None,
        "adjusted": r["adjusted"],
        "facets": _facets(r),
    }


def list_threads(limit: int = 100, offset: int = 0, unread: bool | None = None,
                 status: str | None = None, label: str | None = None) -> list[dict]:
    """Inbox conversations from the cache, newest-first. Pure DB read."""
    where = ["in_inbox"]
    params: list[Any] = []
    if unread:
        where.append("unread")
    if status:
        where.append("status = %s"); params.append(status)
    if label:
        where.append("%s = ANY(labels)"); params.append(label)
    sql = (
        "SELECT * FROM threads WHERE " + " AND ".join(where) +
        " ORDER BY last_internal_date DESC NULLS LAST LIMIT %s OFFSET %s"
    )
    params += [limit, offset]
    with _connect() as c:
        c.row_factory = dict_row
        rows = c.execute(sql, params).fetchall()
    return [_thread_row(r) for r in rows]


def count_threads(unread: bool | None = None) -> dict:
    """Inbox totals for the header (total + unread + classified)."""
    with _connect() as c:
        c.row_factory = dict_row
        r = c.execute(
            "SELECT count(*) AS total, "
            "count(*) FILTER (WHERE unread) AS unread, "
            "count(*) FILTER (WHERE classified_at IS NOT NULL) AS classified "
            "FROM threads WHERE in_inbox"
        ).fetchone()
    return {"total": r["total"], "unread": r["unread"], "classified": r["classified"]}


# --- Message bodies (cache-through on open) -----------------------------------

def get_thread_messages(thread_id: str) -> list[dict]:
    with _connect() as c:
        c.row_factory = dict_row
        return c.execute(
            "SELECT message_id, ordinal, from_addr, to_addr, date_str, "
            "internal_date, subject, snippet, body_html, body_text "
            "FROM messages WHERE thread_id = %s ORDER BY ordinal", (thread_id,)
        ).fetchall()


def store_body(message_id: str, body_html: str, body_text: str) -> None:
    with _connect() as c:
        c.execute(
            "UPDATE messages SET body_html=%s, body_text=%s WHERE message_id=%s",
            (body_html, body_text, message_id),
        )
        c.commit()


# --- Classification (onto the cached threads row) -----------------------------

def save_classification(thread_id: str, facets: dict, labels: list[str]) -> dict[str, Any]:
    """Write a fresh model classification onto an existing cached thread row.
    auto_* == effective; adjusted=false."""
    row = {
        "thread_id": thread_id,
        "type": facets.get("type"), "org": facets.get("org"),
        "prio": str(facets["prio"]) if facets.get("prio") is not None else None,
        "dbx": facets.get("dbx"), "bosch": facets.get("bosch"),
        "bu": facets.get("bu", []) or [], "labels": labels,
        "confidence": facets.get("confidence"), "rationale": facets.get("rationale"),
        "needs_review": bool(facets.get("needs_review")),
        "auto_facets": Jsonb(facets), "auto_labels": labels,
    }
    sql = """
        UPDATE threads SET
            type=%(type)s, org=%(org)s, prio=%(prio)s, dbx=%(dbx)s, bosch=%(bosch)s,
            bu=%(bu)s, labels=%(labels)s, confidence=%(confidence)s,
            rationale=%(rationale)s, needs_review=%(needs_review)s,
            auto_facets=%(auto_facets)s, auto_labels=%(auto_labels)s,
            adjusted=FALSE, adjusted_at=NULL, classified_at=now()
        WHERE thread_id=%(thread_id)s;
    """
    with _connect() as c:
        n = c.execute(sql, row).rowcount
        c.commit()
    if not n:
        raise RuntimeError(f"thread {thread_id} not in cache; run sync first")
    return {"thread_id": thread_id, "labels": labels, "saved": True}


def update_classification(thread_id: str, facets: dict) -> dict[str, Any]:
    """Apply a manual facet edit: recompute labels, set effective columns, mark
    adjusted. The auto_* snapshot is left untouched."""
    labels = taxonomy.all_label_names(facets)
    row = {
        "thread_id": thread_id,
        "type": facets.get("type"), "org": facets.get("org"),
        "prio": str(facets["prio"]) if facets.get("prio") is not None else None,
        "dbx": facets.get("dbx"), "bosch": facets.get("bosch"),
        "bu": facets.get("bu", []) or [], "labels": labels,
        "needs_review": bool(facets.get("needs_review")),
    }
    sql = """
        UPDATE threads SET
            type=%(type)s, org=%(org)s, prio=%(prio)s, dbx=%(dbx)s, bosch=%(bosch)s,
            bu=%(bu)s, labels=%(labels)s, needs_review=%(needs_review)s,
            adjusted=TRUE, adjusted_at=now(),
            classified_at=COALESCE(classified_at, now())
        WHERE thread_id=%(thread_id)s;
    """
    with _connect() as c:
        n = c.execute(sql, row).rowcount
        c.commit()
    if not n:
        raise RuntimeError(f"no classification to update for {thread_id}")
    return {"thread_id": thread_id, "labels": labels, "adjusted": True}


def facets_for(thread_ids: list[str]) -> dict[str, dict]:
    """Map thread_id -> effective facets (classified rows only)."""
    if not thread_ids:
        return {}
    with _connect() as c:
        c.row_factory = dict_row
        rows = c.execute(
            "SELECT * FROM threads WHERE thread_id = ANY(%s) AND classified_at IS NOT NULL",
            (thread_ids,),
        ).fetchall()
    return {r["thread_id"]: _facets(r) for r in rows}


def unclassified_inbox_threads(limit: int = 500) -> list[dict]:
    """Cached inbox threads not yet classified (for the classify pass)."""
    with _connect() as c:
        c.row_factory = dict_row
        rows = c.execute(
            "SELECT thread_id, subject, sender, snippet FROM threads "
            "WHERE in_inbox AND classified_at IS NULL "
            "ORDER BY last_internal_date DESC NULLS LAST LIMIT %s", (limit,)
        ).fetchall()
    return [{"thread_id": r["thread_id"], "subject": r["subject"],
             "from": r["sender"], "snippet": r["snippet"]} for r in rows]


def recent_adjusted(limit: int = 8) -> list[dict]:
    """Recent manually-adjusted rows as few-shot examples for the classifier."""
    with _connect() as c:
        c.row_factory = dict_row
        rows = c.execute(
            "SELECT subject, sender, type, org, prio, dbx, bosch, bu "
            "FROM threads WHERE adjusted = TRUE "
            "ORDER BY adjusted_at DESC LIMIT %s", (limit,)
        ).fetchall()
    return [
        {"subject": r["subject"], "from": r["sender"], "type": r["type"],
         "org": r["org"], "prio": r["prio"], "dbx": r["dbx"],
         "bosch": r["bosch"], "bu": r["bu"] or []}
        for r in rows
    ]


# --- Action board (todos) ----------------------------------------------------

_TODO_COLS = ("id, title, description, status, priority, estimate_hours, type, "
              "use_case_id, use_case_name, bu, project, tags, created_at, updated_at")
_TODO_FIELDS = ("title", "description", "status", "priority", "estimate_hours",
                "type", "use_case_id", "use_case_name", "bu", "project", "tags")


def list_todos() -> list[dict]:
    """All todos, ordered for the board: P0 first, then most-recently-updated."""
    with _connect() as c:
        c.row_factory = dict_row
        return c.execute(
            f"SELECT {_TODO_COLS} FROM todos ORDER BY priority ASC, updated_at DESC"
        ).fetchall()


def create_todo(fields: dict, todo_id: str) -> dict:
    row = {"id": todo_id, **{k: fields.get(k) for k in _TODO_FIELDS}}
    row["title"] = row.get("title") or "(untitled)"
    row["status"] = row.get("status") or "Open"
    row["priority"] = str(row.get("priority") or "2")
    row["tags"] = row.get("tags") or []
    with _connect() as c:
        c.row_factory = dict_row
        return c.execute(
            f"INSERT INTO todos (id, {', '.join(_TODO_FIELDS)}) "
            f"VALUES (%(id)s, {', '.join('%(' + f + ')s' for f in _TODO_FIELDS)}) "
            f"RETURNING {_TODO_COLS}", row
        ).fetchone()


def update_todo(todo_id: str, fields: dict) -> dict:
    """Update any subset of fields (incl. status, for moving columns)."""
    sets = [f for f in _TODO_FIELDS if f in fields]
    if not sets:
        raise RuntimeError("nothing to update")
    params = {f: fields[f] for f in sets}
    params["id"] = todo_id
    assigns = ", ".join(f"{f} = %({f})s" for f in sets) + ", updated_at = now()"
    with _connect() as c:
        c.row_factory = dict_row
        r = c.execute(f"UPDATE todos SET {assigns} WHERE id = %(id)s RETURNING {_TODO_COLS}",
                      params).fetchone()
    if not r:
        raise RuntimeError(f"todo {todo_id} not found")
    return r


def delete_todo(todo_id: str) -> bool:
    with _connect() as c:
        n = c.execute("DELETE FROM todos WHERE id = %s", (todo_id,)).rowcount
        c.commit()
    return bool(n)
