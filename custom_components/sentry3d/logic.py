"""Core parsing and incident logic for Sentry3D."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from .const import STATUS_EMPTY, STATUS_HEALTHY, STATUS_UNHEALTHY, STATUS_UNKNOWN

REQUIRED_SIGNAL_KEYS = (
    "bed_adhesion_ok",
    "spaghetti_detected",
    "layer_shift_detected",
    "detached_part_detected",
    "blob_detected",
    "supports_failed_detected",
    "print_missing_detected",
)

DEFECT_SIGNAL_KEYS = (
    "spaghetti_detected",
    "layer_shift_detected",
    "detached_part_detected",
    "blob_detected",
    "supports_failed_detected",
    "print_missing_detected",
)


@dataclass(slots=True)
class InferenceResult:
    """Normalized model output."""

    status: str
    confidence: float | None
    reason: str
    short_explanation: str
    signals: dict[str, bool]


@dataclass(slots=True)
class IncidentTransition:
    """State transition for consecutive unhealthy and incidents."""

    consecutive_unhealthy_count: int
    incident_active: bool
    new_incident: bool
    cleared_incident: bool


def parse_model_output(raw_text: str) -> InferenceResult:
    """Parse and validate strict JSON output from Ollama."""
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("Empty model output")

    # Require a single JSON object as the complete output.
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise ValueError("Model output contains non-JSON content")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as err:
        raise ValueError("Invalid JSON output") from err

    if not isinstance(payload, dict):
        raise ValueError("Output must be a JSON object")

    status = payload.get("status")
    if status not in (STATUS_HEALTHY, STATUS_UNHEALTHY, STATUS_EMPTY):
        raise ValueError("Invalid status")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("Confidence must be numeric")
    confidence = float(confidence)
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("Confidence must be between 0 and 1 (exclusive)")

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Reason must be a non-empty string")
    reason = reason.strip()

    short_explanation = payload.get("short_explanation")
    if not isinstance(short_explanation, str) or not short_explanation.strip():
        raise ValueError("short_explanation must be a non-empty string")
    short_explanation = short_explanation.strip()

    signals_raw = payload.get("signals")
    if not isinstance(signals_raw, dict):
        raise ValueError("Signals must be an object")

    signal_keys = set(signals_raw)
    required_keys = set(REQUIRED_SIGNAL_KEYS)
    if signal_keys != required_keys:
        missing = sorted(required_keys - signal_keys)
        extra = sorted(signal_keys - required_keys)
        raise ValueError(f"Signals keys mismatch: missing={missing}, extra={extra}")

    signals: dict[str, bool] = {}
    for key in REQUIRED_SIGNAL_KEYS:
        value = signals_raw.get(key)
        if not isinstance(value, bool):
            raise ValueError(f"Signal {key} must be boolean")
        signals[key] = value

    if status == STATUS_HEALTHY and any(signals[key] for key in DEFECT_SIGNAL_KEYS):
        raise ValueError("Healthy output cannot have defect signals set")
    if status == STATUS_EMPTY and any(signals.values()):
        raise ValueError("Empty output cannot have any signals set")

    return InferenceResult(
        status=status,
        confidence=confidence,
        reason=reason,
        short_explanation=short_explanation,
        signals=signals,
    )


def unknown_result(reason: str) -> InferenceResult:
    """Create a normalized unknown result."""
    return InferenceResult(
        status=STATUS_UNKNOWN,
        confidence=None,
        reason=reason,
        short_explanation="No valid result",
        signals={key: False for key in REQUIRED_SIGNAL_KEYS},
    )


def apply_incident_logic(
    *,
    current_status: str,
    previous_consecutive_unhealthy: int,
    incident_active: bool,
    unhealthy_consecutive_threshold: int,
) -> IncidentTransition:
    """Transition consecutive unhealthy counter and incident state."""
    consecutive = previous_consecutive_unhealthy
    new_incident = False
    cleared_incident = False

    if current_status == STATUS_UNHEALTHY:
        consecutive += 1
        if not incident_active and consecutive >= unhealthy_consecutive_threshold:
            incident_active = True
            new_incident = True
    elif current_status in (STATUS_HEALTHY, STATUS_EMPTY):
        consecutive = 0
        if incident_active:
            incident_active = False
            cleared_incident = True

    return IncidentTransition(
        consecutive_unhealthy_count=consecutive,
        incident_active=incident_active,
        new_incident=new_incident,
        cleared_incident=cleared_incident,
    )


def should_send_notification(
    *,
    incident_active: bool,
    new_incident: bool,
    last_notification_time: datetime | None,
    now: datetime,
    min_notification_interval_sec: int,
) -> bool:
    """Determine whether a notification should be sent."""
    if not incident_active:
        return False
    if new_incident:
        return True
    if last_notification_time is None:
        return True
    return (now - last_notification_time) >= timedelta(
        seconds=min_notification_interval_sec
    )
