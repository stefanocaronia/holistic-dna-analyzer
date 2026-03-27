import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hda.doctor_report import _build_report_payload, export_doctor_report


class DoctorReportTests(unittest.TestCase):
    def _read_pdf_text(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _profile_context(self) -> dict[str, dict]:
        return {
            "profile_summary": {
                "content": (
                    "# Summary\n\n"
                    "## Overview\nGeneral overview.\n\n"
                    "## Sleep & Recovery\nSleep context.\n\n"
                    "## Lifestyle Interactions\nLifestyle note.\n\n"
                    "## Interpretation Boundaries\nExploratory claims should stay separate.\n"
                )
            },
            "clinical_context": {
                "content": (
                    "# Clinical Context\n\n"
                    "## Current Medications & Supplements\n"
                    "- Olmesartan 20 mg\n\n"
                    "## Family History\n"
                    "- Father with hypertension.\n"
                )
            },
            "findings": {
                "content": (
                    "# Findings\n\n"
                    "## Exploratory Theme\n\n"
                    "finding_id: exploratory_theme\n"
                    "panel_basis: exploratory\n\n"
                    "### Summary\n"
                    "Exploratory summary for discussion.\n"
                )
            },
            "health_actions": {
                "content": (
                    "# Actions\n\n"
                    "## Alta Priorità\n\n"
                    "### Sleep Apnea Evaluation\n\n"
                    "action_id: sleep_apnea_evaluation\n"
                    "status: active\n\n"
                    "Arrange medical evaluation.\n\n"
                    "## Bassa Priorità\n\n"
                    "### Archived Action\n\n"
                    "action_id: archived_action\n"
                    "status: archived\n\n"
                    "Should not appear.\n"
                )
            },
        }

    def test_build_report_payload_short_filters_exploratory_and_low_priority_content(self):
        contexts = self._profile_context()
        with patch("hda.doctor_report.get_subject_profile", return_value={"name": "Alice", "sex": "female"}), patch(
            "hda.doctor_report.read_context",
            side_effect=lambda subject, section: contexts[section],
        ), patch(
            "hda.doctor_report.list_panels",
            return_value=[{"id": "cardiovascular", "review_status": "verified"}],
        ), patch(
            "hda.doctor_report.analyze_panel",
            return_value={
                "panel_name": "Cardiovascular",
                "results": [
                    {
                        "found": True,
                        "effect": "higher_risk",
                        "description": "Elevated cardiovascular risk marker",
                        "trait": "Risk",
                        "gene": "GENE1",
                    }
                ],
                "composite_results": [],
            },
        ), patch(
            "hda.doctor_report.validate_context",
            return_value={"issues": [{"section": "findings", "message": "Exploratory note."}]},
        ):
            payload = _build_report_payload("alice", "short")

        self.assertEqual(payload["variant"], "short")
        self.assertEqual([heading for heading, _ in payload["profile_sections"]], ["Overview", "Sleep & Recovery"])
        self.assertEqual([heading for heading, _ in payload["clinical_sections"]], ["Current Medications & Supplements", "Family History"])
        self.assertEqual(len(payload["medical_follow_up"]), 1)
        self.assertEqual(payload["medical_follow_up"][0]["title"], "Sleep Apnea Evaluation")
        self.assertEqual(payload["exploratory_blocks"], [])

    def test_export_doctor_report_short_omits_exploratory_sections(self):
        contexts = self._profile_context()
        with tempfile.TemporaryDirectory() as tempdir, patch(
            "hda.doctor_report.get_subject_profile",
            return_value={"name": "Alice", "sex": "female", "date_of_birth": "1980-01-01"},
        ), patch(
            "hda.doctor_report.read_context",
            side_effect=lambda subject, section: contexts[section],
        ), patch(
            "hda.doctor_report.list_panels",
            return_value=[{"id": "cardiovascular", "review_status": "verified"}],
        ), patch(
            "hda.doctor_report.analyze_panel",
            return_value={
                "panel_name": "Cardiovascular",
                "results": [
                    {
                        "found": True,
                        "effect": "higher_risk",
                        "description": "Elevated cardiovascular risk marker",
                        "trait": "Risk",
                        "gene": "GENE1",
                    }
                ],
                "composite_results": [],
            },
        ), patch(
            "hda.doctor_report.validate_context",
            return_value={"issues": [{"section": "findings", "message": "Exploratory note."}]},
        ):
            output = Path(tempdir) / "doctor-report-alice.pdf"
            path = export_doctor_report("alice", str(output), variant="short")
            text = self._read_pdf_text(output)

        self.assertEqual(path, str(output))
        self.assertIn("Health Summary For Clinical Discussion", text)
        self.assertNotIn("Extended Health Summary For Clinical Discussion", text)
        self.assertNotIn("Exploratory Or Contextual Themes", text)
        self.assertNotIn("Interpretation Boundaries", text)
        self.assertIn("Current Medications & Supplements", text)
        self.assertIn("Olmesartan 20 mg", text)
        self.assertIn("Use the long", text)
        self.assertIn("fuller contextual view.", text)

    def test_export_doctor_report_long_includes_exploratory_sections_and_validation_notes(self):
        contexts = self._profile_context()
        with tempfile.TemporaryDirectory() as tempdir, patch(
            "hda.doctor_report.get_subject_profile",
            return_value={"name": "Alice", "sex": "female", "date_of_birth": "1980-01-01"},
        ), patch(
            "hda.doctor_report.read_context",
            side_effect=lambda subject, section: contexts[section],
        ), patch(
            "hda.doctor_report.list_panels",
            return_value=[{"id": "cardiovascular", "review_status": "verified"}],
        ), patch(
            "hda.doctor_report.analyze_panel",
            return_value={
                "panel_name": "Cardiovascular",
                "results": [
                    {
                        "found": True,
                        "effect": "higher_risk",
                        "description": "Elevated cardiovascular risk marker",
                        "trait": "Risk",
                        "gene": "GENE1",
                    }
                ],
                "composite_results": [],
            },
        ), patch(
            "hda.doctor_report.validate_context",
            return_value={"issues": [{"section": "findings", "message": "Exploratory note."}]},
        ):
            output = Path(tempdir) / "doctor-report-alice-long.pdf"
            path = export_doctor_report("alice", str(output), variant="long")
            text = self._read_pdf_text(output)

        self.assertEqual(path, str(output))
        self.assertIn("Extended Health Summary For Clinical Discussion", text)
        self.assertIn("Interpretation Boundaries", text)
        self.assertIn("Exploratory Or Contextual Themes", text)
        self.assertIn("Exploratory summary for discussion.", text)
        self.assertIn("Family History", text)
        self.assertIn("Context Validation Notes", text)
        self.assertIn("Lifestyle Interactions", text)
        self.assertIn("Sleep Apnea Evaluation", text)
        self.assertNotIn("Archived Action", text)


if __name__ == "__main__":
    unittest.main()
