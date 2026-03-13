from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class RunStore(ABC):
    @abstractmethod
    def save_run(self, run_id: str, trace: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return []


class SQLiteRunStore(RunStore):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists run_traces (
                  run_id text primary key,
                  trace_json text not null,
                  created_at text default current_timestamp
                );

                create table if not exists run_events (
                  id integer primary key autoincrement,
                  run_id text not null,
                  event_json text not null,
                  created_at text default current_timestamp
                );
                """
            )

    def save_run(self, run_id: str, trace: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into run_traces(run_id, trace_json) values (?, ?)
                on conflict(run_id) do update set trace_json = excluded.trace_json
                """,
                (run_id, json.dumps(trace)),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select trace_json from run_traces where run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["trace_json"])

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into run_events(run_id, event_json) values (?, ?)",
                (run_id, json.dumps(event)),
            )

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select event_json from run_events where run_id = ? order by id asc",
                (run_id,),
            ).fetchall()
        return [json.loads(row["event_json"]) for row in rows]

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select trace_json from run_traces order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        results = []
        for row in rows:
            try:
                data = json.loads(row["trace_json"])
                results.append({
                    "run_id": data.get("run_id", ""),
                    "conversation_id": data.get("conversation_id", ""),
                    "user_id": data.get("user_id", ""),
                    "created_at": data.get("created_at", ""),
                })
            except (json.JSONDecodeError, KeyError):
                pass
        return results


class PostgresRunStore(RunStore):
    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresRunStore") from exc

        self._psycopg = psycopg
        self._dsn = dsn
        self._init_db()

    def _connect(self):
        return self._psycopg.connect(self._dsn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    create table if not exists run_traces (
                      run_id text primary key,
                      trace_json jsonb not null,
                      created_at timestamptz not null default now()
                    )
                    """
                )
                cur.execute(
                    """
                    create table if not exists run_events (
                      id bigserial primary key,
                      run_id text not null,
                      event_json jsonb not null,
                      created_at timestamptz not null default now()
                    )
                    """
                )
            conn.commit()

    def save_run(self, run_id: str, trace: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into run_traces(run_id, trace_json)
                    values (%s, %s)
                    on conflict(run_id)
                    do update set trace_json = excluded.trace_json
                    """,
                    (run_id, Jsonb(trace)),
                )
            conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select trace_json from run_traces where run_id = %s", (run_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return dict(row[0]) if not isinstance(row[0], dict) else row[0]

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into run_events(run_id, event_json) values (%s, %s)",
                    (run_id, Jsonb(event)),
                )
            conn.commit()

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select event_json from run_events where run_id = %s order by id asc",
                    (run_id,),
                )
                rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            value = row[0]
            out.append(dict(value) if not isinstance(value, dict) else value)
        return out
