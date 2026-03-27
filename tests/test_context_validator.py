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

    def test_validate_context_flags_duplicate_findings_and_missing_references(self):
        findings_path = self.root / "data" / "context" / "alice" / "findings.md"
        findings_path.write_text(
            "---\nsubject: alice\ndoc_type: findings\ntitle: Alice Findings\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Findings\n\n"
            "## Profilo dopaminergico\n\n"
            "finding_id: dopamine_profile\n"
            "created: 2026-03-24\n"
            "updated: 2026-03-27\n"
            "status: active\n"
            "panel_basis: mixed\n\n"
            "### Summary\nReward deficiency dopaminica.\n\n"
            "## Profilo dopaminergico\n\n"
            "finding_id: dopamine_profile_2\n"
            "created: 2026-03-24\n"
            "updated: 2026-03-27\n"
            "status: active\n"
            "panel_basis: mixed\n\n"
            "### Summary\nReward deficiency dopaminica.\n",
            encoding="utf-8",
        )
        actions_path = self.root / "data" / "context" / "alice" / "health_actions.md"
        actions_path.write_text(
            "---\nsubject: alice\ndoc_type: health_actions\ntitle: Alice Actions\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Recommended Health Actions\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Media Priorità\n\n"
            "### Piano dopamina\n\n"
            "action_id: dopamine_plan\n"
            "status: active\n\n"
            "Rivedere dopamine_profile e missing_reference_finding.\n",
            encoding="utf-8",
        )

        payload = validate_context()

        messages = [issue["message"] for issue in payload["issues"]]
        self.assertTrue(any("semantically duplicated" in message for message in messages))
        self.assertTrue(any("references missing finding ids" in message for message in messages))

    def test_validate_context_flags_theme_drift_between_summary_findings_and_actions(self):
        findings_path = self.root / "data" / "context" / "alice" / "findings.md"
        findings_path.write_text(
            "---\nsubject: alice\ndoc_type: findings\ntitle: Alice Findings\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Findings\n\n"
            "## Sonno e recupero\n\n"
            "finding_id: sleep_recovery\n"
            "created: 2026-03-24\n"
            "updated: 2026-03-27\n"
            "status: active\n"
            "panel_basis: mixed\n\n"
            "### Summary\nTema sonno e recupero.\n",
            encoding="utf-8",
        )
        summary_path = self.root / "data" / "context" / "alice" / "profile_summary.md"
        summary_path.write_text(
            "---\nsubject: alice\ndoc_type: profile_summary\ntitle: Alice Summary\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Genetic Profile Summary\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Overview\nProfilo con nodo sonno e recupero.\n",
            encoding="utf-8",
        )
        actions_path = self.root / "data" / "context" / "alice" / "health_actions.md"
        actions_path.write_text(
            "---\nsubject: alice\ndoc_type: health_actions\ntitle: Alice Actions\nlast_updated: 2026-03-27\nschema_version: 1\n---\n\n"
            "# Alice — Recommended Health Actions\n\n"
            "Last updated: 2026-03-27\n\n"
            "## Media Priorità\n\n"
            "### Dieta\n\n"
            "action_id: diet_plan\n"
            "status: active\n\n"
            "Curare la dieta.\n",
            encoding="utf-8",
        )

        payload = validate_context()

        messages = [issue["message"] for issue in payload["issues"]]
        self.assertTrue(any("not reflected in health actions" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
