import unittest

import hda.tools as tools
from hda.tools import agent_tools


class AgentApiTests(unittest.TestCase):
    def test_public_tools_reexport_agent_surface(self):
        expected = {
            "annotate",
            "annotate_my_snp",
            "available_panels",
            "compare",
            "compare_panel",
            "compare_variant",
            "estimate_relatedness",
            "get_stats",
            "list_all_subjects",
            "lookup_snp",
            "notable_findings",
            "run_all_panels",
            "run_panel",
            "search",
            "who_am_i",
        }

        self.assertTrue(expected.issubset(set(tools.__all__)))
        for name in expected:
            self.assertIs(getattr(tools, name), getattr(agent_tools, name))


if __name__ == "__main__":
    unittest.main()
