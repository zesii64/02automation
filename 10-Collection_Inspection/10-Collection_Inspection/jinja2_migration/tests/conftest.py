"""pytest shared fixtures for jinja2_migration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    return HERE


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    return PROJECT_ROOT / "templates"


@pytest.fixture(scope="session")
def fixture_path() -> Path:
    """Path to the L1 context lock fixture JSON."""
    return HERE / "fixtures" / "real_data_baseline.json"


@pytest.fixture(scope="session")
def real_context(fixture_path: Path) -> dict[str, Any]:
    """Load the pinned real_data snapshot (lazy, session-scoped)."""
    if not fixture_path.exists():
        pytest.fail(
            f"Fixture not found: {fixture_path}\n"
            "Run `python dump_full_snapshot.py` to generate it."
        )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def jinja_env():
    """Build a Jinja2 environment pointing at PROJECT_ROOT / templates."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(PROJECT_ROOT / "templates")),
        autoescape=select_autoescape(("html", "j2")),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    return env
