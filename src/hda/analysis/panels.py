"""Panel analysis engine — run curated SNP panels against a subject's genome."""

from pathlib import Path

import yaml

from hda.config import DATA_DIR, get_active_subject
from hda.db.query import get_snp

PANELS_DIR = DATA_DIR / "panels"
PANEL_SUFFIX_REVIEW_STATUS = {
    ".experimental": "exploratory",
    ".draft": "draft",
}
PANEL_ID_ALIASES = {
    "nutrigenomics": "nutrition_metabolism",
    "nutrition_advanced": "nutrition_micronutrients",
}


def _split_panel_filename(path: Path) -> tuple[str, str | None]:
    """Split a panel filename into base id and optional status suffix."""
    stem = path.stem
    for suffix, review_status in PANEL_SUFFIX_REVIEW_STATUS.items():
        if stem.endswith(suffix):
            return stem.removesuffix(suffix), review_status
    return stem, None


def _panel_metadata(panel_id: str, data: dict, inferred_review_status: str | None = None) -> dict:
    """Extract common panel metadata exposed to tools and UI."""
    review_status = data.get("review_status") or inferred_review_status or "verified"
    status = data.get("status")
    if not status:
        status = "core" if inferred_review_status is None else "custom"

    return {
        "id": panel_id,
        "name": data.get("name", panel_id),
        "description": data.get("description", ""),
        "category": data.get("category", ""),
        "status": status,
        "review_status": review_status,
        "version": data.get("version"),
        "last_reviewed": data.get("last_reviewed"),
        "summary": data.get("summary", ""),
        "sources": data.get("sources", []),
        "limitations": data.get("limitations", []),
        "variant_count": len(data.get("variants", [])),
    }


def resolve_panel_id(panel_id: str) -> str:
    """Map legacy panel ids to their canonical names."""
    return PANEL_ID_ALIASES.get(panel_id, panel_id)


def list_panels() -> list[dict]:
    """List all available analysis panels."""
    panels = []
    for f in sorted(PANELS_DIR.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        panel_id, inferred_review_status = _split_panel_filename(f)
        panels.append(_panel_metadata(panel_id, data, inferred_review_status))
    return panels


def load_panel(panel_id: str) -> dict:
    """Load a panel definition from YAML."""
    canonical_id = resolve_panel_id(panel_id)
    candidates = [PANELS_DIR / f"{canonical_id}.yaml"]
    candidates.extend(PANELS_DIR / f"{canonical_id}{suffix}.yaml" for suffix in PANEL_SUFFIX_REVIEW_STATUS)

    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError(f"Panel '{panel_id}' not found. Available: {[p['id'] for p in list_panels()]}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    _, inferred_review_status = _split_panel_filename(path)
    metadata = _panel_metadata(canonical_id, data, inferred_review_status)
    return {**data, **metadata}


def analyze_panel(panel_id: str, subject: str | None = None) -> dict:
    """Run a panel analysis against a subject's genome.

    Args:
        panel_id: Panel identifier (e.g. 'pharmacogenomics', 'cardiovascular')
        subject: Subject key. Uses active subject if not specified.

    Returns:
        Dict with panel info and per-variant results including genotype and interpretation.
    """
    subject = subject or get_active_subject()
    canonical_id = resolve_panel_id(panel_id)
    panel = load_panel(panel_id)

    results = []
    found_count = 0
    for variant in panel.get("variants", []):
        rsid = variant["rsid"]
        snp_data = get_snp(rsid, subject)

        entry = {
            "rsid": rsid,
            "gene": variant.get("gene", ""),
            "trait": variant.get("trait", ""),
            "genotype": None,
            "effect": None,
            "description": None,
            "found": False,
        }

        if snp_data:
            genotype = snp_data["genotype"]
            entry["genotype"] = genotype
            entry["found"] = True
            found_count += 1

            # Look up interpretation — try direct match first, then aliases
            genotypes = variant.get("genotypes", {})
            aliases = variant.get("aliases", {})

            interpretation = genotypes.get(genotype)
            if not interpretation and genotype in aliases:
                interpretation = genotypes.get(aliases[genotype])
            # Try reversed genotype (e.g. TC → CT)
            if not interpretation and len(genotype) == 2:
                reversed_gt = genotype[1] + genotype[0]
                interpretation = genotypes.get(reversed_gt)
                if not interpretation and reversed_gt in aliases:
                    interpretation = genotypes.get(aliases[reversed_gt])

            if interpretation:
                entry["effect"] = interpretation.get("effect")
                entry["description"] = interpretation.get("description")
            else:
                entry["description"] = f"Genotype {genotype} not in panel definitions."

        results.append(entry)

    return {
        "panel_id": canonical_id,
        "requested_panel_id": panel_id,
        "panel_name": panel.get("name", canonical_id),
        "description": panel.get("description", ""),
        "category": panel.get("category", ""),
        "status": panel.get("status", "unknown"),
        "review_status": panel.get("review_status", "unknown"),
        "version": panel.get("version"),
        "last_reviewed": panel.get("last_reviewed"),
        "summary": panel.get("summary", ""),
        "sources": panel.get("sources", []),
        "limitations": panel.get("limitations", []),
        "subject": subject,
        "total_variants": len(results),
        "found_in_genome": found_count,
        "results": results,
    }


def analyze_all_panels(subject: str | None = None) -> list[dict]:
    """Run all available panels against a subject's genome."""
    subject = subject or get_active_subject()
    panels = list_panels()
    return [analyze_panel(p["id"], subject) for p in panels]


def get_risk_summary(subject: str | None = None) -> list[dict]:
    """Get a summary of notable findings across all panels.

    Returns only variants where the subject carries a non-normal effect.
    """
    subject = subject or get_active_subject()
    all_results = analyze_all_panels(subject)
    notable = []

    for panel in all_results:
        for result in panel["results"]:
            if not result["found"]:
                continue
            effect = result.get("effect", "")
            if effect and effect not in ("normal", "lower_risk", "no_e4", "no_e2"):
                notable.append({
                    "panel": panel["panel_name"],
                    "panel_review_status": panel.get("review_status", "unknown"),
                    "rsid": result["rsid"],
                    "gene": result["gene"],
                    "trait": result["trait"],
                    "genotype": result["genotype"],
                    "effect": effect,
                    "description": result["description"],
                })

    return notable
