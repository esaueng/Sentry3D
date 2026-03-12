"""Tests for model output parsing."""

from __future__ import annotations

import pytest
import json

from custom_components.sentry3d.const import (
    STATUS_EMPTY,
    STATUS_HEALTHY,
    STATUS_UNHEALTHY,
)
from custom_components.sentry3d.logic import parse_model_output, unknown_result


VALID_UNHEALTHY = """
{
  "status": "UNHEALTHY",
  "confidence": 0.83,
  "reason": "Visible spaghetti strands are forming above the part.",
  "short_explanation": "Spaghetti near nozzle",
  "focus_region": {
    "x": 0.42,
    "y": 0.19,
    "width": 0.21,
    "height": 0.33
  },
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
    assert result.focus_region == {
        "x": 0.42,
        "y": 0.19,
        "width": 0.21,
        "height": 0.33,
    }


def test_parse_normalizes_long_short_explanation() -> None:
    payload = json.loads(VALID_UNHEALTHY)
    payload["short_explanation"] = "The build plate appears clean and stable"

    result = parse_model_output(json.dumps(payload))
    assert result.short_explanation == "Bed clean stable"


def test_parse_strips_filler_from_short_explanation() -> None:
    payload = json.loads(VALID_UNHEALTHY)
    payload["short_explanation"] = "Loose filament is present on the build plate"

    result = parse_model_output(json.dumps(payload))
    assert result.short_explanation == "Loose filament bed"


def test_parse_normalizes_long_reason() -> None:
    payload = json.loads(VALID_UNHEALTHY)
    payload["reason"] = "Visible spaghetti strands are forming above the part and curling around the nozzle."

    result = parse_model_output(json.dumps(payload))
    assert result.reason == "Visible spaghetti strands are forming above the part"


def test_parse_accepts_code_fenced_json_and_string_values() -> None:
    payload = {
        "status": "unhealthy",
        "confidence": "0.83",
        "reason": "There is spaghetti on the bed.",
        "short_explanation": "There is spaghetti on the bed",
        "focus_region": {
            "x": "0.42",
            "y": "0.19",
            "width": "0.21",
            "height": "0.33",
        },
        "signals": {
            "bed_adhesion_ok": "false",
            "spaghetti_detected": "true",
            "layer_shift_detected": "false",
            "detached_part_detected": "false",
            "blob_detected": "false",
            "supports_failed_detected": "false",
            "print_missing_detected": "false",
        },
    }

    result = parse_model_output(f"```json\n{json.dumps(payload)}\n```")
    assert result.status == STATUS_UNHEALTHY
    assert result.confidence == 0.83
    assert result.short_explanation == "Spaghetti on the bed"


def test_parse_rejects_non_json_wrapping() -> None:
    with pytest.raises(ValueError):
        parse_model_output(f"model says: {VALID_UNHEALTHY}")


def test_parse_rejects_healthy_with_defect_flags() -> None:
    invalid = {
        "status": STATUS_HEALTHY,
        "confidence": 0.92,
        "reason": "Looks fine.",
        "short_explanation": "Looks stable",
        "focus_region": None,
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


def test_parse_derives_missing_short_explanation() -> None:
    payload = {
        "status": STATUS_UNHEALTHY,
        "confidence": 0.8,
        "reason": "Visible spaghetti.",
        "focus_region": None,
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

    result = parse_model_output(json.dumps(payload))
    assert result.short_explanation == "Visible spaghetti"


def test_parse_valid_empty() -> None:
    payload = {
        "status": STATUS_EMPTY,
        "confidence": 0.97,
        "reason": "The build plate is visibly empty.",
        "short_explanation": "No active print",
        "focus_region": None,
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
    assert result.focus_region is None


def test_parse_drops_focus_region_for_non_unhealthy() -> None:
    payload = {
        "status": STATUS_HEALTHY,
        "confidence": 0.91,
        "reason": "The print looks stable.",
        "short_explanation": "Looks good",
        "focus_region": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2},
        "signals": {
            "bed_adhesion_ok": True,
            "spaghetti_detected": False,
            "layer_shift_detected": False,
            "detached_part_detected": False,
            "blob_detected": False,
            "supports_failed_detected": False,
            "print_missing_detected": False,
        },
    }

    result = parse_model_output(json.dumps(payload))
    assert result.status == STATUS_HEALTHY
    assert result.focus_region is None


def test_parse_drops_invalid_focus_region_bounds() -> None:
    payload = {
        "status": STATUS_UNHEALTHY,
        "confidence": 0.74,
        "reason": "A blob is visible on the right side.",
        "short_explanation": "Blob forming",
        "focus_region": {"x": 0.85, "y": 0.2, "width": 0.3, "height": 0.2},
        "signals": {
            "bed_adhesion_ok": False,
            "spaghetti_detected": False,
            "layer_shift_detected": False,
            "detached_part_detected": False,
            "blob_detected": True,
            "supports_failed_detected": False,
            "print_missing_detected": False,
        },
    }

    result = parse_model_output(json.dumps(payload))
    assert result.status == STATUS_UNHEALTHY
    assert result.focus_region is None


def test_unknown_result_derives_short_explanation() -> None:
    result = unknown_result("Invalid model JSON response: short_explanation missing")
    assert result.short_explanation == "Invalid model JSON response"
