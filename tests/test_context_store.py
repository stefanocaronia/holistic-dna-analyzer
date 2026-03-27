import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.config as config
from hda.context_audit import read_context_audit
from hda.context_store import (
    append_context_entry,
    archive_context_block,
    list_context_sections,
    move_context_block,
    read_context,
    read_context_block,
    replace_context_entry,
    replace_context_section,
    upsert_context_block,
    write_context_document,
)


class ContextStoreTests(unittest.TestCase):
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
        (context_dir / "profile_summary.md").write_text(
            "---\n"
            "subject: alice\n"
            "doc_type: profile_summary\n"
            "title: Alice - Summary\n"
            "last_updated: 2026-03-27\n"
            "schema_version: 1\n"
            "---\n"
            "# Summary\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Overview\n"
            "Original overview\n",
            encoding="utf-8",
        )
        (context_dir / "session_notes.md").write_text(
            "---\n"
            "subject: alice\n"
            "doc_type: session_notes\n"
            "title: Alice - Notes\n"
            "last_updated: 2026-03-27\n"
            "schema_version: 1\n"
            "---\n"
            "# Notes\n\n"
            "## 2026-03-27: Existing\n\n"
            "- Follow up\n",
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

    def test_list_context_sections_reports_known_files(self):
        payload = list_context_sections()

        self.assertEqual(payload["subject"], "alice")
        self.assertEqual(len(payload["sections"]), 5)
        by_id = {section["id"]: section for section in payload["sections"]}
        self.assertTrue(by_id["profile_summary"]["exists"])
        self.assertFalse(by_id["clinical_context"]["exists"])
        self.assertFalse(by_id["findings"]["exists"])
        self.assertEqual(by_id["profile_summary"]["metadata"]["doc_type"], "profile_summary")

    def test_read_context_returns_all_sections(self):
        payload = read_context()

        self.assertEqual(payload["subject"], "alice")
        self.assertEqual(len(payload["sections"]), 5)
        by_id = {section["id"]: section for section in payload["sections"]}
        self.assertIn("# Summary", by_id["profile_summary"]["content"])
        self.assertEqual(by_id["profile_summary"]["metadata"]["subject"], "alice")
        self.assertIsNone(by_id["clinical_context"]["content"])
        self.assertIsNone(by_id["health_actions"]["content"])

    def test_write_context_document_updates_last_updated_line(self):
        payload = write_context_document(
            "profile_summary",
            "# Summary\n\nLast updated: 2020-01-01\n\n## Overview\nUpdated overview\n",
        )

        self.assertEqual(payload["metadata"]["doc_type"], "profile_summary")
        self.assertIn("Last updated:", payload["content"])
        self.assertIn("Updated overview", payload["content"])

    def test_replace_context_section_replaces_existing_heading(self):
        payload = replace_context_section("profile_summary", "Overview", "Replaced overview")

        self.assertIn("Replaced overview", payload["content"])
        self.assertNotIn("Original overview", payload["content"])

    def test_replace_context_section_supports_clinical_context(self):
        payload = replace_context_section(
            "clinical_context",
            "Current Medications & Supplements",
            "- Olmesartan 20 mg\n- Vitamin D 2000 IU",
        )

        self.assertEqual(payload["id"], "clinical_context")
        self.assertIn("Current Medications & Supplements", payload["content"])
        self.assertIn("Olmesartan 20 mg", payload["content"])

    def test_upsert_context_block_creates_and_updates_finding(self):
        first = upsert_context_block(
            "findings",
            "dopamine_reward_deficiency",
            "### Summary\nSignal\n",
            metadata={"domains": "adhd, addiction"},
        )
        second = upsert_context_block(
            "findings",
            "dopamine_reward_deficiency",
            "### Summary\nUpdated signal\n",
            metadata={"domains": "adhd, addiction, pharmacogenomics"},
        )

        block = read_context_block("findings", "dopamine_reward_deficiency")
        self.assertIn("Updated signal", second["content"])
        self.assertEqual(block["metadata"]["status"], "active")
        self.assertEqual(block["metadata"]["domains"], "adhd, addiction, pharmacogenomics")

        archived = archive_context_block("findings", "dopamine_reward_deficiency")
        archived_block = read_context_block("findings", "dopamine_reward_deficiency")
        self.assertEqual(archived["metadata"]["doc_type"], "findings")
        self.assertEqual(archived_block["metadata"]["status"], "archived")

    def test_upsert_context_block_uses_human_heading_and_stable_finding_id(self):
        upsert_context_block(
            "findings",
            "dopamine_reward_deficiency",
            "### Summary\nSignal\n",
        )

        block = read_context_block("findings", "dopamine_reward_deficiency")
        self.assertEqual(block["heading"], "Dopamine Reward Deficiency")
        self.assertEqual(block["metadata"]["finding_id"], "dopamine_reward_deficiency")

    def test_upsert_context_block_preserves_custom_finding_title(self):
        upsert_context_block(
            "findings",
            "dopamine_reward_deficiency",
            "### Summary\nSignal\n",
            metadata={"title": "Profilo dopaminergico di reward deficiency"},
        )

        block = read_context_block("findings", "dopamine_reward_deficiency")
        self.assertEqual(block["heading"], "Profilo dopaminergico di reward deficiency")
        self.assertEqual(block["metadata"]["finding_id"], "dopamine_reward_deficiency")

    def test_upsert_move_and_archive_health_action(self):
        upsert_context_block(
            "health_actions",
            "sleep_apnea_evaluation",
            "Rationale and next step.",
            title="Valutazione apnea del sonno",
            destination="Alta Priorità",
            metadata={"status": "active"},
        )

        block = read_context_block("health_actions", "sleep_apnea_evaluation")
        self.assertEqual(block["destination"], "Alta Priorità")

        move_context_block("health_actions", "sleep_apnea_evaluation", "Media Priorità")
        moved = read_context_block("health_actions", "sleep_apnea_evaluation")
        self.assertEqual(moved["destination"], "Media Priorità")

        archive_context_block("health_actions", "sleep_apnea_evaluation")
        archived = read_context_block("health_actions", "sleep_apnea_evaluation")
        self.assertEqual(archived["destination"], "Bassa Priorità")
        self.assertEqual(archived["metadata"]["status"], "archived")

    def test_append_and_replace_session_entry(self):
        append_context_entry(
            "session_notes",
            "New note",
            "- Bullet one",
            entry_date="2026-03-28",
        )
        replace_context_entry(
            "session_notes",
            "2026-03-28: New note",
            "- Replaced bullet",
        )

        block = read_context_block("session_notes", "2026-03-28: New note")
        self.assertIn("Replaced bullet", block["content"])

    def test_context_writes_append_audit_entries(self):
        upsert_context_block(
            "findings",
            "dopamine_reward_deficiency",
            "### Summary\nSignal\n",
        )
        append_context_entry(
            "session_notes",
            "New note",
            "- Bullet one",
            entry_date="2026-03-28",
        )

        audit = read_context_audit()

        self.assertEqual(audit["subject"], "alice")
        self.assertEqual([entry["event_type"] for entry in audit["entries"]], ["upsert_block", "append_entry"])
        self.assertEqual(audit["entries"][0]["details"]["block_id"], "dopamine_reward_deficiency")
        self.assertEqual(audit["entries"][1]["details"]["heading"], "2026-03-28: New note")

    def test_context_audit_limit_returns_latest_entries(self):
        write_context_document("profile_summary", "# Summary\n\n## Overview\nUpdated once\n")
        replace_context_section("profile_summary", "Overview", "Updated twice")

        audit = read_context_audit(limit=1)

        self.assertEqual(len(audit["entries"]), 1)
        self.assertEqual(audit["entries"][0]["event_type"], "replace_section")


if __name__ == "__main__":
    unittest.main()
