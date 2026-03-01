"""Tests for incident transition logic."""

from __future__ import annotations

from custom_components.printersentry.const import STATUS_HEALTHY, STATUS_UNHEALTHY, STATUS_UNKNOWN
from custom_components.printersentry.logic import apply_incident_logic


def test_incident_triggers_on_threshold() -> None:
    transition = apply_incident_logic(
        current_status=STATUS_UNHEALTHY,
        previous_consecutive_unhealthy=2,
        incident_active=False,
        unhealthy_consecutive_threshold=3,
    )

    assert transition.consecutive_unhealthy_count == 3
    assert transition.incident_active is True
    assert transition.new_incident is True
    assert transition.cleared_incident is False


def test_incident_clears_on_healthy() -> None:
    transition = apply_incident_logic(
        current_status=STATUS_HEALTHY,
        previous_consecutive_unhealthy=5,
        incident_active=True,
        unhealthy_consecutive_threshold=3,
    )

    assert transition.consecutive_unhealthy_count == 0
    assert transition.incident_active is False
    assert transition.new_incident is False
    assert transition.cleared_incident is True


def test_unknown_does_not_change_active_incident_counter() -> None:
    transition = apply_incident_logic(
        current_status=STATUS_UNKNOWN,
        previous_consecutive_unhealthy=4,
        incident_active=True,
        unhealthy_consecutive_threshold=3,
    )

    assert transition.consecutive_unhealthy_count == 4
    assert transition.incident_active is True
    assert transition.new_incident is False
    assert transition.cleared_incident is False
