# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/model
# ---
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class {{NAME}}Model:
    """ML model: trained on {{UPSTREAM}}, predictions consumed by {{DOWNSTREAM}}."""

    def __init__(self) -> None:
        self._model: Any = None

    def train(self, X: np.ndarray, y: np.ndarray) -> None:
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model not trained — call train() first")
        raise NotImplementedError

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict[str, float]:
        raise NotImplementedError
