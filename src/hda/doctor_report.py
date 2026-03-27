"""Doctor-facing report export."""

from datetime import date
from pathlib import Path
import html

from hda.analysis.panels import analyze_panel, list_panels
from hda.config import get_active_subject, get_subject_profile
from hda.context_store import _parse_inline_metadata, _split_blocks, read_context
from hda.context_validator import validate_context


def _pdf_safe_text(text: str) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "−": "-",
        "‑": "-",
        "→": "->",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _escape(text: str) -> str:
    return html.escape(_pdf_safe_text(text)).replace("\n", "<br/>")


def _clean_paragraphs(text: str) -> list[str]:
    text = text.replace("**", "")
    lines = [line.rstrip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if stripped.startswith("- "):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            paragraphs.append(stripped)
            continue
        current.append(stripped)

    if current:
        paragraphs.append(" ".join(current).strip())
    return paragraphs


def _extract_summary(content: str) -> str:
    marker = "### Summary"
    if marker not in content:
        paragraphs = _clean_paragraphs(content)
        return paragraphs[0] if paragraphs else ""
    tail = content.split(marker, 1)[1].lstrip()
    if "### " in tail:
        tail = tail.split("### ", 1)[0].rstrip()
    paragraphs = _clean_paragraphs(tail)
    return paragraphs[0] if paragraphs else ""


def _get_profile_sections(subject: str) -> dict[str, str]:
    profile = read_context(subject, "profile_summary")
    _, sections = _split_blocks(profile["content"] or "", 2)
    return {section["heading"]: section["content"].strip() for section in sections}


def _get_findings_blocks(subject: str) -> list[dict]:
    findings = read_context(subject, "findings")
    _, blocks = _split_blocks(findings["content"] or "", 2)
    parsed = []
    for block in blocks:
        metadata, body = _parse_inline_metadata(block["content"])
        parsed.append(
            {
                "id": metadata.get("finding_id") or block["heading"],
                "heading": block["heading"],
                "metadata": metadata,
                "content": body,
            }
        )
    return parsed


def _get_health_actions(subject: str) -> dict[str, dict]:
    actions = read_context(subject, "health_actions")
    _, priority_sections = _split_blocks(actions["content"] or "", 2)
    parsed = {}
    for priority in priority_sections:
        _, blocks = _split_blocks(priority["content"], 3)
        for block in blocks:
            metadata, body = _parse_inline_metadata(block["content"])
            action_id = metadata.get("action_id")
            if not action_id:
                continue
            parsed[action_id] = {
                "title": block["heading"],
                "priority": priority["heading"],
                "metadata": metadata,
                "content": body.strip(),
            }
    return parsed


def _verified_panel_findings(subject: str) -> list[dict]:
    verified_ids = [
        panel["id"]
        for panel in list_panels()
        if panel.get("review_status") == "verified" and panel.get("id") != "traits"
    ]
    findings = []
    for panel_id in verified_ids:
        result = analyze_panel(panel_id, subject)
        panel_lines = []
        for row in result.get("results", []):
            effect = row.get("effect")
            if not row.get("found") or effect in {"normal", "typical", "lower_risk", "efficient", "protective"}:
                continue
            description = row.get("description") or row.get("trait") or effect
            panel_lines.append(f"{row.get('gene')}: {description}")
        for row in result.get("composite_results", []):
            effect = row.get("effect")
            if not row.get("found") or effect in {"normal", "typical", "lower_risk", "efficient", "protective"}:
                continue
            description = row.get("description") or row.get("trait") or effect
            panel_lines.append(f"{row.get('gene')}: {description}")
        if panel_lines:
            findings.append({"panel_name": result["panel_name"], "items": panel_lines})
    return findings


def export_doctor_report(subject: str | None = None, output_path: str | None = None) -> str:
    """Export a simple doctor-facing PDF report."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise RuntimeError(
            "PDF export requires reportlab. Install it with '.\\.venv\\Scripts\\python.exe -m pip install reportlab'."
        ) from e

    subject = subject or get_active_subject()
    profile = {"subject_key": subject, **get_subject_profile(subject)}
    subject = profile["subject_key"]
    validation = validate_context(subject, apply=False)
    profile_sections = _get_profile_sections(subject)
    findings_blocks = _get_findings_blocks(subject)
    health_actions = _get_health_actions(subject)
    verified_findings = _verified_panel_findings(subject)

    output = Path(output_path) if output_path else Path("output/pdf") / f"doctor-report-{subject}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=42,
    )

    regular_font = Path(r"C:\Windows\Fonts\arial.ttf")
    bold_font = Path(r"C:\Windows\Fonts\arialbd.ttf")
    if regular_font.exists() and bold_font.exists():
        pdfmetrics.registerFont(TTFont("HDAArial", str(regular_font)))
        pdfmetrics.registerFont(TTFont("HDAArial-Bold", str(bold_font)))
        base_font = "HDAArial"
        base_bold = "HDAArial-Bold"
    else:
        base_font = "Helvetica"
        base_bold = "Helvetica-Bold"

    styles = getSampleStyleSheet()
    styles["Title"].fontName = base_bold
    styles["BodyText"].fontName = base_font
    styles["Heading2"].fontName = base_bold
    styles["Heading3"].fontName = base_bold
    styles.add(
        ParagraphStyle(
            name="SmallBody",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName=base_bold,
            fontSize=14,
            leading=18,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MinorTitle",
            parent=styles["Heading3"],
            fontName=base_bold,
            fontSize=11,
            leading=14,
            spaceAfter=4,
        )
    )

    story = []
    story.append(Paragraph("Health Summary For Clinical Discussion", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            _escape(
                f"Generated on {date.today().isoformat()} from HDA subject memory, verified core panels, and explicitly labeled exploratory context."
            ),
            styles["SmallBody"],
        )
    )
    story.append(Spacer(1, 12))

    info_rows = [
        ["Patient", str(profile.get("name", subject))],
        ["Subject key", subject],
        ["Sex", str(profile.get("sex", "—"))],
        ["Date of birth", str(profile.get("date_of_birth", "—"))],
        ["Genome source", str(profile.get("source_format", "—"))],
        ["Chip", str(profile.get("chip", "—"))],
    ]
    table = Table(info_rows, colWidths=[110, 360])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), base_font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Current Clinical Context", styles["SectionTitle"]))
    for heading in ["Overview", "Cardiovascular", "Sleep & Recovery", "Nutrition"]:
        section_body = profile_sections.get(heading)
        if not section_body:
            continue
        story.append(Paragraph(_escape(heading), styles["MinorTitle"]))
        for paragraph in _clean_paragraphs(section_body):
            story.append(Paragraph(_escape(paragraph), styles["SmallBody"]))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Verified Core Genetic Findings", styles["SectionTitle"]))
    if not verified_findings:
        story.append(Paragraph("No non-typical findings found across verified core panels.", styles["SmallBody"]))
    else:
        for panel in verified_findings:
            story.append(Paragraph(_escape(panel["panel_name"]), styles["MinorTitle"]))
            for item in panel["items"]:
                story.append(Paragraph(_escape(f"- {item}"), styles["SmallBody"]))
            story.append(Spacer(1, 6))

    story.append(Paragraph("Suggested Medical Follow-up", styles["SectionTitle"]))
    for action_id in [
        "sleep_apnea_evaluation",
        "palpitations_follow_up",
        "hypertension_management",
        "cardiovascular_screening",
        "homocysteine_monitoring",
        "psa_contextual_screening",
    ]:
        action = health_actions.get(action_id)
        if not action:
            continue
        story.append(Paragraph(_escape(f"{action['title']} ({action['priority']})"), styles["MinorTitle"]))
        for paragraph in _clean_paragraphs(action["content"]):
            story.append(Paragraph(_escape(paragraph), styles["SmallBody"]))
            story.append(Spacer(1, 3))

    exploratory_blocks = [
        block
        for block in findings_blocks
        if block["metadata"].get("panel_basis") in {"exploratory", "inferred"}
    ]
    if exploratory_blocks:
        story.append(Paragraph("Exploratory Or Contextual Themes", styles["SectionTitle"]))
        story.append(
            Paragraph(
                _escape(
                    "The items below are not verified core findings. They may still be useful as clinical context or discussion prompts, but should not be treated as established genetic conclusions."
                ),
                styles["SmallBody"],
            )
        )
        story.append(Spacer(1, 6))
        for block in exploratory_blocks:
            story.append(Paragraph(_escape(block["heading"]), styles["MinorTitle"]))
            summary = _extract_summary(block["content"])
            if summary:
                story.append(Paragraph(_escape(summary), styles["SmallBody"]))
                story.append(Spacer(1, 3))

    if validation["issues"]:
        story.append(Paragraph("Context Validation Notes", styles["SectionTitle"]))
        for issue in validation["issues"]:
            story.append(Paragraph(_escape(f"- {issue['section']}: {issue['message']}"), styles["SmallBody"]))

    doc.build(story)
    return str(output)
