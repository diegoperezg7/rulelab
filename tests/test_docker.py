"""Needs a running Docker daemon. CI runs these on Linux only (macOS runners have no Docker)."""

import pytest

from rulelab import engine


@pytest.mark.docker
def test_docker_preflight_passes():
    engine.check_docker()

