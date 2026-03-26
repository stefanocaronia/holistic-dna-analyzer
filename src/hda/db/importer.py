"""Import raw DNA data files into SQLite."""

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hda.config import SOURCES_DIR, get_db_path, load_config, save_config
from hda.db.schema import get_connection, init_db

BATCH_SIZE = 50_000


def parse_myheritage(filepath: Path) -> list[tuple[str, str, int, str]]:
    """Parse a MyHeritage CSV file, yielding (rsid, chromosome, position, genotype) tuples."""
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        # Skip comment lines
        for line in f:
            if not line.startswith("#"):
                break
        reader = csv.DictReader(f, fieldnames=["RSID", "CHROMOSOME", "POSITION", "RESULT"])
        for row in reader:
            rsid = row["RSID"].strip('"')
            chrom = row["CHROMOSOME"].strip('"')
            pos = int(row["POSITION"].strip('"'))
            genotype = row["RESULT"].strip('"')
            rows.append((rsid, chrom, pos, genotype))
    return rows


def detect_format(filepath: Path) -> str:
    """Detect the source file format from its header."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
    if "MyHeritage" in first_line:
        return "MyHeritage"
    if "AncestryDNA" in first_line:
        return "AncestryDNA"
    if "23andMe" in first_line:
        return "23andMe"
    return "unknown"


PARSERS = {
    "MyHeritage": parse_myheritage,
}


def import_subject(subject_key: str) -> int:
    """Import a subject's source file into their SQLite database. Returns row count."""
    config = load_config()
    subject = config["subjects"][subject_key]
    source_file = SOURCES_DIR / subject["source_file"]

    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    fmt = subject.get("source_format") or detect_format(source_file)
    parser = PARSERS.get(fmt)
    if parser is None:
        raise ValueError(f"Unsupported format: {fmt}. Supported: {list(PARSERS.keys())}")

    db_path = get_db_path(subject_key)
    init_db(db_path)

    rows = parser(source_file)

    conn = get_connection(db_path)
    try:
        # Clear existing data for clean re-import
        conn.execute("DELETE FROM snps")

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            conn.executemany(
                "INSERT INTO snps (rsid, chromosome, position, genotype) VALUES (?, ?, ?, ?)",
                batch,
            )
        conn.commit()
    finally:
        conn.close()

    # Update imported_at in config
    config["subjects"][subject_key]["imported_at"] = datetime.now(timezone.utc).isoformat()
    if not subject.get("source_format"):
        config["subjects"][subject_key]["source_format"] = fmt
    save_config(config)

    return len(rows)
