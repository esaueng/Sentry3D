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
    focus_region: dict[str, float] | None


@dataclass(slots=True)
class IncidentTransition:
    """State transition for consecutive unhealthy and incidents."""

    consecutive_unhealthy_count: int
    incident_active: bool
    new_incident: bool
    cleared_incident: bool


def _normalize_short_explanation(text: str, fallback: str = "Unknown") -> str:
    """Build a concise UI-friendly summary from a longer message."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return fallback

    normalized = normalized.replace("build plate", "bed").replace("print bed", "bed")
    lowered = normalized.lower()

    phrase_replacements = (
        ("there is ", ""),
        ("there are ", ""),
        ("is present on the ", ""),
        ("is present on ", ""),
        ("present on the ", ""),
        ("present on ", ""),
        ("appears to be ", ""),
        ("appears ", ""),
        ("visible ", ""),
        ("visibly ", ""),
        ("detected ", ""),
    )
    for source, target in phrase_replacements:
        lowered = lowered.replace(source, target)
    normalized = " ".join(lowered.split())

    for prefix in ("the ", "a ", "an "):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break

    for separator in (":", ";", ".", ",", "\n"):
        normalized = normalized.split(separator, 1)[0].strip()
        if normalized:
            break

    words = normalized.split()
    if len(words) > 3:
        normalized = " ".join(words[:3])

    words = normalized.split()
    trailing_stop_words = {"on", "the", "a", "an", "at", "with", "from", "of", "to"}
    while words and words[-1] in trailing_stop_words:
        words.pop()
    if words:
        normalized = " ".join(words)

    if len(normalized) > 20:
        normalized = f"{normalized[:17].rstrip()}..."

    if normalized:
        normalized = normalized[0].upper() + normalized[1:]

    return normalized or fallback


def _derive_short_explanation(text: str, fallback: str = "Unknown") -> str:
    """Derive a short explanation from a longer reason string."""
    return _normalize_short_explanation(text, fallback)


def _normalize_reason(text: str) -> str:
    """Normalize the model reason to a short single-sentence summary."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return ""

    for separator in (".", ";", "\n"):
        normalized = normalized.split(separator, 1)[0].strip()
        if normalized:
            break

    words = normalized.split()
    if len(words) > 8:
        normalized = " ".join(words[:8])

    if len(normalized) > 56:
        normalized = f"{normalized[:53].rstrip()}..."

    if normalized:
        normalized = normalized[0].upper() + normalized[1:]

    return normalized


def parse_model_output(raw_text: str) -> InferenceResult:
    """Parse and validate strict JSON output from Ollama."""
    stripped = _extract_json_object(raw_text)
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
    if isinstance(status, str):
        status = status.strip().upper()
    if status not in (STATUS_HEALTHY, STATUS_UNHEALTHY, STATUS_EMPTY):
        raise ValueError("Invalid status")

    confidence = payload.get("confidence")
    if isinstance(confidence, str):
        try:
            confidence = float(confidence.strip())
        except ValueError as err:
            raise ValueError("Confidence must be numeric") from err
    elif not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("Confidence must be numeric")
    else:
        confidence = float(confidence)
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("Confidence must be between 0 and 1 (exclusive)")

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Reason must be a non-empty string")
    reason = _normalize_reason(reason)
    if not reason:
        raise ValueError("Reason must be a non-empty string")

    short_explanation = payload.get("short_explanation")
    if isinstance(short_explanation, str) and short_explanation.strip():
        short_explanation = _normalize_short_explanation(short_explanation)
    else:
        short_explanation = _derive_short_explanation(reason)

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
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                value = True
            elif lowered == "false":
                value = False
        if not isinstance(value, bool):
            raise ValueError(f"Signal {key} must be boolean")
        signals[key] = value

    if status == STATUS_HEALTHY and any(signals[key] for key in DEFECT_SIGNAL_KEYS):
        raise ValueError("Healthy output cannot have defect signals set")
    if status == STATUS_EMPTY and any(signals.values()):
        raise ValueError("Empty output cannot have any signals set")

    focus_region_raw = payload.get("focus_region")
    focus_region = _parse_focus_region(focus_region_raw)

    if status != STATUS_UNHEALTHY:
        focus_region = None

    return InferenceResult(
        status=status,
        confidence=confidence,
        reason=reason,
        short_explanation=short_explanation,
        signals=signals,
        focus_region=focus_region,
    )


def _parse_focus_region(focus_region_raw: object) -> dict[str, float] | None:
    """Parse a focus region, dropping invalid overlays instead of failing inference."""
    if focus_region_raw is None or not isinstance(focus_region_raw, dict):
        return None

    required_region_keys = {"x", "y", "width", "height"}
    if set(focus_region_raw) != required_region_keys:
        return None

    focus_region: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        value = focus_region_raw.get(key)
        if isinstance(value, str):
            try:
                value = float(value.strip())
            except ValueError:
                return None
        elif not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        else:
            value = float(value)
        focus_region[key] = value

    if (
        focus_region["x"] < 0.0
        or focus_region["y"] < 0.0
        or focus_region["width"] <= 0.0
        or focus_region["height"] <= 0.0
        or focus_region["x"] > 1.0
        or focus_region["y"] > 1.0
        or focus_region["width"] > 1.0
        or focus_region["height"] > 1.0
        or focus_region["x"] + focus_region["width"] > 1.0
        or focus_region["y"] + focus_region["height"] > 1.0
    ):
        return None

    return focus_region


def unknown_result(reason: str) -> InferenceResult:
    """Create a normalized unknown result."""
    return InferenceResult(
        status=STATUS_UNKNOWN,
        confidence=None,
        reason=reason,
        short_explanation=_derive_short_explanation(reason),
        signals={key: False for key in REQUIRED_SIGNAL_KEYS},
        focus_region=None,
    )


def _extract_json_object(raw_text: str) -> str:
    """Extract the main JSON object from raw model text."""
    stripped = raw_text.strip()
    if not stripped:
        return ""

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1].strip()

    return stripped


def is_confident_unhealthy(
    *,
    status: str,
    confidence: float | None,
    threshold: float,
) -> bool:
    """Return True when an unhealthy result clears the confidence gate."""
    return (
        status == STATUS_UNHEALTHY
        and confidence is not None
        and confidence >= threshold
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
