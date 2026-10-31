# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/pipeline
# ---
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class {{NAME}}Pipeline:
    """ETL pipeline: {{UPSTREAM}} → {{DOWNSTREAM}}."""

    def extract(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def load(self, records: list[dict[str, Any]]) -> int:
        raise NotImplementedError

    def run(self) -> int:
        logger.info("Pipeline %s started", self.__class__.__name__)
        raw = self.extract()
        transformed = self.transform(raw)
        count = self.load(transformed)
        logger.info("Pipeline done — %d rows loaded", count)
        return count
