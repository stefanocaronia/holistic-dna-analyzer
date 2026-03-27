import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hda.config as config
from hda.context_validator import validate_context


class ContextValidatorTests(unittest.TestCase):
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
            "---\nsubject: alice\ndoc_type: profile_summary\ntitle: Alice Summary\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Genetic Profile Summary\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Overview\nProfile overview\n",
            encoding="utf-8",
        )
        (context_dir / "findings.md").write_text(
            "---\nsubject: alice\ndoc_type: findings\ntitle: Alice Findings\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Findings\n\n"
            "## adhd_signal_convergence\n\n"
            "created: 2026-03-24\n"
            "updated: 2026-03-27\n"
            "status: active\n"
            "panel_basis: exploratory\n\n"
            "### Summary\nStrong ADHD signal.\n",
            encoding="utf-8",
        )
        (context_dir / "health_actions.md").write_text(
            "---\nsubject: alice\ndoc_type: health_actions\ntitle: Alice Actions\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Recommended Health Actions\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Media Priorità\n\n"
            "### Valutazione Neuropsichiatrica per AuDHD\n\n"
            "action_id: neuro_eval\n"
            "status: active\n\n"
            "Richiedere valutazione clinica.\n",
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

        panel_patcher = patch(
            "hda.context_validator.list_panels",
            return_value=[
                {"id": "cardiovascular", "review_status": "verified"},
                {"id": "mental_health", "review_status": "exploratory"},
                {"id": "adhd_neurodivergence", "review_status": "exploratory"},
            ],
        )
        self.panel_patcher = panel_patcher
        self.panel_patcher.start()

    def tearDown(self):
        self.panel_patcher.stop()
        for p in reversed(self.patchers):
            p.stop()
        self.tempdir.cleanup()

    def test_validate_context_flags_missing_caveats(self):
        payload = validate_context()

        self.assertGreaterEqual(payload["issue_count"], 2)
        messages = [issue["message"] for issue in payload["issues"]]
        self.assertTrue(any("lacks an explicit cautionary caveat" in message for message in messages))
        self.assertTrue(any("interpretation-boundaries" in message for message in messages))

    def test_validate_context_apply_adds_boundaries_section(self):
        payload = validate_context(apply=True)

        self.assertEqual(len(payload["applied_fixes"]), 1)
        summary_text = (self.root / "data" / "context" / "alice" / "profile_summary.md").read_text(encoding="utf-8")
        self.assertIn("## Interpretation Boundaries", summary_text)


if __name__ == "__main__":
    unittest.main()
