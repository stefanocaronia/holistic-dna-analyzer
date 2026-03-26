import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.config as config


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

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tempdir.cleanup()

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


if __name__ == "__main__":
    unittest.main()
