import unittest
from unittest.mock import patch

from hda.neanderthal import estimate_neanderthal_ancestry


class NeanderthalTests(unittest.TestCase):
    def test_estimate_neanderthal_ancestry_counts_marker_copies(self):
        marker_payloads = {
            "rs4849721": {"rsid": "rs4849721", "genotype": "TT"},
            "rs1364405": {"rsid": "rs1364405", "genotype": "AG"},
            "rs4833095": {"rsid": "rs4833095", "genotype": "TT"},
        }

        def fake_get_snp(rsid, subject):
            return marker_payloads.get(rsid)

        def fake_annotate(rsid, subject=None, sources=None, force_refresh=False):
            populations = []
            for pop, freq in {
                "AFR": 0.02,
                "AMR": 0.15,
                "EAS": 0.10,
                "EUR": 0.35,
                "SAS": 0.22,
            }.items():
                populations.append(
                    {
                        "population": f"1000GENOMES:phase_3:{pop}",
                        "allele": "T" if rsid != "rs1364405" else "A",
                        "frequency": freq,
                    }
                )
                populations.append(
                    {
                        "population": f"1000GENOMES:phase_3:{pop}",
                        "allele": "G" if rsid != "rs1364405" else "G",
                        "frequency": 1 - freq,
                    }
                )
            return {"details": {"ensembl": {"populations": populations}}}

        with patch("hda.neanderthal.get_snp", side_effect=fake_get_snp), patch(
            "hda.neanderthal.annotate_snp_sync",
            side_effect=fake_annotate,
        ), patch("hda.neanderthal.get_active_subject", return_value="stefano"):
            result = estimate_neanderthal_ancestry()

        self.assertEqual(result["observed_copy_count"], 5)
        self.assertEqual(result["positive_markers"], 3)
        self.assertEqual(result["markers_found"], 3)
        self.assertTrue(any(row["population"] == "EUR" for row in result["comparisons"]))


if __name__ == "__main__":
    unittest.main()
