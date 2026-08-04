"""Test that alembic autogenerate detects no drift after running all migrations."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from src.config.database import BaseModel


@pytest.fixture(scope="module")
def test_db_url(postgres_service):
    """Return PostgreSQL database URL for testing (same fixture as conftest)."""
    return postgres_service


def test_autogenerate_detects_no_drift(test_db_url):
    """Run all migrations from scratch, then verify autogenerate is empty.

    The test drops all tables and clears the alembic_version table to ensure
    a clean slate — other tests may have left the DB in an inconsistent state
    (e.g., tables dropped via BaseModel.metadata.drop_all but alembic_version
    still at head).
    """
    repo_root = Path(__file__).resolve().parent.parent
    versions_dir = repo_root / "migrations" / "versions"

    # Convert asyncpg URL to sync postgresql:// for the sync SQLAlchemy engine
    # used to clean up the DB.
    sync_db_url = test_db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Pass the async URL — env.py converts it to sync internally.
    # The app's DatabaseSessionManager needs an async driver, so we
    # must keep the asyncpg dialect in DATABASE_URL for the subprocess.
    db_url = test_db_url

    env = {
        **os.environ,
        "DATABASE_URL": db_url,
    }

    generated = None
    try:
        # Clean slate: drop all tables and clear alembic_version
        engine = create_engine(sync_db_url)
        with engine.begin() as conn:
            BaseModel.metadata.drop_all(conn)
            conn.execute(text("DELETE FROM alembic_version"))
        engine.dispose()

        # Run all migrations to head
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            check=True,
            cwd=repo_root,
        )

        # Attempt autogenerate
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "revision",
                "--autogenerate",
                "-m",
                "check",
            ],
            env=env,
            check=True,
            cwd=repo_root,
        )

        # Find the newest generated file by mtime
        generated = max(versions_dir.glob("*.py"), key=lambda p: p.stat().st_mtime)

        # Read the body (skip docstring, revision vars, and blank lines)
        with generated.open() as f:
            body = f.read()

        # Assert no op. calls in the generated migration
        assert re.search(r"\bop\.\w+\(", body) is None, (
            f"Autogenerate detected drift in {generated.name}"
        )
    finally:
        # Clean up the generated migration file
        if generated is not None:
            generated.unlink(missing_ok=True)
