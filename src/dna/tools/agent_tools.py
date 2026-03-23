"""Tool functions designed to be called by any AI agent.

Each function has a clear docstring, accepts simple types, and returns
dicts/lists that are easy to serialize. The active subject from config.yaml
is used as default when no subject is specified.
"""

from dna.config import get_active_subject, get_subject_profile, list_subjects
from dna.db.query import (
    chromosome_summary,
    compare_snp,
    compare_subjects,
    count_snps,
    get_snp,
    search_snps,
)


def who_am_i() -> dict:
    """Return the active subject's profile (name, sex, date of birth, etc.)."""
    name = get_active_subject()
    profile = get_subject_profile(name)
    return {"subject_key": name, **profile}


def list_all_subjects() -> dict:
    """List all available subjects with their profiles."""
    active = get_active_subject()
    subjects = list_subjects()
    return {"active": active, "subjects": subjects}


def lookup_snp(rsid: str, subject: str | None = None) -> dict:
    """Look up a specific SNP by its rsid (e.g. 'rs1234').

    Args:
        rsid: The SNP identifier (e.g. 'rs53576')
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with rsid, chromosome, position, genotype. Or not_found message.
    """
    result = get_snp(rsid, subject)
    if result is None:
        return {"error": f"SNP {rsid} not found", "subject": subject or get_active_subject()}
    return {**result, "subject": subject or get_active_subject()}


def search(
    chromosome: str | None = None,
    position_start: int | None = None,
    position_end: int | None = None,
    genotype: str | None = None,
    rsid_pattern: str | None = None,
    subject: str | None = None,
    limit: int = 100,
) -> dict:
    """Search SNPs with flexible filters.

    Args:
        chromosome: Filter by chromosome (e.g. '1', '22', 'X', 'MT')
        position_start: Minimum base pair position
        position_end: Maximum base pair position
        genotype: Filter by exact genotype (e.g. 'AA', 'CT')
        rsid_pattern: SQL LIKE pattern for rsid (e.g. 'rs53%')
        subject: Subject key. Uses active subject if not specified.
        limit: Max results (default 100)

    Returns:
        Dict with results list and total count.
    """
    results = search_snps(
        chromosome=chromosome,
        position_start=position_start,
        position_end=position_end,
        genotype=genotype,
        rsid_pattern=rsid_pattern,
        subject=subject,
        limit=limit,
    )
    return {
        "subject": subject or get_active_subject(),
        "count": len(results),
        "results": results,
    }


def get_stats(subject: str | None = None) -> dict:
    """Get summary statistics: total SNPs and per-chromosome breakdown.

    Args:
        subject: Subject key. Uses active subject if not specified.
    """
    subject = subject or get_active_subject()
    total = count_snps(subject)
    by_chrom = chromosome_summary(subject)
    return {"subject": subject, "total_snps": total, "chromosomes": by_chrom}


def compare_variant(rsid: str, subject_a: str, subject_b: str) -> dict:
    """Compare a specific SNP between two subjects.

    Args:
        rsid: The SNP identifier
        subject_a: First subject key
        subject_b: Second subject key
    """
    return compare_snp(rsid, subject_a, subject_b)


def compare(
    subject_a: str,
    subject_b: str,
    only_different: bool = True,
    chromosome: str | None = None,
    limit: int = 100,
) -> dict:
    """Compare all SNPs between two subjects.

    Args:
        subject_a: First subject key
        subject_b: Second subject key
        only_different: If True, only return SNPs where genotypes differ
        chromosome: Optional chromosome filter
        limit: Max results
    """
    results = compare_subjects(
        subject_a=subject_a,
        subject_b=subject_b,
        only_different=only_different,
        chromosome=chromosome,
        limit=limit,
    )
    return {
        "subject_a": subject_a,
        "subject_b": subject_b,
        "only_different": only_different,
        "count": len(results),
        "results": results,
    }
