"""Tests for model output parsing."""

from __future__ import annotations

import json
import pytest

from custom_components.printersentry.const import STATUS_HEALTHY, STATUS_UNHEALTHY
from custom_components.printersentry.logic import parse_model_output


VALID_UNHEALTHY = """
{
  "status": "UNHEALTHY",
  "confidence": 0.83,
  "reason": "Visible spaghetti strands are forming above the part.",
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
    assert result.signals["spaghetti_detected"] is True


def test_parse_rejects_non_json_wrapping() -> None:
    with pytest.raises(ValueError):
        parse_model_output(f"model says: {VALID_UNHEALTHY}")


def test_parse_rejects_healthy_with_defect_flags() -> None:
    invalid = {
        "status": STATUS_HEALTHY,
        "confidence": 0.92,
        "reason": "Looks fine.",
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
