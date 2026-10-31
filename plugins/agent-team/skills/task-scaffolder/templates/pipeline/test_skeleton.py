# --- artifact metadata ---
# owner_agent: {{OWNER_AGENT}}
# upstream:    {{UPSTREAM}}
# downstream:  {{DOWNSTREAM}}
# created_at:  {{CREATED_AT}}
# template:    task-scaffolder/pipeline
# ---
from unittest.mock import MagicMock, patch

import pytest

from .skeleton import {{NAME}}Pipeline


@pytest.fixture()
def pipeline() -> {{NAME}}Pipeline:
    return {{NAME}}Pipeline()


def test_run_calls_extract_transform_load(pipeline: {{NAME}}Pipeline) -> None:
    pipeline.extract = MagicMock(return_value=[{"id": 1}])
    pipeline.transform = MagicMock(return_value=[{"id": 1}])
    pipeline.load = MagicMock(return_value=1)

    result = pipeline.run()

    assert result == 1
    pipeline.extract.assert_called_once()
    pipeline.transform.assert_called_once_with([{"id": 1}])
    pipeline.load.assert_called_once_with([{"id": 1}])


def test_extract_raises_not_implemented(pipeline: {{NAME}}Pipeline) -> None:
    with pytest.raises(NotImplementedError):
        pipeline.extract()
