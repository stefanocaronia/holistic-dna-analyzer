import unittest
from unittest.mock import patch

from click.testing import CliRunner

from hda.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_switch_success(self):
        with patch("hda.config.switch_subject") as switch_subject:
            result = self.runner.invoke(main, ["switch", "alice"])

        self.assertEqual(result.exit_code, 0)
        switch_subject.assert_called_once_with("alice")
        self.assertIn("Active subject: alice", result.output)

    def test_switch_failure_returns_exit_code_1(self):
        with patch("hda.config.switch_subject", side_effect=KeyError("Subject 'eve' not found in config.yaml")):
            result = self.runner.invoke(main, ["switch", "eve"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Subject 'eve' not found", result.output)

    def test_import_missing_file_shows_fix_tip(self):
        with patch("hda.config.get_active_subject", return_value="alice"), patch(
            "hda.db.importer.import_subject", side_effect=FileNotFoundError("missing file")
        ):
            result = self.runner.invoke(main, ["import"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("missing file", result.output)
        self.assertIn("data/sources", result.output)

    def test_import_format_error_shows_supported_formats(self):
        with patch("hda.config.get_active_subject", return_value="alice"), patch(
            "hda.db.importer.SUPPORTED_FORMATS_LABEL", "MyHeritage, 23andMe, AncestryDNA"
        ), patch("hda.db.importer.import_subject", side_effect=ValueError("unsupported format")):
            result = self.runner.invoke(main, ["import"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("supported import formats", result.output)
        self.assertIn("MyHeritage, 23andMe, AncestryDNA", result.output)

    def test_panels_lists_review_status(self):
        with patch(
            "hda.analysis.panels.list_panels",
            return_value=[
                {
                    "id": "cardiovascular",
                    "name": "Cardiovascular",
                    "description": "Core panel",
                    "category": "health",
                    "review_status": "verified",
                    "variant_count": 1,
                }
            ],
        ):
            result = self.runner.invoke(main, ["panels"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Review", result.output)
        self.assertIn("verified", result.output)

    def test_whoami_prints_active_subject(self):
        with patch("hda.config.get_active_subject", return_value="stefano"), patch(
            "hda.config.get_subject_profile",
            return_value={"name": "Stefano", "sex": "male"},
        ):
            result = self.runner.invoke(main, ["whoami"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Active Subject", result.output)
        self.assertIn("stefano", result.output)
        self.assertIn("Stefano", result.output)

    def test_search_command_prints_results(self):
        with patch(
            "hda.db.query.search_snps",
            return_value=[
                {"rsid": "rs1", "chromosome": "1", "position": 123, "genotype": "AA"},
                {"rsid": "rs2", "chromosome": "1", "position": 456, "genotype": "CT"},
            ],
        ):
            result = self.runner.invoke(main, ["search", "--chromosome", "1", "--limit", "2"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("SNP Search", result.output)
        self.assertIn("rs1", result.output)
        self.assertIn("rs2", result.output)

    def test_compare_variant_command_prints_table(self):
        with patch(
            "hda.db.query.compare_snp",
            return_value={"rsid": "rs123", "alice": "AA", "bob": "AG", "match": False},
        ):
            result = self.runner.invoke(main, ["compare-variant", "rs123", "alice", "bob"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Variant Comparison: rs123", result.output)
        self.assertIn("alice", result.output)
        self.assertIn("bob", result.output)

    def test_compare_command_prints_rows(self):
        with patch(
            "hda.db.query.compare_subjects",
            return_value=[
                {
                    "rsid": "rs1",
                    "chromosome": "1",
                    "position": 123,
                    "genotype_a": "AA",
                    "genotype_b": "AG",
                }
            ],
        ):
            result = self.runner.invoke(main, ["compare", "alice", "bob", "--limit", "1"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Compare alice vs bob", result.output)
        self.assertIn("rs1", result.output)

    def test_compare_panel_command_prints_summary(self):
        with patch(
            "hda.tools.compare_panel",
            return_value={
                "panel_name": "Cardiovascular",
                "review_status": "verified",
                "requires_disclaimer": False,
                "summary": {"same_effect_count": 1, "different_effect_count": 1, "missing_count": 0},
                "results": [
                    {
                        "gene": "GENE1",
                        "rsid": "rs1",
                        "trait": "Trait 1",
                        "subject_a_genotype": "AA",
                        "subject_b_genotype": "AG",
                        "subject_a_effect": "typical",
                        "subject_b_effect": "higher_risk",
                        "comparison": "different_effect",
                    }
                ],
                "composite_results": [],
            },
        ):
            result = self.runner.invoke(main, ["compare-panel", "cardiovascular", "alice", "bob"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cardiovascular", result.output)
        self.assertIn("different effect", result.output)

    def test_relatedness_command_prints_metrics(self):
        with patch(
            "hda.tools.estimate_relatedness",
            return_value={
                "shared_snps": 100,
                "comparable_snps": 90,
                "exact_match_rate": 0.8,
                "ibs0_rate": 0.01,
                "ibs1_rate": 0.19,
                "ibs2_rate": 0.8,
                "heuristic_relationship": "possibly_first_degree_or_very_close",
                "interpretation_warning": "Exploratory only.",
            },
        ):
            result = self.runner.invoke(main, ["relatedness", "alice", "bob"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("possibly_first_degree_or_very_close", result.output)
        self.assertIn("Exploratory only.", result.output)

    def test_analyze_exploratory_panel_prints_warning(self):
        with patch(
            "hda.analysis.panels.analyze_panel",
            return_value={
                "panel_name": "Sleep",
                "panel_id": "sleep",
                "subject": "stefano",
                "review_status": "exploratory",
                "found_in_genome": 1,
                "total_variants": 1,
                "results": [
                    {
                        "gene": "CLOCK",
                        "rsid": "rs1801260",
                        "trait": "Chronotype",
                        "genotype": "AG",
                        "effect": "intermediate",
                        "description": "Exploratory chronotype signal.",
                        "found": True,
                    }
                ],
                "composite_results": [],
            },
        ):
            result = self.runner.invoke(main, ["analyze", "sleep"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("panel review status is 'exploratory'", result.output)
        self.assertIn("CLOCK", result.output)

    def test_analyze_missing_panel_returns_exit_code_1(self):
        with patch("hda.analysis.panels.analyze_panel", side_effect=FileNotFoundError("Panel not found")):
            result = self.runner.invoke(main, ["analyze", "missing"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Panel not found", result.output)

    def test_report_handles_empty_findings(self):
        with patch("hda.analysis.panels.get_risk_summary", return_value=[]):
            result = self.runner.invoke(main, ["report"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No notable findings across all panels", result.output)


if __name__ == "__main__":
    unittest.main()
