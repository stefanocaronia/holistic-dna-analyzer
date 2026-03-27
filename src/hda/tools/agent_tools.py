"""Tool functions designed to be called by any AI agent.

Each function has a clear docstring, accepts simple types, and returns
dicts/lists that are easy to serialize. The active subject from config.yaml
is used as default when no subject is specified.
"""

__all__ = [
    "append_context_entry",
    "archive_context_block",
    "annotate",
    "annotate_my_snp",
    "available_panels",
    "compare",
    "compare_panel",
    "compare_variant",
    "estimate_relatedness",
    "export_doctor_report",
    "get_stats",
    "list_context_sections",
    "list_all_subjects",
    "lookup_snp",
    "move_context_block",
    "migrate_context",
    "notable_findings",
    "read_context_block",
    "replace_context_entry",
    "replace_context_section",
    "read_context",
    "validate_context",
    "run_all_panels",
    "run_panel",
    "search",
    "upsert_context_block",
    "write_context_document",
    "who_am_i",
]

from hda.analysis.panels import (
    analyze_all_panels,
    analyze_panel,
    get_risk_summary,
    list_panels,
)
from hda.api.annotator import annotate_snp_sync
from hda.config import get_active_subject, get_subject_profile, list_subjects
from hda.context_store import append_context_entry as append_context_entry_data
from hda.context_store import archive_context_block as archive_context_block_data
from hda.context_store import list_context_sections as list_context_sections_data
from hda.context_store import move_context_block as move_context_block_data
from hda.context_store import read_context as read_context_data
from hda.context_store import read_context_block as read_context_block_data
from hda.context_store import replace_context_entry as replace_context_entry_data
from hda.context_store import replace_context_section as replace_context_section_data
from hda.context_store import upsert_context_block as upsert_context_block_data
from hda.context_store import write_context_document as write_context_document_data
from hda.context_migrator import migrate_context as migrate_context_data
from hda.context_validator import validate_context as validate_context_data
from hda.doctor_report import export_doctor_report as export_doctor_report_data
from hda.db.query import (
    chromosome_summary,
    estimate_relatedness as estimate_subject_relatedness,
    compare_snp,
    compare_subjects,
    count_snps,
    get_snp,
    search_snps,
)


def _panel_disclaimer_fields(review_status: str | None) -> dict:
    """Return explicit disclaimer metadata for agent-facing panel results."""
    review_status = review_status or "unknown"
    requires_disclaimer = review_status != "verified"
    warning = None
    if requires_disclaimer:
        warning = (
            f"This panel has review_status='{review_status}' and is not part of the verified core set. "
            "Treat any interpretation as exploratory and recommend professional review for important decisions."
        )
    return {
        "requires_disclaimer": requires_disclaimer,
        "interpretation_warning": warning,
    }


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


def write_context_document(section: str, content: str, subject: str | None = None) -> dict:
    """Replace an entire context document while preserving frontmatter."""
    return write_context_document_data(section, content, subject)


def replace_context_section(section: str, heading: str, content: str, subject: str | None = None) -> dict:
    """Replace or append a `##` section inside a maintained context document."""
    return replace_context_section_data(section, heading, content, subject)


def list_context_sections(subject: str | None = None) -> dict:
    """List the standard persistent-memory sections for a subject."""
    return list_context_sections_data(subject)


def read_context(subject: str | None = None, section: str | None = None) -> dict:
    """Read one or all context sections for a subject."""
    return read_context_data(subject, section)


def read_context_block(section: str, block_id: str, subject: str | None = None) -> dict:
    """Read one structured block from findings, health_actions, or session_notes."""
    return read_context_block_data(section, block_id, subject)


def upsert_context_block(
    section: str,
    block_id: str,
    content: str,
    subject: str | None = None,
    metadata: dict | None = None,
    title: str | None = None,
    destination: str | None = None,
) -> dict:
    """Upsert a structured block inside findings or health_actions."""
    return upsert_context_block_data(section, block_id, content, subject, metadata, title, destination)


def move_context_block(section: str, block_id: str, destination: str, subject: str | None = None) -> dict:
    """Move a structured block to another destination."""
    return move_context_block_data(section, block_id, destination, subject)


def migrate_context(
    subject: str | None = None,
    section: str | None = None,
    apply: bool = False,
    backup: bool = True,
    backup_root: str | None = None,
) -> dict:
    """Plan or apply deterministic migrations to the current context schema."""
    return migrate_context_data(subject, section, apply, backup, backup_root)


def archive_context_block(section: str, block_id: str, subject: str | None = None) -> dict:
    """Archive a structured block in findings or health_actions."""
    return archive_context_block_data(section, block_id, subject)


def append_context_entry(
    section: str,
    title: str,
    content: str,
    subject: str | None = None,
    entry_date: str | None = None,
) -> dict:
    """Append a dated chronological entry to session_notes."""
    return append_context_entry_data(section, title, content, subject, entry_date)


