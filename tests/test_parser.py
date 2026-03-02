"""Tests for model output parsing."""

from __future__ import annotations

import pytest
import json

from custom_components.sentry3d.const import (
    STATUS_EMPTY,
    STATUS_HEALTHY,
    STATUS_UNHEALTHY,
)
from custom_components.sentry3d.logic import parse_model_output


VALID_UNHEALTHY = """
{
  "status": "UNHEALTHY",
  "confidence": 0.83,
  "reason": "Visible spaghetti strands are forming above the part.",
  "short_explanation": "Spaghetti near nozzle",
  "signals": {
    "bed_adhesion_ok": false,
    "spaghetti_detected": true,
    "layer_shift_detected": false,
    "detached_part_detected": false,
    "blob_detected": false,
    "supports_failed_detected": false,
    "print_missing_detected": false
  }
}
"""


def test_parse_valid_unhealthy() -> None:
    result = parse_model_output(VALID_UNHEALTHY)
    assert result.status == STATUS_UNHEALTHY
    assert result.confidence == 0.83
    assert "spaghetti" in result.reason.lower()
    assert result.short_explanation == "Spaghetti near nozzle"
    assert result.signals["spaghetti_detected"] is True


def test_parse_rejects_non_json_wrapping() -> None:
    with pytest.raises(ValueError):
        parse_model_output(f"model says: {VALID_UNHEALTHY}")


def test_parse_rejects_healthy_with_defect_flags() -> None:
    invalid = {
        "status": STATUS_HEALTHY,
        "confidence": 0.92,
        "reason": "Looks fine.",
        "short_explanation": "Looks stable",
        "signals": {
            "bed_adhesion_ok": True,
            "spaghetti_detected": True,
            "layer_shift_detected": False,
            "detached_part_detected": False,
            "blob_detected": False,
            "supports_failed_detected": False,
            "print_missing_detected": False,
        },
    }

    with pytest.raises(ValueError):
        parse_model_output(json.dumps(invalid))


def test_parse_rejects_missing_short_explanation() -> None:
    invalid = {
        "status": STATUS_UNHEALTHY,
        "confidence": 0.8,
        "reason": "Visible spaghetti.",
        "signals": {
            "bed_adhesion_ok": False,
            "spaghetti_detected": True,
            "layer_shift_detected": False,
            "detached_part_detected": False,
            "blob_detected": False,
            "supports_failed_detected": False,
            "print_missing_detected": False,
        },
    }

    with pytest.raises(ValueError):
        parse_model_output(json.dumps(invalid))


def test_parse_valid_empty() -> None:
    payload = {
        "status": STATUS_EMPTY,
        "confidence": 0.97,
        "reason": "The build plate is visibly empty.",
        "short_explanation": "No active print",
        "signals": {
            "bed_adhesion_ok": False,
            "spaghetti_detected": False,
            "layer_shift_detected": False,
            "detached_part_detected": False,
            "blob_detected": False,
            "supports_failed_detected": False,
            "print_missing_detected": False,
        },
    }

    result = parse_model_output(json.dumps(payload))
    assert result.status == STATUS_EMPTY
    assert result.short_explanation == "No active print"
