"""SQLite schema definition and connection helpers."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS snps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rsid TEXT NOT NULL,
    chromosome TEXT NOT NULL,
    position INTEGER NOT NULL,
    genotype TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snps_rsid ON snps(rsid);
CREATE INDEX IF NOT EXISTS idx_snps_chromosome_position ON snps(chromosome, position);
CREATE INDEX IF NOT EXISTS idx_snps_chromosome ON snps(chromosome);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.close()
