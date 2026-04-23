import unittest
from unittest.mock import patch

from hda.ancestry import estimate_ancestry


class AncestryTests(unittest.TestCase):
    def test_estimate_ancestry_returns_ranked_scores_from_marker_panel(self):
        marker_payloads = {
            "rs1426654": {
                "rsid": "rs1426654",
                "chromosome": "15",
                "position": 1,
                "genotype": "AA",
            },
            "rs2814778": {
                "rsid": "rs2814778",
                "chromosome": "1",
                "position": 1,
                "genotype": "TT",
            },
            "rs3827760": {
                "rsid": "rs3827760",
                "chromosome": "2",
                "position": 1,
                "genotype": "TT",
            },
        }

        def fake_get_snp(rsid, subject):
            return marker_payloads.get(rsid)

        def fake_annotate(rsid, subject=None, sources=None, force_refresh=False):
            populations_by_rsid = {
                "rs1426654": {
                    "AFR": {"A": 0.07, "G": 0.93},
                    "AMR": {"A": 0.58, "G": 0.42},
                    "EAS": {"A": 0.01, "G": 0.99},
                    "EUR": {"A": 0.99, "G": 0.01},
                    "SAS": {"A": 0.68, "G": 0.32},
                },
                "rs2814778": {
                    "AFR": {"C": 0.96, "T": 0.04},
                    "AMR": {"C": 0.08, "T": 0.92},
                    "EAS": {"C": 0.0, "T": 1.0},
                    "EUR": {"C": 0.01, "T": 0.99},
                    "SAS": {"C": 0.01, "T": 0.99},
                },
                "rs3827760": {
                    "AFR": {"C": 0.0, "T": 1.0},
                    "AMR": {"C": 0.65, "T": 0.35},
                    "EAS": {"C": 0.94, "T": 0.06},
                    "EUR": {"C": 0.0, "T": 1.0},
                    "SAS": {"C": 0.0, "T": 1.0},
                },
            }
            populations = []
            for pop, alleles in populations_by_rsid[rsid].items():
                for allele, freq in alleles.items():
                    populations.append(
                        {
                            "population": f"1000GENOMES:phase_3:{pop}",
                            "allele": allele,
                            "frequency": freq,
                        }
                    )
            return {
                "details": {
                    "ensembl": {
                        "populations": populations,
                    }
                }
            }

        with patch("hda.ancestry.get_snp", side_effect=fake_get_snp), patch(
            "hda.ancestry.annotate_snp_sync",
            side_effect=fake_annotate,
        ), patch("hda.ancestry.get_active_subject", return_value="stefano"):
            result = estimate_ancestry(min_markers=3)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["markers_used"], 3)
        self.assertEqual(result["scores"][0]["population"], "EUR")
        self.assertGreater(result["scores"][0]["probability"], result["scores"][1]["probability"])
        self.assertEqual(result["confidence"], "low")


if __name__ == "__main__":
    unittest.main()
