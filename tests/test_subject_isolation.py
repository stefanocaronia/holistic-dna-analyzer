import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

import hda.config as config
from hda.cli import main
from hda.tools import list_context_sections, lookup_snp


class SubjectIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_text(
            "active_subject: alice\n"
            "subjects:\n"
            "  alice:\n"
            "    name: Alice\n"
            "  bob:\n"
            "    name: Bob\n",
            encoding="utf-8",
        )
        db_dir = self.root / "data" / "db"
        db_dir.mkdir(parents=True)
        self._write_subject_db(db_dir / "alice.db", "AA")
        self._write_subject_db(db_dir / "bob.db", "GG")
        (self.root / "data" / "context" / "alice").mkdir(parents=True)
        (self.root / "data" / "context" / "bob").mkdir(parents=True)

        patches = [
            patch.object(config, "ROOT_DIR", self.root),
            patch.object(config, "CONFIG_PATH", self.config_path),
            patch.object(config, "DATA_DIR", self.root / "data"),
            patch.object(config, "DB_DIR", self.root / "data" / "db"),
            patch.object(config, "CONTEXT_DIR", self.root / "data" / "context"),
        ]
        self.patchers = patches
        for p in self.patchers:
            p.start()
        self.runner = CliRunner()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tempdir.cleanup()

    def _write_subject_db(self, path: Path, genotype: str):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE snps (rsid TEXT, chromosome TEXT, position INTEGER, genotype TEXT)")
        conn.execute("INSERT INTO snps VALUES (?, ?, ?, ?)", ("rs1", "1", 12345, genotype))
        conn.commit()
        conn.close()

    def test_get_db_path_requires_configured_subject(self):
        self.assertEqual(config.get_db_path("alice"), self.root / "data" / "db" / "alice.db")
        with self.assertRaises(KeyError):
            config.get_db_path("../../outside")

    def test_get_context_path_requires_configured_subject(self):
        self.assertEqual(config.get_context_path("bob"), self.root / "data" / "context" / "bob")
        with self.assertRaises(KeyError):
            config.get_context_path("eve")

    def test_switch_subject_requires_configured_subject(self):
        config.switch_subject("bob")
        self.assertEqual(config.get_active_subject(), "bob")

        with self.assertRaises(KeyError):
            config.switch_subject("mallory")

    def test_api_lookup_snp_respects_active_subject_and_explicit_subject(self):
        self.assertEqual(lookup_snp("rs1")["subject"], "alice")
        self.assertEqual(lookup_snp("rs1")["genotype"], "AA")

        self.assertEqual(lookup_snp("rs1", subject="bob")["subject"], "bob")
        self.assertEqual(lookup_snp("rs1", subject="bob")["genotype"], "GG")

        with self.assertRaises(KeyError):
            lookup_snp("rs1", subject="mallory")

    def test_api_context_lookup_rejects_unconfigured_subject(self):
        payload = list_context_sections("alice")
        self.assertEqual(payload["subject"], "alice")

        with self.assertRaises(KeyError):
            list_context_sections("mallory")

    def test_cli_snp_routes_to_selected_subject_and_rejects_unknown_subject(self):
        active_result = self.runner.invoke(main, ["snp", "rs1"])
        self.assertEqual(active_result.exit_code, 0)
        self.assertIn("AA", active_result.output)
        self.assertNotIn("GG", active_result.output)

        explicit_result = self.runner.invoke(main, ["snp", "rs1", "--subject", "bob"])
        self.assertEqual(explicit_result.exit_code, 0)
        self.assertIn("GG", explicit_result.output)
        self.assertNotIn("AA", explicit_result.output)

        invalid_result = self.runner.invoke(main, ["snp", "rs1", "--subject", "mallory"])
        self.assertEqual(invalid_result.exit_code, 1)
        self.assertIn("mallory", invalid_result.output)


if __name__ == "__main__":
    unittest.main()
