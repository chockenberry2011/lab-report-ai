import re


def normalize_result_id(s: str) -> str:
    """
    Normalize a result/job id by stripping known debug/stage suffixes.

    Examples:
    - "abcd-1234.03_compose.debug" -> "abcd-1234"
    - "abcd-1234.debug" -> "abcd-1234"
    - "abcd-1234" -> "abcd-1234"
    """
    if not isinstance(s, str):
        return s

    # Strip the most specific suffix first
    for suffix in (".03_compose.debug", ".debug"):
        if s.endswith(suffix):
            return s[: -len(suffix)]
    return s

