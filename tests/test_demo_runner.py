"""Startup checks and vector auto-seed."""
import pytest

from config.settings import get_settings
from layers.pipeline.demo_runner import ensure_vector_memory, run_startup_checks


@pytest.fixture
def settings():
    return get_settings()


@pytest.mark.asyncio
async def test_run_startup_checks(settings):
    result = await run_startup_checks(settings)
    assert "input_validation" in result
    assert "memory" in result
    assert "ready" in result


def test_ensure_vector_memory_returns_shape(settings):
    mem = ensure_vector_memory(settings)
    assert "count" in mem
    assert "source" in mem
