import unittest
from unittest.mock import patch

from dashboard.subject_selector import get_dashboard_subject_state, select_subject


class _FakeSidebar:
    def __init__(self, selected):
        self.selected = selected
        self.calls = []

    def selectbox(self, label, options, index=0, key=None):
        self.calls.append({"label": label, "options": list(options), "index": index, "key": key})
        return self.selected


class DashboardSubjectSelectorTests(unittest.TestCase):
    def test_get_dashboard_subject_state_uses_configured_subjects_and_active_default(self):
        with patch(
            "dashboard.subject_selector.list_subjects",
            return_value={"alice": {"name": "Alice"}, "bob": {"name": "Bob"}},
        ), patch("dashboard.subject_selector.get_active_subject", return_value="bob"):
            _, subject_keys, default_index = get_dashboard_subject_state()

        self.assertEqual(subject_keys, ["alice", "bob"])
        self.assertEqual(default_index, 1)

    def test_select_subject_only_offers_configured_keys(self):
        sidebar = _FakeSidebar("bob")
        with patch(
            "dashboard.subject_selector.list_subjects",
            return_value={"alice": {"name": "Alice"}, "bob": {"name": "Bob"}},
        ), patch("dashboard.subject_selector.get_active_subject", return_value="alice"):
            selected = select_subject(sidebar, key="profile_subject")

        self.assertEqual(selected, "bob")
        self.assertEqual(
            sidebar.calls[0],
            {"label": "Subject", "options": ["alice", "bob"], "index": 0, "key": "profile_subject"},
        )

    def test_select_subject_falls_back_to_first_subject_when_active_missing(self):
        sidebar = _FakeSidebar("alice")
        with patch(
            "dashboard.subject_selector.list_subjects",
            return_value={"alice": {"name": "Alice"}, "bob": {"name": "Bob"}},
        ), patch("dashboard.subject_selector.get_active_subject", return_value="charlie"):
            selected = select_subject(sidebar, key="panel_subject")

        self.assertEqual(selected, "alice")
        self.assertEqual(sidebar.calls[0]["index"], 0)

    def test_get_dashboard_subject_state_requires_at_least_one_configured_subject(self):
        with patch("dashboard.subject_selector.list_subjects", return_value={}), patch(
            "dashboard.subject_selector.get_active_subject",
            return_value="alice",
        ):
            with self.assertRaises(RuntimeError):
                get_dashboard_subject_state()


if __name__ == "__main__":
    unittest.main()
