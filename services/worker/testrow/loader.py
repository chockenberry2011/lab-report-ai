# Compatibility shim for older workers that import services.worker.testrow.loader
from pathlib import Path
import json, joblib

def load_model(model_dir):
    """
    Return (model, labels) loaded from model_dir without requiring label_encoder.pkl.
    """
    d = Path(model_dir)
    model_path = None
    for name in ("model.crf", "crf.joblib", "model.joblib"):
        p = d / name
        if p.exists():
            model_path = p
            break
    if not model_path:
        raise FileNotFoundError(f"No CRF model file found in {d}")
    crf = joblib.load(model_path)
    labels = []
    meta = d / "metadata.json"
    if meta.exists():
        md = json.loads(meta.read_text(encoding="utf-8"))
        for key in ("labels", "label_list", "classes"):
            if isinstance(md.get(key), list) and md[key]:
                labels = list(md[key]); break
    if not labels:
        classes = getattr(crf, "classes_", None)
        labels = list(classes) if isinstance(classes, (list, tuple)) else []
    if not labels:
        labels = ["O","B-TEST_NAME","I-TEST_NAME","B-VALUE","I-VALUE","B-UNIT","I-UNIT","B-REF_RANGE","I-REF_RANGE","B-FLAG","I-FLAG"]
    return crf, labels