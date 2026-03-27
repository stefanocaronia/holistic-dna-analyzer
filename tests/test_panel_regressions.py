import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import hda.config as config
from hda.analysis.panels import analyze_panel, get_risk_summary
from hda.db.schema import get_connection, init_db


class PanelRegressionTests(unittest.TestCase):
    FIXTURE_PATH = Path(__file__).parent / "fixtures" / "panels" / "core_subject.yaml"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.fixture = yaml.safe_load(self.FIXTURE_PATH.read_text(encoding="utf-8"))
        subject_key = self.fixture["subject"]["key"]
        self.subject_key = subject_key

        self.config_path = self.root / "config.yaml"
        self.config_path.write_text(
            "active_subject: fixture_subject\n"
            "subjects:\n"
            "  fixture_subject:\n"
            "    name: Fixture Subject\n",
            encoding="utf-8",
        )

        db_dir = self.root / "data" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / f"{subject_key}.db"
        init_db(self.db_path)
        conn = get_connection(self.db_path)
        conn.executemany(
            "INSERT INTO snps (rsid, chromosome, position, genotype) VALUES (?, ?, ?, ?)",
            [
                (row["rsid"], row["chromosome"], row["position"], row["genotype"])
                for row in self.fixture["snps"]
            ],
        )
        conn.commit()
        conn.close()

        patches = [
            patch.object(config, "ROOT_DIR", self.root),
            patch.object(config, "CONFIG_PATH", self.config_path),
            patch.object(config, "DATA_DIR", self.root / "data"),
            patch.object(config, "DB_DIR", db_dir),
            patch.object(config, "CONTEXT_DIR", self.root / "data" / "context"),
        ]
        self.patchers = patches
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tempdir.cleanup()

    def test_core_panels_match_expected_fixture_outputs(self):
        for panel_id, expected in self.fixture["expected_panels"].items():
            result = analyze_panel(panel_id, self.subject_key)
            self.assertEqual(result["review_status"], "verified", panel_id)

            variant_effects = {row["rsid"]: row["effect"] for row in result["results"] if row["found"]}
            for rsid, expected_effect in expected.get("variants", {}).items():
                self.assertEqual(variant_effects.get(rsid), expected_effect, f"{panel_id}:{rsid}")

            composite_effects = {row["id"]: row["effect"] for row in result.get("composite_results", []) if row["found"]}
            for composite_id, expected_effect in expected.get("composites", {}).items():
                self.assertEqual(composite_effects.get(composite_id), expected_effect, f"{panel_id}:{composite_id}")

    def test_risk_summary_matches_expected_notable_fixture_rsids(self):
        summary = get_risk_summary(self.subject_key)
        summary_pairs = sorted((row["rsid"], row["panel_review_status"]) for row in summary)
        expected_pairs = sorted(
            (row["rsid"], row["panel_review_status"]) for row in self.fixture["expected_notable"]
        )

        self.assertEqual(summary_pairs, expected_pairs)


if __name__ == "__main__":
    unittest.main()
