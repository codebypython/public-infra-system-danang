"""Pytest fixtures — async DB, FastAPI test client, factory helpers.

Tests run against a disposable Postgres+PostGIS testcontainer (or override via
TEST_DATABASE_URL env). For pure unit tests of pure functions, no DB is needed.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure test settings are picked up
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DEBUG", "false")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
