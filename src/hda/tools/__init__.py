"""Stable agent-facing API surface for HDA.

Import from ``hda.tools`` or ``hda.tools.agent_tools`` when building agents on
top of the project. Internal modules under ``hda.analysis``, ``hda.db``, and
``hda.api`` may evolve faster.
"""

from hda.tools.agent_tools import (
    annotate,
    annotate_my_snp,
    available_panels,
    compare,
    compare_panel,
    compare_variant,
    estimate_relatedness,
    get_stats,
    list_all_subjects,
    lookup_snp,
    notable_findings,
    run_all_panels,
    run_panel,
    search,
    who_am_i,
)

__all__ = [
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
]
