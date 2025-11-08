"""Persistent caching using SQLite for resumable searches."""

import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..core.models import Paper
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SearchCache:
    """
    SQLite-based cache for search results enabling resumability.

    Stores raw API responses, parsed Paper objects and progress tracking.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "search_cache.db"
        self.conn = sqlite3.connect(
            str(self.db_path), isolation_level="DEFERRED", check_same_thread=False
        )
        # Performance options
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -64000")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS search_queries (
                query_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                query_text TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                created_at TEXT NOT NULL,
                completed BOOLEAN DEFAULT FALSE,
                last_offset INTEGER DEFAULT 0,
                last_cursor TEXT,
                total_pages INTEGER DEFAULT 0,
                total_papers INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_queries_source ON search_queries(source, query_text);

            CREATE TABLE IF NOT EXISTS cached_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                offset_value INTEGER,
                cursor_value TEXT,
                raw_response TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                paper_count INTEGER,
                FOREIGN KEY (query_id) REFERENCES search_queries(query_id),
                UNIQUE(query_id, page_number)
            );

            CREATE INDEX IF NOT EXISTS idx_pages_query ON cached_pages(query_id, page_number);

            CREATE TABLE IF NOT EXISTS cached_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT NOT NULL,
                paper_id TEXT NOT NULL,
                paper_data TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                FOREIGN KEY (query_id) REFERENCES search_queries(query_id),
                UNIQUE(query_id, paper_id)
            );

            CREATE INDEX IF NOT EXISTS idx_papers_query ON cached_papers(query_id);
            """
        )
        self.conn.commit()

    @staticmethod
    def _compute_query_id(source: str, query: str, start_date: Optional[str], end_date: Optional[str]) -> str:
        key = f"{source}|{query}|{start_date or ''}|{end_date or ''}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def register_query(
        self,
        source: str,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        query_id = self._compute_query_id(source, query, start_date, end_date)
        self.conn.execute(
            """INSERT OR IGNORE INTO search_queries
            (query_id, source, query_text, start_date, end_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                query_id,
                source,
                query,
                start_date,
                end_date,
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.commit()
        return query_id

    def get_query_progress(self, query_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            """SELECT source, query_text, start_date, end_date,
                      completed, last_offset, last_cursor, total_pages, total_papers
                   FROM search_queries WHERE query_id = ?""",
            (query_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "source": row[0],
            "query": row[1],
            "start_date": row[2],
            "end_date": row[3],
            "completed": bool(row[4]),
            "last_offset": row[5],
            "last_cursor": row[6],
            "total_pages": row[7],
            "total_papers": row[8],
        }

    def cache_page(
        self,
        query_id: str,
        page_number: int,
        raw_response: Dict[str, Any],
        offset: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> None:
        paper_count = len(raw_response.get("data") or raw_response.get("results", []))
        self.conn.execute(
            """INSERT OR REPLACE INTO cached_pages
            (query_id, page_number, offset_value, cursor_value, raw_response, fetched_at, paper_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                query_id,
                page_number,
                offset,
                cursor,
                json.dumps(raw_response),
                datetime.utcnow().isoformat(),
                paper_count,
            ),
        )
        # update progress
        self.conn.execute(
            """UPDATE search_queries SET last_offset = ?, last_cursor = ?, total_pages = total_pages + 1
               WHERE query_id = ?""",
            (offset, cursor, query_id),
        )
        self.conn.commit()

    def cache_paper(self, query_id: str, paper: Paper) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO cached_papers
            (query_id, paper_id, paper_data, cached_at)
            VALUES (?, ?, ?, ?)""",
            (
                query_id,
                paper.paper_id,
                paper.model_dump_json(exclude={"raw_data"}),
                datetime.utcnow().isoformat(),
            ),
        )
        self.conn.execute(
            """UPDATE search_queries SET total_papers = (
                SELECT COUNT(*) FROM cached_papers WHERE query_id = ?
            ) WHERE query_id = ?""",
            (query_id, query_id),
        )
        self.conn.commit()

    def get_cached_papers(self, query_id: str) -> List[Paper]:
        cur = self.conn.execute(
            "SELECT paper_data FROM cached_papers WHERE query_id = ? ORDER BY id", (query_id,)
        )
        papers: List[Paper] = []
        for (paper_json,) in cur:
            papers.append(Paper.model_validate_json(paper_json))
        return papers

    def mark_completed(self, query_id: str) -> None:
        self.conn.execute("UPDATE search_queries SET completed = TRUE WHERE query_id = ?", (query_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()