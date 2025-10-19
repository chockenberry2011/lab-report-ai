"""
TestRow pipeline initializer for runtime inference.

Provides a single entrypoint `build_testrow_pipeline()` that loads the
model once and exposes a consistent API used by the worker compose step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os

from services.worker.models.testrow_loader import (
    TestRowModelAdapter,
    load_testrow_adapter,
)


@dataclass
class TestRowPipeline:
    """Thin wrapper around TestRowModelAdapter with a stable interface."""

    adapter: TestRowModelAdapter
    name: str = "crf-pipeline"

    def predict(self, tokens: List[str]) -> List[str]:
        return self.adapter.predict(tokens)

    def predict_proba(self, tokens: List[str]) -> List[Dict[str, float]]:
        return self.adapter.predict_proba(tokens)


def build_testrow_pipeline() -> Optional[TestRowPipeline]:
    """
    Initialize and return the singleton pipeline used for parsing test rows.

    - Reads MODEL_TESTROW_DIR or defaults to /models/testrow
    - Returns None if no model artifacts are found
    """
    model_dir = os.getenv("MODEL_TESTROW_DIR", "/models/testrow")
    adapter = load_testrow_adapter(model_dir)
    if adapter is None:
        return None
    return TestRowPipeline(adapter=adapter, name="crf-pipeline")