def replace_context_entry(section: str, heading: str, content: str, subject: str | None = None) -> dict:
    """Replace an existing chronological entry in session_notes."""
    return replace_context_entry_data(section, heading, content, subject)


def validate_context(subject: str | None = None, apply: bool = False) -> dict:
    """Validate context documents against evidence-basis rules and optional fixes."""
    return validate_context_data(subject, apply)


def export_doctor_report(subject: str | None = None, output_path: str | None = None) -> str:
    """Export a simple doctor-facing PDF report."""
    return export_doctor_report_data(subject, output_path)


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


def compare_panel(panel_id: str, subject_a: str, subject_b: str) -> dict:
    """Compare a curated panel between two subjects."""
    panel_a = analyze_panel(panel_id, subject_a)
    panel_b = analyze_panel(panel_id, subject_b)

    def _index_rows(rows: list[dict], key: str) -> dict[str, dict]:
        return {row[key]: row for row in rows}

    by_rsid_a = _index_rows(panel_a["results"], "rsid")
    by_rsid_b = _index_rows(panel_b["results"], "rsid")

    compared_results = []
    same_effect = 0
    different_effect = 0
    missing = 0

    for rsid in by_rsid_a:
        row_a = by_rsid_a[rsid]
        row_b = by_rsid_b[rsid]
        if not row_a["found"] or not row_b["found"]:
            comparison = "missing"
            missing += 1
        elif row_a.get("effect") == row_b.get("effect"):
            comparison = "same_effect"
            same_effect += 1
        else:
            comparison = "different_effect"
            different_effect += 1

        compared_results.append(
            {
                "rsid": rsid,
                "gene": row_a["gene"],
                "trait": row_a["trait"],
                "subject_a_genotype": row_a.get("genotype"),
                "subject_b_genotype": row_b.get("genotype"),
                "subject_a_effect": row_a.get("effect"),
                "subject_b_effect": row_b.get("effect"),
                "comparison": comparison,
            }
        )

    composite_a = _index_rows(panel_a.get("composite_results", []), "id")
    composite_b = _index_rows(panel_b.get("composite_results", []), "id")
    compared_composites = []
    for composite_id in composite_a:
        row_a = composite_a[composite_id]
        row_b = composite_b[composite_id]
        if not row_a["found"] or not row_b["found"]:
            comparison = "missing"
        elif row_a.get("effect") == row_b.get("effect"):
            comparison = "same_effect"
        else:
            comparison = "different_effect"

        compared_composites.append(
            {
                "id": composite_id,
                "gene": row_a["gene"],
                "trait": row_a["trait"],
                "components": row_a.get("components", []),
                "subject_a_genotype": row_a.get("label") or row_a.get("genotype"),
                "subject_b_genotype": row_b.get("label") or row_b.get("genotype"),
                "subject_a_effect": row_a.get("effect"),
                "subject_b_effect": row_b.get("effect"),
                "comparison": comparison,
            }
        )

    return {
        "panel_id": panel_a["panel_id"],
        "panel_name": panel_a["panel_name"],
        "review_status": panel_a["review_status"],
        "status": panel_a["status"],
        "subject_a": subject_a,
        "subject_b": subject_b,
        "summary": {
            "same_effect_count": same_effect,
            "different_effect_count": different_effect,
            "missing_count": missing,
            "total_items": len(compared_results) + len(compared_composites),
        },
        "results": compared_results,
        "composite_results": compared_composites,
        **_panel_disclaimer_fields(panel_a.get("review_status")),
    }


def estimate_relatedness(subject_a: str, subject_b: str) -> dict:
    """Estimate rough genetic relatedness between two subjects."""
    return estimate_subject_relatedness(subject_a, subject_b)


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
        List of panels with id, name, description, category, review metadata,
        and explicit disclaimer fields for non-verified panels.
    """
    panels = []
    for panel in list_panels():
        panels.append({**panel, **_panel_disclaimer_fields(panel.get("review_status"))})
    return panels


def run_panel(panel_id: str, subject: str | None = None) -> dict:
    """Run a curated SNP panel against a subject's genome.

    Panels are predefined sets of well-studied variants grouped by theme
    (e.g. pharmacogenomics, cardiovascular, nutrition_metabolism, traits, wellness).

    Args:
        panel_id: Panel identifier. Use available_panels() to see options.
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with per-variant genotype, effect, and interpretation.
    """
    result = analyze_panel(panel_id, subject)
    return {**result, **_panel_disclaimer_fields(result.get("review_status"))}


def run_all_panels(subject: str | None = None) -> list[dict]:
    """Run all available panels against a subject's genome.

    Args:
        subject: Subject key. Uses active subject if not specified.

    Returns:
        List of panel results.
    """
    results = []
    for panel in analyze_all_panels(subject):
        results.append({**panel, **_panel_disclaimer_fields(panel.get("review_status"))})
    return results


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
