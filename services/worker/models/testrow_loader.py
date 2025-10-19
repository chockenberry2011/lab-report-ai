"""
Test-Row model loader and adapter.

Provides a thin compatibility layer so the worker can run with either
- sklearn-crfsuite model saved as `model.crf`, or
- joblib-serialized estimator saved as `crf.joblib`.

The adapter exposes a consistent API:
  - predict(tokens: List[str]) -> List[str]
  - predict_proba(tokens: List[str]) -> List[Dict[str, float]]
  - labels: List[str]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import joblib


def _basic_token_features(seq: List[str], i: int) -> Dict[str, Any]:
    w = seq[i]
    feats = {
        "bias": 1.0,
        "w.lower": w.lower(),
        "w.isdigit": w.isdigit(),
        "w.hasdigit": any(ch.isdigit() for ch in w),
        "w.has%": "%" in w,
        "w.has/": "/" in w,
        "w.has-": "-" in w or "–" in w or "—" in w,
        "w.sfx2": w[-2:] if len(w) >= 2 else w,
        "w.pfx2": w[:2],
    }
    if i > 0:
        wp = seq[i - 1]
        feats.update(
            {
                "-1.lower": wp.lower(),
                "-1.hasdigit": any(ch.isdigit() for ch in wp),
                "-1.has/": "/" in wp,
                "-1.has-": "-" in wp,
            }
        )
    else:
        feats["BOS"] = True
    if i < len(seq) - 1:
        wn = seq[i + 1]
        feats.update(
            {
                "+1.lower": wn.lower(),
                "+1.hasdigit": any(ch.isdigit() for ch in wn),
                "+1.has/": "/" in wn,
                "+1.has-": "-" in wn,
            }
        )
    else:
        feats["EOS"] = True
    return feats


@dataclass
class TestRowModelAdapter:
    estimator: Any
    labels: List[str]

    def predict(self, tokens: List[str]) -> List[str]:
        # Build simple CRF-style features as a robust default
        try:
            X = [[_basic_token_features(tokens, i) for i in range(len(tokens))]]
            y = self.estimator.predict(X)
            if y and isinstance(y, list):
                return list(y[0])
        except Exception:
            pass
        # Last resort: return all "O" tags to keep behavior safe
        return ["O"] * len(tokens)

    def predict_proba(self, tokens: List[str]) -> List[Dict[str, float]]:
        # Try common sklearn-crfsuite APIs
        try:
            X = [[_basic_token_features(tokens, i) for i in range(len(tokens))]]
            if hasattr(self.estimator, "predict_marginals_single"):
                # Single sentence interface
                marginals = self.estimator.predict_marginals_single(X[0])
                return [dict(m) if isinstance(m, dict) else {} for m in marginals]
            if hasattr(self.estimator, "predict_marginals"):
                marginals = self.estimator.predict_marginals(X)
                if marginals and isinstance(marginals, list):
                    return [dict(m) if isinstance(m, dict) else {} for m in marginals[0]]
        except Exception:
            pass
        # Unknown estimator; return empty distributions per token
        return [{} for _ in tokens]


def _read_labels_from_metadata(dir_path: Path) -> Optional[List[str]]:
    meta = dir_path / "metadata.json"
    if not meta.exists():
        return None
    try:
        with open(meta, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in ("labels", "label_list", "classes"):
            v = data.get(key)
            if isinstance(v, list):
                return list(v)
    except Exception:
        return None
    return None


def load_testrow_adapter(model_dir: str | Path) -> Optional[TestRowModelAdapter]:
    d = Path(model_dir)
    if not d.exists():
        return None

    # Artifact preference
    for fname in ("model.crf", "crf.joblib"):
        p = d / fname
        if p.exists():
            try:
                est = joblib.load(str(p))
            except Exception:
                continue
            labels = _read_labels_from_metadata(d) or [
                "O",
                "B-TEST_NAME",
                "I-TEST_NAME",
                "B-VALUE",
                "I-VALUE",
                "B-UNIT",
                "I-UNIT",
                "B-REF_RANGE",
                "I-REF_RANGE",
                "B-FLAG",
                "I-FLAG",
            ]
            return TestRowModelAdapter(estimator=est, labels=labels)
    return None

