import os

os.environ["COLUMNS"] = "200"  # keep Rich from wrapping CLI output in assertions

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_text() -> str:
    return (FIXTURES / "sample_agents.md").read_text()
