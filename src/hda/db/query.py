"""Query helpers for SNP databases."""

import sqlite3
from pathlib import Path

from hda.config import get_db_path, get_active_subject
from hda.db.schema import get_connection


def _conn(subject: str | None = None) -> sqlite3.Connection:
    subject = subject or get_active_subject()
    db_path = get_db_path(subject)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found for '{subject}'. Run 'hda import {subject}' first.")
    return get_connection(db_path)


def get_snp(rsid: str, subject: str | None = None) -> dict | None:
    """Look up a single SNP by rsid."""
    conn = _conn(subject)
    row = conn.execute(
        "SELECT rsid, chromosome, position, genotype FROM snps WHERE rsid = ?",
        (rsid,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def search_snps(
    chromosome: str | None = None,
    position_start: int | None = None,
    position_end: int | None = None,
    genotype: str | None = None,
    rsid_pattern: str | None = None,
    subject: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Search SNPs with filters."""
    conn = _conn(subject)
    conditions = []
    params: list = []

    if chromosome:
        conditions.append("chromosome = ?")
        params.append(chromosome)
    if position_start is not None:
        conditions.append("position >= ?")
        params.append(position_start)
    if position_end is not None:
        conditions.append("position <= ?")
        params.append(position_end)
    if genotype:
        conditions.append("genotype = ?")
        params.append(genotype)
    if rsid_pattern:
        conditions.append("rsid LIKE ?")
        params.append(rsid_pattern)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    rows = conn.execute(
        f"SELECT rsid, chromosome, position, genotype FROM snps WHERE {where} ORDER BY chromosome, position LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_snps(subject: str | None = None) -> int:
    """Count total SNPs for a subject."""
    conn = _conn(subject)
    row = conn.execute("SELECT COUNT(*) as cnt FROM snps").fetchone()
    conn.close()
    return row["cnt"]


def chromosome_summary(subject: str | None = None) -> list[dict]:
    """Get SNP count per chromosome."""
    conn = _conn(subject)
    rows = conn.execute(
        "SELECT chromosome, COUNT(*) as count FROM snps GROUP BY chromosome ORDER BY "
        "CASE WHEN chromosome GLOB '[0-9]*' THEN CAST(chromosome AS INTEGER) "
        "ELSE 999 END, chromosome"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def compare_snp(rsid: str, subject_a: str, subject_b: str) -> dict:
    """Compare a specific SNP between two subjects."""
    snp_a = get_snp(rsid, subject_a)
    snp_b = get_snp(rsid, subject_b)
    return {
        "rsid": rsid,
        subject_a: snp_a["genotype"] if snp_a else None,
        subject_b: snp_b["genotype"] if snp_b else None,
        "match": (snp_a and snp_b and snp_a["genotype"] == snp_b["genotype"]),
    }


def compare_subjects(
    subject_a: str,
    subject_b: str,
    only_different: bool = True,
    chromosome: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Compare SNPs between two subjects using ATTACH DATABASE."""
    db_a = get_db_path(subject_a)
    db_b = get_db_path(subject_b)
    if not db_a.exists():
        raise FileNotFoundError(f"Database not found for '{subject_a}'")
    if not db_b.exists():
        raise FileNotFoundError(f"Database not found for '{subject_b}'")

    conn = get_connection(db_a)
    conn.execute(f"ATTACH DATABASE ? AS db_b", (str(db_b),))

    conditions = ["a.rsid = b.rsid"]
    params: list = []

    if only_different:
        conditions.append("a.genotype != b.genotype")
    if chromosome:
        conditions.append("a.chromosome = ?")
        params.append(chromosome)

    where = " AND ".join(conditions)
    params.append(limit)

    rows = conn.execute(
        f"SELECT a.rsid, a.chromosome, a.position, "
        f"a.genotype AS genotype_a, b.genotype AS genotype_b "
        f"FROM snps a JOIN db_b.snps b ON {where} "
        f"ORDER BY a.chromosome, a.position LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
