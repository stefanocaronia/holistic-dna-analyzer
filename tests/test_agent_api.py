import unittest

import hda.tools as tools
from hda.tools import agent_tools


class AgentApiTests(unittest.TestCase):
    def test_public_tools_reexport_agent_surface(self):
        expected = {
            "append_context_entry",
            "archive_context_block",
            "annotate",
            "annotate_my_snp",
            "available_panels",
            "compare",
            "compare_panel",
            "compare_variant",
            "estimate_relatedness",
            "export_doctor_report",
            "get_stats",
            "list_context_sections",
            "list_all_subjects",
            "lookup_snp",
            "migrate_context",
            "move_context_block",
            "notable_findings",
            "read_context_block",
            "replace_context_entry",
            "replace_context_section",
            "read_context",
            "run_all_panels",
            "run_panel",
            "search",
            "upsert_context_block",
            "write_context_document",
            "who_am_i",
        }

        self.assertTrue(expected.issubset(set(tools.__all__)))
        for name in expected:
            self.assertIs(getattr(tools, name), getattr(agent_tools, name))


if __name__ == "__main__":
    unittest.main()
