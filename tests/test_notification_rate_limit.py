"""Tests for notification rate-limiting logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.sentry3d.logic import should_send_notification


def test_notification_sent_for_new_incident() -> None:
    now = datetime.now(UTC)
    assert should_send_notification(
        incident_active=True,
        new_incident=True,
        last_notification_time=now,
        now=now,
        min_notification_interval_sec=300,
    )


def test_notification_suppressed_inside_interval() -> None:
    now = datetime.now(UTC)
    last_notification = now - timedelta(seconds=120)

    assert not should_send_notification(
        incident_active=True,
        new_incident=False,
        last_notification_time=last_notification,
        now=now,
        min_notification_interval_sec=300,
    )


def test_notification_allowed_after_interval_elapsed() -> None:
    now = datetime.now(UTC)
    last_notification = now - timedelta(seconds=301)

    assert should_send_notification(
        incident_active=True,
        new_incident=False,
        last_notification_time=last_notification,
        now=now,
        min_notification_interval_sec=300,
    )


def test_notification_suppressed_when_incident_not_active() -> None:
    now = datetime.now(UTC)
    assert not should_send_notification(
        incident_active=False,
        new_incident=True,
        last_notification_time=None,
        now=now,
        min_notification_interval_sec=0,
    )
