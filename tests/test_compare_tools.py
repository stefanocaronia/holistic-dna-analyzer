import unittest
from unittest.mock import patch

from hda.db.query import estimate_relatedness
from hda.tools.agent_tools import compare_panel


class CompareToolsTests(unittest.TestCase):
    def test_estimate_relatedness_returns_close_match_heuristic(self):
        rows = [
            {"genotype_a": "AA", "genotype_b": "AA"},
            {"genotype_a": "CT", "genotype_b": "CT"},
            {"genotype_a": "AG", "genotype_b": "AA"},
            {"genotype_a": "CC", "genotype_b": "CT"},
            {"genotype_a": "GG", "genotype_b": "GG"},
        ]

        with patch("hda.db.query._joined_subject_rows", return_value=rows):
            result = estimate_relatedness("alice", "bob")

        self.assertEqual(result["shared_snps"], 5)
        self.assertEqual(result["comparable_snps"], 5)
        self.assertAlmostEqual(result["exact_match_rate"], 0.6)
        self.assertEqual(result["heuristic_relationship"], "possibly_close_relatives")

    def test_compare_panel_summarizes_differences(self):
        alice_panel = {
            "panel_id": "cardiovascular",
            "panel_name": "Cardiovascular",
            "review_status": "verified",
            "status": "core",
            "results": [
                {
                    "rsid": "rs1",
                    "gene": "GENE1",
                    "trait": "Trait 1",
                    "genotype": "AA",
                    "effect": "typical",
                    "found": True,
                },
                {
                    "rsid": "rs2",
                    "gene": "GENE2",
                    "trait": "Trait 2",
                    "genotype": "CT",
                    "effect": "higher_risk",
                    "found": True,
                },
            ],
            "composite_results": [
                {
                    "id": "apoe",
                    "gene": "APOE",
                    "trait": "APOE profile",
                    "components": ["rs3", "rs4"],
                    "label": "e3/e3",
                    "effect": "typical",
                    "found": True,
                }
            ],
        }
        bob_panel = {
            "panel_id": "cardiovascular",
            "panel_name": "Cardiovascular",
            "review_status": "verified",
            "status": "core",
            "results": [
                {
                    "rsid": "rs1",
                    "gene": "GENE1",
                    "trait": "Trait 1",
                    "genotype": "AA",
                    "effect": "typical",
                    "found": True,
                },
                {
                    "rsid": "rs2",
                    "gene": "GENE2",
                    "trait": "Trait 2",
                    "genotype": "TT",
                    "effect": "lower_risk",
                    "found": True,
                },
            ],
            "composite_results": [
                {
                    "id": "apoe",
                    "gene": "APOE",
                    "trait": "APOE profile",
                    "components": ["rs3", "rs4"],
                    "label": "e3/e4",
                    "effect": "increased_risk",
                    "found": True,
                }
            ],
        }

        with patch("hda.tools.agent_tools.analyze_panel", side_effect=[alice_panel, bob_panel]):
            result = compare_panel("cardiovascular", "alice", "bob")

        self.assertEqual(result["summary"]["same_effect_count"], 1)
        self.assertEqual(result["summary"]["different_effect_count"], 1)
        self.assertEqual(result["summary"]["total_items"], 3)
        self.assertEqual(result["composite_results"][0]["comparison"], "different_effect")


if __name__ == "__main__":
    unittest.main()
