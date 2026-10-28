import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_guide() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "sample_guide.json").read_text())
    return data
