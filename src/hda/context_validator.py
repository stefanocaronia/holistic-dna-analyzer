"""Validation helpers for subject context documents."""

import re

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

SEMANTIC_THEME_KEYWORDS = {
    "dopamina": ("dopamina", "reward", "stimol", "nicotina"),
    "stress": ("stress", "cortis", "seroton"),
    "sonno": ("sonno", "apnea", "russ", "recuper"),
    "cardiovascular": ("cardio", "pression", "ipertension", "omociste", "psa"),
}


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _summary_excerpt(body: str) -> str:
    if "### Summary" not in body:
        return _normalize_text(body)[:180]
    tail = body.split("### Summary", 1)[1].lstrip()
    if "### " in tail:
        tail = tail.split("### ", 1)[0]
    return _normalize_text(tail)[:180]


def _mentioned_themes(text: str) -> set[str]:
    lower = text.lower()
    themes = set()
    for theme, keywords in SEMANTIC_THEME_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            themes.add(theme)
    return themes


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
    finding_ids = set()
    seen_finding_signatures = {}
    finding_themes = set()
    for block in finding_blocks:
        metadata, body = _parse_inline_metadata(block["content"])
        finding_id = metadata.get("finding_id") or block["heading"]
        panel_basis = metadata.get("panel_basis")
        full_text = f"{block['heading']}\n{body}"
        finding_ids.add(finding_id)
        finding_themes.update(_mentioned_themes(full_text))

        signature = (block["heading"].strip().lower(), _summary_excerpt(body))
        if signature in seen_finding_signatures:
            issues.append(
                {
                    "severity": "warning",
                    "section": "findings",
                    "block_id": finding_id,
                    "message": (
                        f"Finding block appears semantically duplicated with '{seen_finding_signatures[signature]}'. "
                        "Consolidate instead of keeping parallel variants of the same finding."
                    ),
                    "fixable": False,
                }
            )
        else:
            seen_finding_signatures[signature] = finding_id

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
    action_themes = set()
    for priority_section in priority_sections:
        _, action_blocks = _split_blocks(priority_section["content"], 3)
        for block in action_blocks:
            metadata, body = _parse_inline_metadata(block["content"])
            text = f"{block['heading']}\n{body}".lower()
            action_themes.update(_mentioned_themes(text))

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

            references = set(re.findall(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b", body))
            missing_references = sorted(ref for ref in references if ref not in finding_ids)
            if missing_references:
                issues.append(
                    {
                        "severity": "warning",
                        "section": "health_actions",
                        "block_id": metadata.get("action_id") or block["heading"],
                        "message": (
                            "Health action references missing finding ids: "
                            + ", ".join(missing_references)
                            + "."
                        ),
                        "fixable": False,
                    }
                )

    profile_themes = _mentioned_themes(profile_summary["content"] or "")
    missing_from_knowledge = sorted(theme for theme in profile_themes if theme not in finding_themes)
    if missing_from_knowledge:
        issues.append(
            {
                "severity": "warning",
                "section": "profile_summary",
                "block_id": None,
                "message": (
                    "Profile summary mentions themes without a matching findings block: "
                    + ", ".join(missing_from_knowledge)
                    + "."
                ),
                "fixable": False,
            }
        )

    missing_from_actions = sorted(theme for theme in finding_themes if theme in profile_themes and theme not in action_themes)
    if missing_from_actions:
        issues.append(
            {
                "severity": "warning",
                "section": "health_actions",
                "block_id": None,
                "message": (
                    "Important profile/finding themes are not reflected in health actions: "
                    + ", ".join(missing_from_actions)
                    + "."
                ),
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
