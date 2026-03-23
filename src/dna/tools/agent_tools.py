"""Tool functions designed to be called by any AI agent.

Each function has a clear docstring, accepts simple types, and returns
dicts/lists that are easy to serialize. The active subject from config.yaml
is used as default when no subject is specified.
"""

from dna.analysis.panels import (
    analyze_all_panels,
    analyze_panel,
    get_risk_summary,
    list_panels,
)
from dna.api.annotator import annotate_snp_sync
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


def annotate(
    rsid: str,
    subject: str | None = None,
    sources: list[str] | None = None,
    force_refresh: bool = False,
) -> dict:
    """Annotate a SNP with info from online databases (SNPedia, ClinVar, Ensembl).

    Fetches gene name, clinical significance, associated conditions,
    population frequencies, and more. Results are cached locally.

    Args:
        rsid: SNP identifier (e.g. 'rs1234')
        subject: Subject key (for cache DB). Uses active subject if not specified.
        sources: List of sources to query. Options: 'snpedia', 'clinvar', 'ensembl'.
                 Defaults to all three.
        force_refresh: If True, bypass cache and re-fetch from online.

    Returns:
        Dict with merged annotations: gene, clinical_significance, condition,
        summary, population_frequency, and per-source details.
    """
    return annotate_snp_sync(rsid, subject, sources, force_refresh)


def annotate_my_snp(rsid: str, sources: list[str] | None = None) -> dict:
    """Look up a SNP in the active subject's genome AND annotate it from online databases.

    Combines genotype lookup with annotation in a single call.

    Args:
        rsid: SNP identifier (e.g. 'rs1234')
        sources: Which online sources to query. Defaults to all.

    Returns:
        Dict with genotype from the subject's DNA plus annotations from online DBs.
    """
    subject = get_active_subject()
    genotype_data = get_snp(rsid, subject)
    annotation_data = annotate_snp_sync(rsid, subject, sources)

    return {
        "rsid": rsid,
        "subject": subject,
        "genotype": genotype_data["genotype"] if genotype_data else None,
        "chromosome": genotype_data["chromosome"] if genotype_data else None,
        "position": genotype_data["position"] if genotype_data else None,
        "found_in_genome": genotype_data is not None,
        "annotation": annotation_data,
    }


def available_panels() -> list[dict]:
    """List all available analysis panels.

    Returns:
        List of panels with id, name, description, category, and variant count.
    """
    return list_panels()


def run_panel(panel_id: str, subject: str | None = None) -> dict:
    """Run a curated SNP panel against a subject's genome.

    Panels are predefined sets of well-studied variants grouped by theme
    (e.g. pharmacogenomics, cardiovascular, nutrigenomics, traits, wellness).

    Args:
        panel_id: Panel identifier. Use available_panels() to see options.
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with per-variant genotype, effect, and interpretation.
    """
    return analyze_panel(panel_id, subject)


def run_all_panels(subject: str | None = None) -> list[dict]:
    """Run all available panels against a subject's genome.

    Args:
        subject: Subject key. Uses active subject if not specified.

    Returns:
        List of panel results.
    """
    return analyze_all_panels(subject)


def notable_findings(subject: str | None = None) -> list[dict]:
    """Get a summary of non-normal findings across all panels.

    Scans all panels and returns only variants where the subject carries
    a noteworthy genotype (not 'normal' or 'lower_risk').

    Args:
        subject: Subject key. Uses active subject if not specified.

    Returns:
        List of notable variants with panel, gene, trait, genotype, effect, description.
    """
    return get_risk_summary(subject)
