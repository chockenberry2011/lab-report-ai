import re

_bracket_re = re.compile(r"\[(\d+)\]")

def split_path(path: str):
    """
    Accepts:
      - dot path: panels[0].tests[2].value
      - json pointer: /panels/0/tests/2/value
    Returns list of segments where array indices are ints.
    """
    if not path:
        return []
    if path.startswith("/"):  # JSON Pointer
        parts = [p for p in path.split("/") if p != ""]
    else:
        parts = []
        for token in path.split("."):
            # split token like tests[2][3] -> ["tests", 2, 3]
            head, *rest = _bracket_re.split(token)
            if head:
                parts.append(head)
            for i, seg in enumerate(rest):
                if i % 2 == 0 and seg != "":
                    # text between bracket groups (unlikely)
                    parts.append(seg)
                elif seg.isdigit():
                    parts.append(int(seg))
    # convert numeric strings from pointer to ints
    norm = []
    for p in parts:
        if isinstance(p, str) and p.isdigit():
            norm.append(int(p))
        else:
            norm.append(p)
    return norm