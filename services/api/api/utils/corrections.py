from typing import Any, List, Dict, Union
from copy import deepcopy
from .paths import split_path

CorrectionItem = Dict[str, Any]

def _ensure_parent(container: Union[dict, list], seg):
    return container

def set_by_path(obj: Any, path: str, value: Any) -> Any:
    parts = split_path(path)
    cur = obj
    for i, seg in enumerate(parts):
        is_last = i == len(parts) - 1
        if isinstance(seg, int):
            if not isinstance(cur, list):
                # convert non-list to list if needed
                nxt = []
                if isinstance(cur, dict):
                    # cannot place list directly inside dict without a key;
                    # caller ensures we navigated via a list key earlier.
                    pass
                return obj  # bail (invalid structure)
            # grow list
            while len(cur) <= seg:
                cur.append(None)
            if is_last:
                cur[seg] = value
            else:
                if cur[seg] is None:
                    # create intermediate dict by default
                    cur[seg] = {}
                cur = cur[seg]
        else:
            # dict segment
            if not isinstance(cur, dict):
                return obj
            if is_last:
                cur[seg] = value
            else:
                if seg not in cur or cur[seg] is None:
                    # create next container; prefer dict
                    cur[seg] = {}
                cur = cur[seg]
    return obj

def unset_by_path(obj: Any, path: str) -> Any:
    parts = split_path(path)
    cur = obj
    for i, seg in enumerate(parts):
        is_last = i == len(parts) - 1
        if isinstance(seg, int):
            if not isinstance(cur, list) or seg >= len(cur):
                return obj
            if is_last:
                cur[seg] = None
            else:
                cur = cur[seg]
        else:
            if not isinstance(cur, dict) or seg not in cur:
                return obj
            if is_last:
                cur.pop(seg, None)
            else:
                cur = cur[seg]
    return obj

def apply_corrections(base: Dict[str, Any], items: List[CorrectionItem]) -> Dict[str, Any]:
    doc = deepcopy(base)
    for it in items or []:
        op = (it.get("op") or "set").lower()
        path = it.get("path")
        if not path:
            continue
        if op == "unset":
            unset_by_path(doc, path)
        elif op in ("set", "add", "replace", ""):
            set_by_path(doc, path, it.get("value"))
        elif op == "append":
            # limited: append only if target is list
            parts = split_path(path)
            cur = doc
            for seg in parts:
                cur = cur[seg] if isinstance(seg, int) else cur.get(seg, None)
                if cur is None:
                    break
            if isinstance(cur, list):
                cur.append(it.get("value"))
        else:
            # ignore unknown ops
            pass
    return doc