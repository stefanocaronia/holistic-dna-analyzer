import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.analysis.panels as panels
from hda.analysis.panels import analyze_panel, list_panels, load_panel


class PanelMetadataTests(unittest.TestCase):
    def test_list_panels_exposes_review_metadata(self):
        panels = {panel["id"]: panel for panel in list_panels()}
        self.assertIn("nutrition_metabolism", panels)
        self.assertIn("review_status", panels["nutrition_metabolism"])
        self.assertIn("status", panels["nutrition_metabolism"])

    def test_analyze_panel_propagates_panel_metadata(self):
        panel = load_panel("nutrition_metabolism")
        self.assertEqual(panel["review_status"], "verified")

        result = analyze_panel("nutrition_metabolism", "stefano")
        self.assertEqual(result["review_status"], "verified")
        self.assertEqual(result["status"], "core")
        self.assertIn("sources", result)
        self.assertIn("limitations", result)

    def test_legacy_panel_ids_still_resolve(self):
        panel = load_panel("nutrigenomics")
        self.assertEqual(panel["id"], "nutrition_metabolism")

        result = analyze_panel("nutrition_advanced", "stefano")
        self.assertEqual(result["panel_id"], "nutrition_micronutrients")
        self.assertEqual(result["requested_panel_id"], "nutrition_advanced")

    def test_filename_suffix_sets_review_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "focus.experimental.yaml").write_text(
                "name: Focus\n"
                "description: Experimental focus panel\n"
                "category: health\n"
                "variants: []\n",
                encoding="utf-8",
            )
            (root / "sleep_boost.draft.yaml").write_text(
                "name: Sleep Boost\n"
                "description: Draft panel\n"
                "category: wellness\n"
                "variants: []\n",
                encoding="utf-8",
            )

            with patch.object(panels, "PANELS_DIR", root):
                listed = {panel["id"]: panel for panel in list_panels()}
                self.assertEqual(listed["focus"]["review_status"], "exploratory")
                self.assertEqual(listed["focus"]["status"], "experimental")
                self.assertEqual(listed["sleep_boost"]["review_status"], "draft")
                self.assertEqual(listed["sleep_boost"]["status"], "draft")
                self.assertEqual(load_panel("focus")["review_status"], "exploratory")
                self.assertEqual(load_panel("sleep_boost")["review_status"], "draft")

    def test_composite_panel_results_are_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "apoe.yaml").write_text(
                "name: APOE Test\n"
                "description: Test panel\n"
                "category: health\n"
                "variants: []\n"
                "composites:\n"
                "  - id: apoe_profile\n"
                "    gene: APOE\n"
                "    trait: APOE profile\n"
                "    components:\n"
                "      - rs429358\n"
                "      - rs7412\n"
                "    genotypes:\n"
                "      'TT|CC':\n"
                "        label: e3/e3\n"
                "        effect: typical\n"
                "        description: Typical APOE profile.\n",
                encoding="utf-8",
            )

            def fake_get_snp(rsid, subject):
                values = {
                    "rs429358": {"rsid": "rs429358", "chromosome": "19", "position": 0, "genotype": "TT"},
                    "rs7412": {"rsid": "rs7412", "chromosome": "19", "position": 0, "genotype": "CC"},
                }
                return values.get(rsid)

            with patch.object(panels, "PANELS_DIR", root), patch.object(panels, "get_snp", fake_get_snp):
                result = analyze_panel("apoe", "stefano")
                self.assertEqual(result["total_variants"], 1)
                self.assertEqual(result["found_in_genome"], 1)
                self.assertEqual(result["composite_results"][0]["label"], "e3/e3")
                self.assertEqual(result["composite_results"][0]["effect"], "typical")


if __name__ == "__main__":
    unittest.main()
