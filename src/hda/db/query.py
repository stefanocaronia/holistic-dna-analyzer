"""Query helpers for SNP databases."""

import sqlite3

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
    rows = _joined_subject_rows(
        subject_a=subject_a,
        subject_b=subject_b,
        chromosome=chromosome,
        limit=limit,
        only_different=only_different,
    )
    return [dict(r) for r in rows]


def _joined_subject_rows(
    subject_a: str,
    subject_b: str,
    chromosome: str | None = None,
    limit: int | None = None,
    only_different: bool = False,
) -> list[sqlite3.Row]:
    """Return joined SNP rows between two subjects."""
    db_a = get_db_path(subject_a)
    db_b = get_db_path(subject_b)
    if not db_a.exists():
        raise FileNotFoundError(f"Database not found for '{subject_a}'")
    if not db_b.exists():
        raise FileNotFoundError(f"Database not found for '{subject_b}'")

    conn = get_connection(db_a)
    conn.execute("ATTACH DATABASE ? AS db_b", (str(db_b),))

    conditions = ["a.rsid = b.rsid"]
    params: list = []

    if only_different:
        conditions.append("a.genotype != b.genotype")
    if chromosome:
        conditions.append("a.chromosome = ?")
        params.append(chromosome)

    where = " AND ".join(conditions)
    limit_clause = ""
    if limit is not None:
        limit_clause = " LIMIT ?"
        params.append(limit)

    rows = conn.execute(
        f"SELECT a.rsid, a.chromosome, a.position, "
        f"a.genotype AS genotype_a, b.genotype AS genotype_b "
        f"FROM snps a JOIN db_b.snps b ON {where} "
        f"ORDER BY a.chromosome, a.position{limit_clause}",
        params,
    ).fetchall()
    conn.close()
    return rows


def _ibs_bucket(genotype_a: str, genotype_b: str) -> str:
    """Classify a genotype pair into a simple IBS bucket."""
    if genotype_a == genotype_b:
        return "ibs2"

    alleles_a = [allele for allele in genotype_a if allele != "-"]
    alleles_b = [allele for allele in genotype_b if allele != "-"]
    shared = len(set(alleles_a) & set(alleles_b))
    return "ibs0" if shared == 0 else "ibs1"


def estimate_relatedness(subject_a: str, subject_b: str) -> dict:
    """Return a simple heuristic relatedness summary between two subjects."""
    rows = _joined_subject_rows(subject_a, subject_b, limit=None, only_different=False)

    comparable = 0
    exact_matches = 0
    ibs0 = 0
    ibs1 = 0
    ibs2 = 0

    for row in rows:
        genotype_a = row["genotype_a"]
        genotype_b = row["genotype_b"]
        if not genotype_a or not genotype_b or "-" in genotype_a or "-" in genotype_b:
            continue
        if len(genotype_a) != 2 or len(genotype_b) != 2:
            continue

        comparable += 1
        if genotype_a == genotype_b:
            exact_matches += 1

        bucket = _ibs_bucket(genotype_a, genotype_b)
        if bucket == "ibs0":
            ibs0 += 1
        elif bucket == "ibs1":
            ibs1 += 1
        else:
            ibs2 += 1

    if comparable == 0:
        return {
            "subject_a": subject_a,
            "subject_b": subject_b,
            "shared_snps": len(rows),
            "comparable_snps": 0,
            "exact_match_count": 0,
            "exact_match_rate": 0.0,
            "ibs0_count": 0,
            "ibs1_count": 0,
            "ibs2_count": 0,
            "heuristic_relationship": "insufficient_data",
            "interpretation_warning": (
                "Not enough comparable SNPs were available to estimate relatedness. "
                "This heuristic is exploratory and not suitable for legal or clinical use."
            ),
        }

    exact_rate = exact_matches / comparable
    ibs0_rate = ibs0 / comparable
    ibs1_rate = ibs1 / comparable
    ibs2_rate = ibs2 / comparable

    if exact_rate > 0.985 and ibs0_rate < 0.001:
        heuristic = "same_sample_or_monozygotic_twin"
    elif ibs0_rate < 0.005 and exact_rate > 0.70:
        heuristic = "possibly_first_degree_or_very_close"
    elif ibs0_rate < 0.02 and exact_rate >= 0.60:
        heuristic = "possibly_close_relatives"
    elif exact_rate > 0.45:
        heuristic = "possibly_related_but_not_close"
    else:
        heuristic = "no_strong_signal_of_close_relatedness"

    return {
        "subject_a": subject_a,
        "subject_b": subject_b,
        "shared_snps": len(rows),
        "comparable_snps": comparable,
        "exact_match_count": exact_matches,
        "exact_match_rate": exact_rate,
        "ibs0_count": ibs0,
        "ibs1_count": ibs1,
        "ibs2_count": ibs2,
        "ibs0_rate": ibs0_rate,
        "ibs1_rate": ibs1_rate,
        "ibs2_rate": ibs2_rate,
        "heuristic_relationship": heuristic,
        "interpretation_warning": (
            "Relatedness is estimated from raw chip overlap using a simple IBS heuristic. "
            "Treat it as exploratory only, especially across different chips or missingness levels."
        ),
    }
