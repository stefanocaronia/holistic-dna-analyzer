"""Validation helpers for subject context documents."""

from hda.analysis.panels import list_panels
from hda.context_store import (
    _parse_inline_metadata,
    _split_blocks,
    read_context,
    replace_context_section,
)


CAVEAT_KEYWORDS = (
    "esplor",
    "non diagnostic",
    "non-diagnostic",
    "non verified",
    "plausibil",
    "caveat",
    "inferred",
    "non deriva da un finding verified",
)

NEURODEVELOPMENTAL_KEYWORDS = (
    "adhd",
    "audhd",
    "autism",
    "autismo",
    "asd",
    "neuropsichiatr",
)


def _has_caveat(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in CAVEAT_KEYWORDS)


def _profile_summary_disclaimer() -> str:
    return (
        "Questo profilo integra anche finding esplorativi o inferiti, soprattutto nelle aree "
        "neurocognitive e di stress. I punti su dopamina/ADHD-like, asse serotonina-cortisolo, "
        "AuDHD e lettura profonda vs smartphone servono come lenti interpretative utili, ma non "
        "vanno trattati come finding verified o come diagnosi cliniche."
    )


def validate_context(subject: str | None = None, apply: bool = False) -> dict:
    """Validate context documents for structural and evidence-basis issues."""
    context = read_context(subject)
    findings = next(section for section in context["sections"] if section["id"] == "findings")
    profile_summary = next(section for section in context["sections"] if section["id"] == "profile_summary")
    health_actions = next(section for section in context["sections"] if section["id"] == "health_actions")

    issues = []
    applied_fixes = []

    verified_panels = sorted(panel["id"] for panel in list_panels() if panel.get("review_status") == "verified")
    exploratory_panels = sorted(panel["id"] for panel in list_panels() if panel.get("review_status") != "verified")

    _, finding_blocks = _split_blocks(findings["content"] or "", 2)
    has_non_verified_findings = False
    for block in finding_blocks:
        metadata, body = _parse_inline_metadata(block["content"])
        finding_id = metadata.get("finding_id") or block["heading"]
        panel_basis = metadata.get("panel_basis")
        full_text = f"{block['heading']}\n{body}"

        if not panel_basis:
            issues.append(
                {
                    "severity": "warning",
                    "section": "findings",
                    "block_id": finding_id,
                    "message": "Finding block is missing panel_basis metadata.",
                    "fixable": False,
                }
            )
            continue

        if panel_basis in {"exploratory", "inferred", "mixed"}:
            has_non_verified_findings = True

        if panel_basis in {"exploratory", "inferred"} and not _has_caveat(full_text):
            issues.append(
                {
                    "severity": "warning",
                    "section": "findings",
                    "block_id": finding_id,
                    "message": f"Finding block has panel_basis='{panel_basis}' but lacks an explicit cautionary caveat.",
                    "fixable": False,
                }
            )

    if has_non_verified_findings and "## Interpretation Boundaries" not in (profile_summary["content"] or ""):
        issue = {
            "severity": "warning",
            "section": "profile_summary",
            "message": "Profile summary contains or depends on non-verified findings but lacks an explicit interpretation-boundaries section.",
            "fixable": True,
        }
        issues.append(issue)
        if apply:
            replace_context_section("profile_summary", "Interpretation Boundaries", _profile_summary_disclaimer(), subject)
            applied_fixes.append(
                {
                    "section": "profile_summary",
                    "message": "Added Interpretation Boundaries section.",
                }
            )

    _, priority_sections = _split_blocks(health_actions["content"] or "", 2)
    for priority_section in priority_sections:
        _, action_blocks = _split_blocks(priority_section["content"], 3)
        for block in action_blocks:
            metadata, body = _parse_inline_metadata(block["content"])
            text = f"{block['heading']}\n{body}".lower()

            if "action_id" not in metadata or "status" not in metadata:
                issues.append(
                    {
                        "severity": "warning",
                        "section": "health_actions",
                        "block_id": block["heading"],
                        "message": "Health action block is missing action_id or status metadata.",
                        "fixable": False,
                    }
                )

            if any(keyword in text for keyword in NEURODEVELOPMENTAL_KEYWORDS) and not _has_caveat(text):
                issues.append(
                    {
                        "severity": "warning",
                        "section": "health_actions",
                        "block_id": metadata.get("action_id") or block["heading"],
                        "message": "Neurodevelopmental action references exploratory material without an explicit cautionary caveat.",
                        "fixable": False,
                    }
                )

    return {
        "subject": context["subject"],
        "verified_panels": verified_panels,
        "non_verified_panels": exploratory_panels,
        "issue_count": len(issues),
        "issues": issues,
        "applied_fixes": applied_fixes,
    }
