import re

# Suffixes we may see on result IDs that should not be used to key storage.
_SUFFIXES = (
    ".03_compose.debug",
    ".03_compose",
    ".debug",
)


def normalize_result_id(value: str) -> str:
    """
    Normalize a result_id coming from routes like:
      - <uuid>
      - <uuid>.03_compose
      - <uuid>.03_compose.debug
      - <uuid>.debug
    Returns the base <uuid> without trailing slashes or known suffixes.
    """
    if not isinstance(value, str):
        return value
    s = value.strip().rstrip("/")
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s

