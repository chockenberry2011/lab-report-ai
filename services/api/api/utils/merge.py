from pathlib import Path
import json
from .corrections import apply_corrections

def load_corrections(results_dir: Path, base_id: str):
    p = results_dir / base_id / "corrections.json"
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text("utf-8"))
        return doc.get("items") or []
    except Exception:
        return []