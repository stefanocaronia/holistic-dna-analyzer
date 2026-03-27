import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.config as config
from hda.context_audit import read_context_audit
from hda.context_migrator import migrate_context


class ContextMigratorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "config.yaml"
        self.config_path.write_text(
            "active_subject: alice\n"
            "subjects:\n"
            "  alice:\n"
            "    name: Alice\n",
            encoding="utf-8",
        )

        context_dir = self.root / "data" / "context" / "alice"
        context_dir.mkdir(parents=True)
        (context_dir / "findings.md").write_text(
            "---\nsubject: alice\ndoc_type: findings\ntitle: Alice Findings\nlast_updated: 2026-03-27\nschema_version: 0\n---\n\n"
            "# Alice Findings\n\n"
            "## dopamine_reward_deficiency\n\n"
            "### Summary\n"
            "Signal\n",
            encoding="utf-8",
        )
        (context_dir / "health_actions.md").write_text(
            "---\nsubject: alice\ndoc_type: health_actions\ntitle: Alice Actions\nlast_updated: 2026-03-27\nschema_version: 0\n---\n\n"
            "# Alice Actions\n\n"
            "## High Priority\n\n"
            "### Sleep Apnea Evaluation\n\n"
            "See doctor.\n",
            encoding="utf-8",
        )
        (context_dir / "profile_summary.md").write_text(
            "---\nsubject: alice\ndoc_type: profile_summary\ntitle: Alice Summary\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice - Genetic Profile Summary\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Overview\nCurrent summary.\n",
            encoding="utf-8",
        )

        patches = [
            patch.object(config, "ROOT_DIR", self.root),
            patch.object(config, "CONFIG_PATH", self.config_path),
            patch.object(config, "DATA_DIR", self.root / "data"),
            patch.object(config, "CONTEXT_DIR", self.root / "data" / "context"),
        ]
        self.patchers = patches
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tempdir.cleanup()

    def test_migrate_context_dry_run_reports_legacy_changes(self):
        payload = migrate_context()

        self.assertTrue(payload["needs_migration"])
        by_id = {section["id"]: section for section in payload["sections"]}
        self.assertEqual(by_id["findings"]["status"], "needs_migration")
        self.assertGreater(by_id["findings"]["change_count"], 0)
        self.assertEqual(by_id["health_actions"]["status"], "needs_migration")

        findings_text = (self.root / "data" / "context" / "alice" / "findings.md").read_text(encoding="utf-8")
        self.assertIn("schema_version: 0", findings_text)
        self.assertNotIn("finding_id:", findings_text)

    def test_migrate_context_apply_creates_backup_and_rewrites_legacy_files(self):
        backup_root = self.root / "backups"
        payload = migrate_context(apply=True, backup_root=str(backup_root))

        self.assertEqual(payload["migrated_count"], 2)
        self.assertTrue(payload["backup_path"])
        backup_dir = Path(payload["backup_path"])
        self.assertTrue(backup_dir.exists())

        migrated_findings = (self.root / "data" / "context" / "alice" / "findings.md").read_text(encoding="utf-8")
        self.assertIn("schema_version: 1", migrated_findings)
        self.assertIn("## Dopamine Reward Deficiency", migrated_findings)
        self.assertIn("finding_id: dopamine_reward_deficiency", migrated_findings)

        migrated_actions = (self.root / "data" / "context" / "alice" / "health_actions.md").read_text(encoding="utf-8")
        self.assertIn("## Alta Priorità", migrated_actions)
        self.assertIn("action_id: sleep_apnea_evaluation", migrated_actions)
        self.assertIn("status: active", migrated_actions)

        backed_up_findings = (backup_dir / "findings.md").read_text(encoding="utf-8")
        self.assertIn("schema_version: 0", backed_up_findings)
        self.assertIn("## dopamine_reward_deficiency", backed_up_findings)

        audit = read_context_audit()
        self.assertEqual([entry["event_type"] for entry in audit["entries"]], ["migrate_section", "migrate_section"])
        self.assertEqual({entry["section"] for entry in audit["entries"]}, {"findings", "health_actions"})

    def test_migrate_context_skips_unversioned_documents(self):
        unversioned = self.root / "data" / "context" / "alice" / "session_notes.md"
        unversioned.write_text("# Notes\n\n## 2026-03-27: Legacy\n\n- Note\n", encoding="utf-8")

        payload = migrate_context(section="session_notes")

        section = payload["sections"][0]
        self.assertEqual(section["status"], "manual_intervention_required")
        self.assertFalse(section["needs_migration"])
        self.assertTrue(section["warnings"])


if __name__ == "__main__":
    unittest.main()
