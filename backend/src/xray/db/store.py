from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np


SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY,
  media_key TEXT NOT NULL UNIQUE,
  path TEXT NOT NULL,
  size INTEGER NOT NULL,
  mtime_ns INTEGER NOT NULL,
  duration REAL NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY,
  external_id TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  portrait_path TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS roles (
  id INTEGER PRIMARY KEY,
  media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  UNIQUE(media_id, person_id, role)
);
CREATE TABLE IF NOT EXISTS embeddings (
  id INTEGER PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  media_id INTEGER REFERENCES media(id) ON DELETE CASCADE,
  scope TEXT NOT NULL CHECK(scope IN ('global','media-specific')),
  model_id TEXT NOT NULL,
  model_version TEXT NOT NULL,
  dimension INTEGER NOT NULL,
  vector BLOB NOT NULL,
  source TEXT NOT NULL,
  quality REAL NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model_id, model_version, person_id);
CREATE TABLE IF NOT EXISTS analyses (
  id INTEGER PRIMARY KEY,
  media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  timestamp REAL NOT NULL,
  timestamp_bucket INTEGER NOT NULL,
  model_id TEXT NOT NULL,
  response_json TEXT NOT NULL,
  latency_ms REAL NOT NULL,
  created_at REAL NOT NULL,
  UNIQUE(media_id, timestamp_bucket, model_id)
);
CREATE TABLE IF NOT EXISTS detections (
  id INTEGER PRIMARY KEY,
  analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  person_id INTEGER REFERENCES people(id),
  bbox_json TEXT NOT NULL,
  similarity REAL,
  top2_margin REAL,
  accepted INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS gallery_jobs (
  id INTEGER PRIMARY KEY,
  media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  urls_json TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  UNIQUE(media_id, person_id)
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def health(self) -> bool:
        try:
            with self.connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def upsert_media(self, media_key: str, path: Path, duration: float, metadata: dict[str, Any]) -> int:
        stat = path.stat()
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO media(media_key,path,size,mtime_ns,duration,metadata_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(media_key) DO UPDATE SET metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",
                (media_key, str(path), stat.st_size, stat.st_mtime_ns, duration, json.dumps(metadata), now, now),
            )
            return int(connection.execute("SELECT id FROM media WHERE media_key=?", (media_key,)).fetchone()[0])

    def upsert_person(self, external_id: str, name: str) -> int:
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO people(external_id,name,created_at,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(external_id) DO UPDATE SET name=excluded.name,updated_at=excluded.updated_at""",
                (external_id, name, now, now),
            )
            return int(connection.execute("SELECT id FROM people WHERE external_id=?", (external_id,)).fetchone()[0])

    def set_roles(self, media_id: int, person_id: int, roles: list[str]) -> None:
        with self.connect() as connection:
            changed = False
            for role in roles:
                if role.strip():
                    cursor = connection.execute(
                        "INSERT OR IGNORE INTO roles(media_id,person_id,role) VALUES(?,?,?)",
                        (media_id, person_id, role.strip()),
                    )
                    changed = changed or cursor.rowcount > 0
            if changed:
                connection.execute("DELETE FROM analyses WHERE media_id=?", (media_id,))

    def enqueue_gallery(self, media_id: int, person_id: int, urls: list[str]) -> None:
        if not urls:
            return
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO gallery_jobs(media_id,person_id,urls_json,state,created_at,updated_at)
                   VALUES(?,?,?,'queued',?,?)
                   ON CONFLICT(media_id,person_id) DO UPDATE SET
                     urls_json=excluded.urls_json,
                     state=CASE WHEN gallery_jobs.state='done' THEN 'done' ELSE 'queued' END,
                     updated_at=excluded.updated_at""",
                (media_id, person_id, json.dumps(urls), now, now),
            )

    def claim_gallery_job(self) -> sqlite3.Row | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM gallery_jobs WHERE state IN ('queued','retry') AND attempts < 4 ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE gallery_jobs SET state='running',attempts=attempts+1,updated_at=? WHERE id=?",
                    (time.time(), row["id"]),
                )
            return row

    def finish_gallery_job(self, job_id: int, error: str | None = None) -> None:
        state = "done" if error is None else "retry"
        with self.connect() as connection:
            connection.execute(
                "UPDATE gallery_jobs SET state=?,error=?,updated_at=? WHERE id=?",
                (state, error[:500] if error else None, time.time(), job_id),
            )

    def add_embedding(
        self,
        person_id: int,
        vector: np.ndarray,
        model_id: str,
        model_version: str,
        source: str,
        quality: float,
        media_id: int | None = None,
        scope: str = "global",
    ) -> None:
        contiguous = np.asarray(vector, dtype=np.float32).reshape(-1)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO embeddings(person_id,media_id,scope,model_id,model_version,dimension,vector,source,quality,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    person_id,
                    media_id,
                    scope,
                    model_id,
                    model_version,
                    contiguous.size,
                    contiguous.tobytes(),
                    source,
                    quality,
                    time.time(),
                ),
            )
            connection.execute(
                "DELETE FROM analyses WHERE media_id IN (SELECT media_id FROM roles WHERE person_id=?)",
                (person_id,),
            )

    def count_embeddings(self, person_id: int, model_id: str, model_version: str) -> int:
        with self.connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE person_id=? AND model_id=? AND model_version=?",
                    (person_id, model_id, model_version),
                ).fetchone()[0]
            )

    def gallery_for_media(self, media_id: int, model_id: str, model_version: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.id person_id,p.external_id,p.name,p.portrait_path,e.vector,e.dimension,
                          GROUP_CONCAT(DISTINCT r.role) roles
                   FROM roles r JOIN people p ON p.id=r.person_id
                   JOIN embeddings e ON e.person_id=p.id
                   WHERE r.media_id=? AND e.model_id=? AND e.model_version=?
                     AND (e.scope='global' OR e.media_id=?)
                   GROUP BY p.id,e.id""",
                (media_id, model_id, model_version, media_id),
            ).fetchall()
        return [
            {
                "person_id": row["person_id"],
                "external_id": row["external_id"],
                "name": row["name"],
                "portrait_path": row["portrait_path"],
                "roles": (row["roles"] or "").split(",") if row["roles"] else [],
                "vector": np.frombuffer(row["vector"], dtype=np.float32, count=row["dimension"]).copy(),
            }
            for row in rows
        ]

    def get_cached(self, media_id: int, bucket: int, model_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT response_json FROM analyses WHERE media_id=? AND timestamp_bucket=? AND model_id=?",
                (media_id, bucket, model_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put_analysis(
        self,
        media_id: int,
        timestamp: float,
        bucket: int,
        model_id: str,
        response: dict[str, Any],
        latency_ms: float,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO analyses(media_id,timestamp,timestamp_bucket,model_id,response_json,latency_ms,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (media_id, timestamp, bucket, model_id, json.dumps(response), latency_ms, time.time()),
            )
            analysis_id = int(
                connection.execute(
                    "SELECT id FROM analyses WHERE media_id=? AND timestamp_bucket=? AND model_id=?",
                    (media_id, bucket, model_id),
                ).fetchone()[0]
            )
            for detection in response.get("people", []):
                actor = detection.get("actor", {})
                person = connection.execute(
                    "SELECT id FROM people WHERE external_id=?", (actor.get("id"),)
                ).fetchone()
                connection.execute(
                    """INSERT INTO detections(analysis_id,person_id,bbox_json,similarity,top2_margin,accepted)
                       VALUES(?,?,?,?,?,?)""",
                    (
                        analysis_id,
                        int(person[0]) if person else None,
                        json.dumps(detection.get("bbox", {})),
                        detection.get("similarity"),
                        detection.get("top2_margin"),
                        1 if detection.get("accepted") else 0,
                    ),
                )

    def set_portrait(self, person_id: int, path: Path) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE people SET portrait_path=?,updated_at=? WHERE id=?",
                (str(path), time.time(), person_id),
            )

    def person(self, person_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id,external_id,name,portrait_path FROM people WHERE id=?", (person_id,)
            ).fetchone()
        return dict(row) if row else None

    def portrait(self, external_id: str) -> Path | None:
        with self.connect() as connection:
            row = connection.execute("SELECT portrait_path FROM people WHERE external_id=?", (external_id,)).fetchone()
        return Path(row[0]) if row and row[0] else None

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("media", "people", "embeddings", "analyses", "detections", "gallery_jobs")
            }
            avg = connection.execute("SELECT AVG(latency_ms) FROM analyses").fetchone()[0]
        counts.update({"db_bytes": self.path.stat().st_size if self.path.exists() else 0, "average_latency_ms": avg or 0})
        return counts

    def gallery_counts(self, media_id: int, model_id: str, model_version: str) -> tuple[int, int]:
        with self.connect() as connection:
            ready = connection.execute(
                """SELECT COUNT(DISTINCT r.person_id) FROM roles r JOIN embeddings e ON e.person_id=r.person_id
                   WHERE r.media_id=? AND e.model_id=? AND e.model_version=?""",
                (media_id, model_id, model_version),
            ).fetchone()[0]
            queued = connection.execute(
                "SELECT COUNT(*) FROM gallery_jobs WHERE media_id=? AND state!='done'", (media_id,)
            ).fetchone()[0]
        return int(ready), int(queued)

    def prune_analyses(self, older_than: float) -> int:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM analyses WHERE created_at < ?", (older_than,))
            return cursor.rowcount

    def invalidate_media(self, media_key: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM analyses WHERE media_id=(SELECT id FROM media WHERE media_key=?)",
                (media_key,),
            )
            return cursor.rowcount

    def gallery_status(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.external_id,p.name,g.state,g.attempts,g.error,
                          COUNT(e.id) AS embeddings
                   FROM gallery_jobs g JOIN people p ON p.id=g.person_id
                   LEFT JOIN embeddings e ON e.person_id=p.id
                   GROUP BY g.id ORDER BY p.name"""
            ).fetchall()
        return [dict(row) for row in rows]

    def rebuild_gallery(self, external_id: str | None = None) -> dict[str, int]:
        with self.connect() as connection:
            if external_id:
                people = connection.execute(
                    "SELECT id FROM people WHERE external_id=?", (external_id,)
                ).fetchall()
            else:
                people = connection.execute("SELECT id FROM people").fetchall()
            person_ids = [int(row[0]) for row in people]
            if not person_ids:
                return {"people": 0, "embeddings_deleted": 0, "jobs_queued": 0}
            placeholders = ",".join("?" for _ in person_ids)
            analyses = connection.execute(
                f"SELECT DISTINCT media_id FROM roles WHERE person_id IN ({placeholders})", person_ids
            ).fetchall()
            media_ids = [int(row[0]) for row in analyses]
            deleted = connection.execute(
                f"DELETE FROM embeddings WHERE person_id IN ({placeholders})", person_ids
            ).rowcount
            queued = connection.execute(
                f"""UPDATE gallery_jobs SET state='queued',attempts=0,error=NULL,updated_at=?
                    WHERE person_id IN ({placeholders})""",
                (time.time(), *person_ids),
            ).rowcount
            if media_ids:
                media_placeholders = ",".join("?" for _ in media_ids)
                connection.execute(
                    f"DELETE FROM analyses WHERE media_id IN ({media_placeholders})", media_ids
                )
            return {"people": len(person_ids), "embeddings_deleted": deleted, "jobs_queued": queued}
