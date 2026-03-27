import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.config as config
from hda.context_audit import read_context_audit
from hda.context_documents import (
    import_context_document,
    import_context_inbox,
    list_context_documents,
    list_context_inbox,
)
from hda.context_store import read_context


class ContextDocumentsTests(unittest.TestCase):
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
        (self.root / "data" / "context" / "alice").mkdir(parents=True)
        self.source_file = self.root / "cbc-report.pdf"
        self.source_file.write_text("fake pdf bytes", encoding="utf-8")

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

    def test_import_context_document_copies_into_dated_category_folder(self):
        payload = import_context_document(
            str(self.source_file),
            document_date="2026-03-27",
            category="labs",
            title="CBC Report",
            notes="Primary care upload",
        )

        doc = payload["document"]
        self.assertEqual(payload["subject"], "alice")
        self.assertTrue(Path(doc["path"]).exists())
        self.assertIn("documents/2026-03-27/labs/", doc["relative_path"])
        self.assertTrue(Path(doc["markdown_path"]).exists())
        self.assertTrue(doc["markdown_relative_path"].endswith(".extracted.md"))
        self.assertEqual(doc["title"], "CBC Report")
        self.assertEqual(doc["notes"], "Primary care upload")
        self.assertTrue(self.source_file.exists())
        clinical = read_context(section="clinical_context")
        self.assertIn("Recent Labs & Imaging", clinical["content"])
        self.assertIn("2026-03-27 - CBC Report", clinical["content"])
        self.assertIn(".extracted.md", clinical["content"])
        audit = read_context_audit()
        self.assertEqual(audit["entries"][-1]["event_type"], "integrate_document")

    def test_list_context_documents_includes_imported_and_manual_files(self):
        import_context_document(
            str(self.source_file),
            document_date="2026-03-27",
            category="labs",
            title="CBC Report",
        )
        manual_dir = self.root / "data" / "context" / "alice" / "documents" / "2026-03-20" / "imaging"
        manual_dir.mkdir(parents=True)
        manual_file = manual_dir / "echo.pdf"
        manual_file.write_text("manual", encoding="utf-8")

        payload = list_context_documents()

        self.assertEqual(payload["count"], 2)
        by_filename = {item["filename"]: item for item in payload["documents"]}
        self.assertIn("echo.pdf", by_filename)
        self.assertEqual(by_filename["echo.pdf"]["category"], "imaging")
        self.assertEqual(by_filename["echo.pdf"]["document_date"], "2026-03-20")
        self.assertEqual(by_filename["echo.pdf"]["title"], "Echo")

    def test_list_context_inbox_infers_date_and_category_from_path(self):
        inbox_dir = self.root / "data" / "context" / "alice" / "documents_inbox" / "2026-03-15" / "labs"
        inbox_dir.mkdir(parents=True)
        inbox_file = inbox_dir / "ferritin.pdf"
        inbox_file.write_text("lab", encoding="utf-8")

        payload = list_context_inbox()

        self.assertEqual(payload["count"], 1)
        item = payload["documents"][0]
        self.assertEqual(item["document_date"], "2026-03-15")
        self.assertEqual(item["category"], "labs")
        self.assertEqual(item["filename"], "ferritin.pdf")

    def test_list_context_inbox_creates_real_subject_folder_if_missing(self):
        inbox_root = self.root / "data" / "context" / "alice" / "documents_inbox"

        payload = list_context_inbox()

        self.assertEqual(payload["count"], 0)
        self.assertTrue(inbox_root.exists())
        self.assertTrue(inbox_root.is_dir())

    def test_list_context_inbox_infers_labs_category_from_filename_when_in_root(self):
        inbox_root = self.root / "data" / "context" / "alice" / "documents_inbox"
        inbox_root.mkdir(parents=True)
        inbox_file = inbox_root / "esami-sangue.pdf"
        inbox_file.write_text("lab", encoding="utf-8")

        payload = list_context_inbox()

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["documents"][0]["category"], "labs")

    def test_import_context_inbox_moves_pending_files_into_archive(self):
        inbox_dir = self.root / "data" / "context" / "alice" / "documents_inbox" / "imaging"
        inbox_dir.mkdir(parents=True)
        inbox_file = inbox_dir / "echo.pdf"
        inbox_file.write_text("echo", encoding="utf-8")

        payload = import_context_inbox()

        self.assertEqual(payload["imported_count"], 1)
        imported = payload["imported"][0]
        self.assertEqual(imported["category"], "imaging")
        self.assertIn("documents/", imported["relative_path"])
        self.assertTrue(imported["markdown_relative_path"].endswith(".extracted.md"))
        self.assertFalse(inbox_file.exists())
        self.assertEqual(list_context_inbox()["count"], 0)
        audit = read_context_audit()
        self.assertEqual(audit["entries"][-1]["event_type"], "integrate_document")


if __name__ == "__main__":
    unittest.main()
