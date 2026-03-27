"""Shared subject-selection helpers for dashboard pages."""

from hda.config import get_active_subject, list_subjects


def get_dashboard_subject_state() -> tuple[dict, list[str], int]:
    """Return configured subjects, ordered keys, and default selection index."""
    subjects = list_subjects()
    subject_keys = list(subjects.keys())
    if not subject_keys:
        raise RuntimeError("No subjects are configured in config.yaml.")

    active = get_active_subject()
    default_index = subject_keys.index(active) if active in subject_keys else 0
    return subjects, subject_keys, default_index


def select_subject(sidebar, *, key: str, label: str = "Subject") -> str:
    """Render a sidebar subject selector constrained to configured keys only."""
    _, subject_keys, default_index = get_dashboard_subject_state()
    return sidebar.selectbox(label, subject_keys, index=default_index, key=key)
