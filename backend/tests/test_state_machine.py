"""Test report status state machine validation logic."""

import pytest

from app.modules.reports.service import compute_sla_due
from datetime import datetime, timedelta, UTC


def test_sla_urgent():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    due = compute_sla_due("urgent", now)
    assert due == now + timedelta(hours=2)


def test_sla_low():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    due = compute_sla_due("low", now)
    assert due == now + timedelta(hours=72)


def test_sla_unknown_falls_back_to_24h():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    due = compute_sla_due("xxx", now)
    assert due == now + timedelta(hours=24)
