"""Data coordinator for Sentry3D."""

from __future__ import annotations

import asyncio
import base64
from collections import deque
from datetime import datetime, timedelta
import hashlib
from io import BytesIO
import logging
import random
import subprocess
from typing import Any

import aiohttp
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CAPTURE_METHOD_OPENCV,
    CONF_CAPTURE_METHOD,
    CONF_CHECK_INTERVAL_SEC,
    CONF_HISTORY_SIZE,
    CONF_LLM_PROVIDER,
    CONF_MAX_BACKOFF_SEC,
    CONF_MIN_NOTIFICATION_INTERVAL_SEC,
    CONF_MOTION_DETECTION_ENABLED,
    CONF_MOTION_THRESHOLD,
    CONF_NOTIFY_ON_INCIDENT,
    CONF_OLLAMA_BASE_URL,
    CONF_OLLAMA_MODEL,
    CONF_OLLAMA_TIMEOUT_SEC,
    CONF_OPENAI_API_KEY,
    CONF_OPENAI_BASE_URL,
    CONF_OPENAI_MODEL,
    CONF_RTSP_URL,
    CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    CONF_UNHEALTHY_CONFIDENCE_THRESHOLD,
    CONF_VISION_PROMPT,
    DEFAULT_CAPTURE_METHOD,
    DEFAULT_CHECK_INTERVAL_SEC,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_MAX_BACKOFF_SEC,
    DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC,
    DEFAULT_MOTION_DETECTION_ENABLED,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_ON_INCIDENT,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_SEC,
    DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    DEFAULT_UNHEALTHY_CONFIDENCE_THRESHOLD,
    DEFAULT_VISION_PROMPT,
    DOMAIN,
    EVENT_INCIDENT,
    INVALID_JSON_RETRY_COUNT,
    LLM_PROVIDER_OLLAMA,
    LLM_PROVIDER_OPENAI,
    MAX_HTTP_RETRIES,
    STATUS_UNHEALTHY,
    STATUS_UNKNOWN,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    USER_PROMPT,
)
from .logic import (
    InferenceResult,
    apply_incident_logic,
    is_confident_unhealthy,
    parse_model_output,
    should_send_notification,
    unknown_result,
)

_LOGGER = logging.getLogger(__name__)


def _encode_frame(frame: bytes | None) -> str | None:
    """Encode JPEG bytes for storage."""
    if frame is None:
        return None
    return base64.b64encode(frame).decode("ascii")


def _decode_frame(frame_text: Any) -> bytes | None:
    """Decode stored JPEG bytes."""
    if not isinstance(frame_text, str) or not frame_text:
        return None
    try:
        return base64.b64decode(frame_text.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return None


class RetryableLLMError(Exception):
    """Raised for retryable LLM transport failures."""


class UnreachableLLMError(Exception):
    """Raised when the LLM endpoint cannot be reached."""


class Sentry3DCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates capture, inference, and incident lifecycle."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.config_entry = entry
        self._session = async_get_clientsession(hass)
        self._history: deque[dict[str, Any]] = deque(maxlen=DEFAULT_HISTORY_SIZE)
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry.entry_id}",
        )
        self._last_frame: bytes | None = None
        self._last_frame_time: datetime | None = None
        self._last_frame_hash: str | None = None
        self._last_llm_frame: bytes | None = None
        self._last_llm_frame_time: datetime | None = None
        self._last_llm_frame_hash: str | None = None
        self._last_overlay_frame: bytes | None = None
        self._same_frame_count = 0
        self._capture_reused_last_frame = False
        self._last_model_output: str | None = None
        self._last_model_output_hash: str | None = None
        self._incident_active = False
        self._incident_start_time: datetime | None = None
        self._consecutive_unhealthy_count = 0
        self._last_notification_time: datetime | None = None
        self._capture_backoff_until: datetime | None = None
        self._capture_backoff_sec = 0
        self._motion_detected = False
        self._motion_score: float | None = None
        self._previous_motion_signature: list[int] | None = None
        self._llm_reachable: bool | None = None

        self._read_entry_options()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=self.check_interval_sec),
        )

        self.data = self._default_state("Initializing")

    @property
    def last_frame(self) -> bytes | None:
        """Return last captured frame bytes."""
        return self._last_frame

    @property
    def last_llm_frame(self) -> bytes | None:
        """Return last frame bytes sent to the LLM."""
        return self._last_llm_frame

    @property
    def last_overlay_frame(self) -> bytes | None:
        """Return last rendered overlay frame."""
        return self._last_overlay_frame

    @property
    def history(self) -> list[dict[str, Any]]:
        """Return history list."""
        return list(self._history)

    @property
    def runtime_state(self) -> dict[str, Any]:
        """Return internal runtime diagnostics."""
        return {
            "incident_active": self._incident_active,
            "incident_start_time": self._incident_start_time.isoformat()
            if self._incident_start_time
            else None,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
            "unhealthy_confidence_threshold": self.unhealthy_confidence_threshold,
            "capture_backoff_until": self._capture_backoff_until.isoformat()
            if self._capture_backoff_until
            else None,
            "capture_backoff_sec": self._capture_backoff_sec,
            "motion_detected": self._motion_detected,
            "motion_detection_enabled": self.motion_detection_enabled,
            "motion_score": self._motion_score,
            "llm_reachable": self._llm_reachable,
            "llm_provider": self.llm_provider,
            "vision_prompt_hash": _text_digest(self.vision_prompt),
            "using_default_prompt": self.vision_prompt == DEFAULT_VISION_PROMPT,
            "vision_prompt_length": len(self.vision_prompt),
            "last_model_output_hash": self._last_model_output_hash,
            "last_model_output_excerpt": _text_excerpt(self._last_model_output),
            "last_frame_time": self._last_frame_time.isoformat()
            if self._last_frame_time
            else None,
            "last_frame_hash": self._last_frame_hash,
            "last_llm_frame_time": self._last_llm_frame_time.isoformat()
            if self._last_llm_frame_time
            else None,
            "last_llm_frame_hash": self._last_llm_frame_hash,
            "same_frame_count": self._same_frame_count,
            "capture_reused_last_frame": self._capture_reused_last_frame,
            "overlay_available": self._last_overlay_frame is not None,
        }

    def _read_entry_options(self) -> None:
        options = self.config_entry.options
        data = self.config_entry.data

        self.integration_name = str(
            options.get(CONF_NAME, data.get(CONF_NAME, DEFAULT_NAME))
        )
        self.rtsp_url = str(options.get(CONF_RTSP_URL, data[CONF_RTSP_URL]))
        self.ollama_base_url = str(
            options.get(CONF_OLLAMA_BASE_URL, data[CONF_OLLAMA_BASE_URL])
        ).rstrip("/")
        self.ollama_model = str(options.get(CONF_OLLAMA_MODEL, data[CONF_OLLAMA_MODEL]))
        self.llm_provider = str(
            options.get(
                CONF_LLM_PROVIDER,
                data.get(CONF_LLM_PROVIDER, DEFAULT_LLM_PROVIDER),
            )
        )
        self.openai_base_url = str(
            options.get(
                CONF_OPENAI_BASE_URL,
                data.get(CONF_OPENAI_BASE_URL, DEFAULT_OPENAI_BASE_URL),
            )
        ).rstrip("/")
        self.openai_model = str(
            options.get(
                CONF_OPENAI_MODEL,
                data.get(CONF_OPENAI_MODEL, DEFAULT_OPENAI_MODEL),
            )
        )
        self.openai_api_key = str(
            options.get(
                CONF_OPENAI_API_KEY,
                data.get(CONF_OPENAI_API_KEY, ""),
            )
        )
        self.vision_prompt = str(
            options.get(
                CONF_VISION_PROMPT,
                data.get(CONF_VISION_PROMPT, DEFAULT_VISION_PROMPT),
            )
        ).strip()
        if not self.vision_prompt:
            self.vision_prompt = DEFAULT_VISION_PROMPT

        self.check_interval_sec = int(
            options.get(
                CONF_CHECK_INTERVAL_SEC,
                data.get(CONF_CHECK_INTERVAL_SEC, DEFAULT_CHECK_INTERVAL_SEC),
            )
        )
        self.ollama_timeout_sec = int(
            options.get(
                CONF_OLLAMA_TIMEOUT_SEC,
                data.get(CONF_OLLAMA_TIMEOUT_SEC, DEFAULT_OLLAMA_TIMEOUT_SEC),
            )
        )
        self.history_size = int(
            options.get(
                CONF_HISTORY_SIZE,
                data.get(CONF_HISTORY_SIZE, DEFAULT_HISTORY_SIZE),
            )
        )
        self.unhealthy_consecutive_threshold = int(
            options.get(
                CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
                data.get(
                    CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
                    DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD,
                ),
            )
        )
        self.unhealthy_confidence_threshold = float(
            options.get(
                CONF_UNHEALTHY_CONFIDENCE_THRESHOLD,
                data.get(
                    CONF_UNHEALTHY_CONFIDENCE_THRESHOLD,
                    DEFAULT_UNHEALTHY_CONFIDENCE_THRESHOLD,
                ),
            )
        )
        self.max_backoff_sec = int(
            options.get(
                CONF_MAX_BACKOFF_SEC,
                data.get(CONF_MAX_BACKOFF_SEC, DEFAULT_MAX_BACKOFF_SEC),
            )
        )
        self.capture_method = str(
            options.get(
                CONF_CAPTURE_METHOD,
                data.get(CONF_CAPTURE_METHOD, DEFAULT_CAPTURE_METHOD),
            )
        )
        self.notify_on_incident = bool(
            options.get(
                CONF_NOTIFY_ON_INCIDENT,
                data.get(CONF_NOTIFY_ON_INCIDENT, DEFAULT_NOTIFY_ON_INCIDENT),
            )
        )
        self.min_notification_interval_sec = int(
            options.get(
                CONF_MIN_NOTIFICATION_INTERVAL_SEC,
                data.get(
                    CONF_MIN_NOTIFICATION_INTERVAL_SEC,
                    DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC,
                ),
            )
        )
        self.motion_detection_enabled = bool(
            options.get(
                CONF_MOTION_DETECTION_ENABLED,
                data.get(
                    CONF_MOTION_DETECTION_ENABLED,
                    DEFAULT_MOTION_DETECTION_ENABLED,
                ),
            )
        )
        self.motion_threshold = float(
            options.get(
                CONF_MOTION_THRESHOLD,
                data.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD),
            )
        )
        if self.llm_provider not in {LLM_PROVIDER_OLLAMA, LLM_PROVIDER_OPENAI}:
            self.llm_provider = LLM_PROVIDER_OLLAMA

    async def async_initialize(self) -> None:
        """Restore persisted state."""
        await self._async_restore_store()

    async def async_shutdown(self) -> None:
        """Persist state on unload."""
        await self._store.async_save(self._serialize_store())

    async def async_handle_config_update(self, entry: ConfigEntry) -> None:
        """Apply changed options dynamically."""
        self.config_entry = entry
        old_history = list(self._history)
        self._read_entry_options()
        self.update_interval = timedelta(seconds=self.check_interval_sec)
        self._history = deque(old_history[-self.history_size :], maxlen=self.history_size)
        self._store.async_delay_save(self._serialize_store, 5)
        self.hass.async_create_task(
            self.async_refresh(),
            name=f"{DOMAIN}_{self.config_entry.entry_id}_config_refresh",
        )

    async def async_force_update(self) -> None:
        """Force a refresh that bypasses motion gating once."""
        try:
            data = await self._async_run_update_cycle(force_inference=True)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            now = dt_util.utcnow()
            _LOGGER.exception(
                "Forced refresh failed for %s",
                self.integration_name,
            )
            data = self._build_safe_state(
                reason=f"Forced refresh failed: {err}",
                now=now,
            )
        self.async_set_updated_data(data)

    async def _async_restore_store(self) -> None:
        """Restore history and incident state from storage."""
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        history = stored.get("history", [])
        if isinstance(history, list):
            self._history = deque(history[-self.history_size :], maxlen=self.history_size)

        self._incident_active = bool(stored.get("incident_active", False))
        self._consecutive_unhealthy_count = int(
            stored.get("consecutive_unhealthy_count", 0)
        )

        incident_start_raw = stored.get("incident_start_time")
        if isinstance(incident_start_raw, str):
            self._incident_start_time = dt_util.parse_datetime(incident_start_raw)

        notification_time_raw = stored.get("last_notification_time")
        if isinstance(notification_time_raw, str):
            self._last_notification_time = dt_util.parse_datetime(notification_time_raw)

        self._last_frame = _decode_frame(stored.get("last_frame_b64"))
        self._last_llm_frame = _decode_frame(stored.get("last_llm_frame_b64"))
        self._last_overlay_frame = _decode_frame(stored.get("last_overlay_frame_b64"))

        if self._history:
            latest = self._history[-1]
            self._motion_detected = bool(latest.get("motion_detected", False))
            motion_score = latest.get("motion_score")
            self._motion_score = (
                float(motion_score) if isinstance(motion_score, (int, float)) else None
            )
            llm_reachable = latest.get("llm_reachable")
            self._llm_reachable = (
                bool(llm_reachable) if isinstance(llm_reachable, bool) else None
            )
            llm_frame_time_raw = latest.get("llm_frame_time")
            if isinstance(llm_frame_time_raw, str):
                self._last_llm_frame_time = dt_util.parse_datetime(llm_frame_time_raw)
            frame_time_raw = latest.get("frame_time")
            if isinstance(frame_time_raw, str):
                self._last_frame_time = dt_util.parse_datetime(frame_time_raw)
            self.data = self._default_state("Restored from history")
            self.data.update(
                {
                    "status": latest.get("status", STATUS_UNKNOWN),
                    "confidence": latest.get("confidence"),
                    "reason": latest.get("reason", ""),
                    "short_explanation": latest.get("short_explanation", ""),
                    "signals": latest.get("signals", {}),
                    "focus_region": latest.get("focus_region"),
                    "motion_detected": self._motion_detected,
                    "motion_score": self._motion_score,
                    "llm_reachable": self._llm_reachable,
                    "llm_provider": self.llm_provider,
                    "last_update": latest.get("timestamp"),
                    "last_frame_time": latest.get("frame_time"),
                    "last_frame_hash": latest.get("frame_hash"),
                    "last_llm_frame_time": latest.get("llm_frame_time"),
                    "last_llm_frame_hash": latest.get("llm_frame_hash"),
                    "same_frame_count": latest.get("same_frame_count", 0),
                    "capture_reused_last_frame": latest.get(
                        "capture_reused_last_frame", False
                    ),
                    "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
                    "unhealthy_confidence_threshold": self.unhealthy_confidence_threshold,
                    "unhealthy_gate_passed": latest.get(
                        "unhealthy_gate_passed", False
                    ),
                    "incident_active": self._incident_active,
                    "incident_start_time": self._incident_start_time.isoformat()
                    if self._incident_start_time
                    else None,
                    "last_notification_time": self._last_notification_time.isoformat()
                    if self._last_notification_time
                    else None,
                }
            )

    def _serialize_store(self) -> dict[str, Any]:
        """Serialize coordinator state for storage."""
        return {
            "history": list(self._history),
            "incident_active": self._incident_active,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
            "incident_start_time": self._incident_start_time.isoformat()
            if self._incident_start_time
            else None,
            "last_notification_time": self._last_notification_time.isoformat()
            if self._last_notification_time
            else None,
            "last_frame_b64": _encode_frame(self._last_frame),
            "last_llm_frame_b64": _encode_frame(self._last_llm_frame),
            "last_overlay_frame_b64": _encode_frame(self._last_overlay_frame),
        }

    def _default_state(self, reason: str) -> dict[str, Any]:
        """Build default state payload."""
        return {
            "status": STATUS_UNKNOWN,
            "confidence": None,
            "reason": reason,
            "short_explanation": "Unknown",
            "signals": {
                "bed_adhesion_ok": False,
                "spaghetti_detected": False,
                "layer_shift_detected": False,
                "detached_part_detected": False,
                "blob_detected": False,
                "supports_failed_detected": False,
                "print_missing_detected": False,
            },
            "focus_region": None,
            "motion_detected": False,
            "motion_detection_enabled": self.motion_detection_enabled,
            "motion_score": None,
            "llm_reachable": None,
            "llm_provider": self.llm_provider,
            "vision_prompt_hash": _text_digest(self.vision_prompt),
            "using_default_prompt": self.vision_prompt == DEFAULT_VISION_PROMPT,
            "last_model_output_hash": None,
            "last_model_output_excerpt": None,
            "last_update": None,
            "last_frame_time": None,
            "last_frame_hash": None,
            "last_llm_frame_time": None,
            "last_llm_frame_hash": None,
            "same_frame_count": 0,
            "capture_reused_last_frame": False,
            "overlay_available": False,
            "consecutive_unhealthy_count": 0,
            "unhealthy_confidence_threshold": self.unhealthy_confidence_threshold,
            "unhealthy_gate_passed": False,
            "incident_active": False,
            "incident_start_time": None,
            "last_notification_time": None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Run one full check cycle."""
        return await self._async_run_update_cycle(force_inference=False)

    async def _async_run_update_cycle(self, *, force_inference: bool) -> dict[str, Any]:
        """Run one full check cycle, optionally bypassing motion gating/backoff."""
        now = dt_util.utcnow()

        try:
            if (
                not force_inference
                and self._capture_backoff_until
                and now < self._capture_backoff_until
            ):
                remaining = (self._capture_backoff_until - now).total_seconds()
                result = unknown_result(
                    f"Capture backoff active ({remaining:.1f}s remaining)"
                )
                return await self._async_finalize_cycle(result, now)

            try:
                frame = await self._async_capture_frame()
                frame_hash = _frame_digest(frame)
                self._capture_reused_last_frame = False
                if self._last_frame_hash == frame_hash:
                    self._same_frame_count += 1
                    if self._same_frame_count >= 3:
                        _LOGGER.warning(
                            "Captured identical frame %s times in a row for %s",
                            self._same_frame_count,
                            self.integration_name,
                        )
                else:
                    self._same_frame_count = 0
                self._last_frame = frame
                self._last_frame_time = now
                self._last_frame_hash = frame_hash
                self._capture_backoff_sec = 0
                self._capture_backoff_until = None
            except asyncio.CancelledError:
                if self.hass.is_stopping:
                    raise
                _LOGGER.warning(
                    "RTSP frame capture refresh was cancelled for %s; keeping state as UNKNOWN",
                    self.integration_name,
                )
                return await self._async_finalize_cycle(
                    unknown_result("Frame capture cancelled"),
                    now,
                )
            except Exception as err:  # noqa: BLE001
                if force_inference and self._last_frame is not None:
                    _LOGGER.warning(
                        "Forced refresh capture failed for %s; reusing last frame: %s",
                        self.integration_name,
                        err,
                    )
                    frame = self._last_frame
                    self._capture_reused_last_frame = True
                else:
                    self._capture_backoff_sec = (
                        self.check_interval_sec
                        if self._capture_backoff_sec == 0
                        else min(self.max_backoff_sec, self._capture_backoff_sec * 2)
                    )
                    delay_sec = self._capture_backoff_sec + random.uniform(
                        0, max(0.1, self._capture_backoff_sec * 0.25)
                    )
                    self._capture_backoff_until = now + timedelta(seconds=delay_sec)
                    _LOGGER.warning(
                        "RTSP frame capture failed for %s: %s. Retrying in %.1fs",
                        self.rtsp_url,
                        err,
                        delay_sec,
                    )
                    result = unknown_result(f"Frame capture failed: {err}")
                    return await self._async_finalize_cycle(result, now)

            if self.motion_detection_enabled:
                (
                    self._motion_detected,
                    self._motion_score,
                    self._previous_motion_signature,
                ) = await self.hass.async_add_executor_job(
                    _detect_motion_and_signature,
                    self._previous_motion_signature,
                    frame,
                    self.motion_threshold,
                )
            else:
                self._motion_detected = False
                self._motion_score = None
                self._previous_motion_signature = None

            if (
                self.motion_detection_enabled
                and not force_inference
                and not self._motion_detected
            ):
                _LOGGER.debug(
                    "No motion detected for %s, skipping LLM inference",
                    self.integration_name,
                )
                result = unknown_result("No motion detected; inference skipped")
                result.short_explanation = "No motion detected"
                return await self._async_finalize_cycle(result, now)

            self._last_llm_frame = frame
            self._last_llm_frame_time = now
            self._last_llm_frame_hash = _frame_digest(frame)
            result = await self._async_infer_frame(frame)
            if force_inference and result.status == STATUS_UNKNOWN:
                result.reason = f"Forced refresh failed: {result.reason}"
                result.short_explanation = "Force refresh failed"
            return await self._async_finalize_cycle(result, now)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception(
                "Unexpected coordinator update failure for %s",
                self.integration_name,
            )
            return self._build_safe_state(
                reason=f"Coordinator update failed: {err}",
                now=now,
            )

    async def _async_capture_frame(self) -> bytes:
        """Capture a single JPEG from RTSP."""
        if self.capture_method == CAPTURE_METHOD_OPENCV:
            return await self.hass.async_add_executor_job(
                _capture_frame_opencv,
                self.rtsp_url,
            )

        timeout = max(5, self.ollama_timeout_sec)
        return await self.hass.async_add_executor_job(
            _capture_frame_ffmpeg,
            self.rtsp_url,
            timeout,
        )

    async def _async_infer_frame(self, frame: bytes) -> InferenceResult:
        """Run inference and strict parse with one invalid-JSON retry."""
        for parse_attempt in range(INVALID_JSON_RETRY_COUNT + 1):
            try:
                if self.llm_provider == LLM_PROVIDER_OPENAI:
                    model_text = await self._async_openai_chat(frame)
                else:
                    model_text = await self._async_ollama_chat(frame)
                self._last_model_output = model_text
                self._last_model_output_hash = _text_digest(model_text)
                return parse_model_output(model_text)
            except ValueError as err:
                if parse_attempt < INVALID_JSON_RETRY_COUNT:
                    _LOGGER.warning(
                        "Invalid model JSON on attempt %s for %s: %s",
                        parse_attempt + 1,
                        self.integration_name,
                        err,
                    )
                    continue
                _LOGGER.error("Model output parsing failed: %s", err)
                return unknown_result(f"Invalid model JSON response: {err}")
            except UnreachableLLMError as err:
                self._llm_reachable = False
                _LOGGER.error(
                    "LLM inference failed for %s: %s",
                    self.integration_name,
                    err,
                )
                return unknown_result(f"LLM inference failed: {err}")
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "LLM inference failed for %s: %s",
                    self.integration_name,
                    err,
                )
                return unknown_result(f"LLM inference failed: {err}")

        return unknown_result("Inference failed")

    async def _async_ollama_chat(self, frame: bytes) -> str:
        """Call remote Ollama with retry/backoff for retryable failures."""
        url = f"{self.ollama_base_url}/api/chat"
        frame_base64 = base64.b64encode(frame).decode("ascii")

        payload = {
            "model": self.ollama_model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": self.vision_prompt},
                {
                    "role": "user",
                    "content": USER_PROMPT,
                    "images": [frame_base64],
                },
            ],
            "options": {"temperature": 0},
        }

        timeout = aiohttp.ClientTimeout(total=self.ollama_timeout_sec)

        for attempt in range(MAX_HTTP_RETRIES):
            try:
                async with self._session.post(url, json=payload, timeout=timeout) as response:
                    self._llm_reachable = True
                    if response.status >= 500:
                        raise RetryableLLMError(f"HTTP {response.status}")
                    if response.status >= 400:
                        body_text = await response.text()
                        raise RuntimeError(
                            f"HTTP {response.status}: {body_text[:400]}"
                        )

                    body = await response.json(content_type=None)
                    if not isinstance(body, dict):
                        raise RuntimeError("Unexpected Ollama response body")

                    message = body.get("message")
                    if not isinstance(message, dict):
                        raise RuntimeError("Missing message object in Ollama response")

                    content = message.get("content")
                    if not isinstance(content, str):
                        raise RuntimeError("Missing message.content in Ollama response")

                    return content

            except (
                asyncio.TimeoutError,
                aiohttp.ClientError,
                RetryableLLMError,
            ) as err:
                if attempt >= MAX_HTTP_RETRIES - 1:
                    raise UnreachableLLMError(
                        "Max retries reached for Ollama request"
                    ) from err
                base_delay = min(self.max_backoff_sec, 2**attempt)
                delay = base_delay + random.uniform(0, max(0.1, base_delay * 0.3))
                _LOGGER.warning(
                    "Retryable Ollama call failure (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt + 1,
                    MAX_HTTP_RETRIES,
                    err,
                    delay,
                )
                await asyncio.sleep(delay)

        raise UnreachableLLMError("Unable to call Ollama")

    async def _async_openai_chat(self, frame: bytes) -> str:
        """Call OpenAI-compatible chat completions endpoint."""
        url = f"{self.openai_base_url}/v1/chat/completions"
        frame_base64 = base64.b64encode(frame).decode("ascii")

        headers: dict[str, str] = {}
        if self.openai_api_key:
            headers["Authorization"] = f"Bearer {self.openai_api_key}"

        payload = {
            "model": self.openai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.vision_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{frame_base64}",
                            },
                        },
                    ],
                },
            ],
        }

        timeout = aiohttp.ClientTimeout(total=self.ollama_timeout_sec)

        for attempt in range(MAX_HTTP_RETRIES):
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    self._llm_reachable = True
                    if response.status >= 500:
                        raise RetryableLLMError(f"HTTP {response.status}")
                    if response.status >= 400:
                        body_text = await response.text()
                        raise RuntimeError(
                            f"HTTP {response.status}: {body_text[:400]}"
                        )

                    body = await response.json(content_type=None)
                    if not isinstance(body, dict):
                        raise RuntimeError("Unexpected OpenAI response body")

                    choices = body.get("choices")
                    if not isinstance(choices, list) or not choices:
                        raise RuntimeError("Missing choices in OpenAI response")
                    first = choices[0]
                    if not isinstance(first, dict):
                        raise RuntimeError("Invalid choices[0] in OpenAI response")
                    message = first.get("message")
                    if not isinstance(message, dict):
                        raise RuntimeError("Missing message in OpenAI response")
                    content = message.get("content")
                    parsed_content = _extract_openai_content(content)
                    if not parsed_content:
                        raise RuntimeError("Missing message content in OpenAI response")
                    return parsed_content

            except (
                asyncio.TimeoutError,
                aiohttp.ClientError,
                RetryableLLMError,
            ) as err:
                if attempt >= MAX_HTTP_RETRIES - 1:
                    raise UnreachableLLMError(
                        "Max retries reached for OpenAI request"
                    ) from err
                base_delay = min(self.max_backoff_sec, 2**attempt)
                delay = base_delay + random.uniform(0, max(0.1, base_delay * 0.3))
                _LOGGER.warning(
                    "Retryable OpenAI call failure (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt + 1,
                    MAX_HTTP_RETRIES,
                    err,
                    delay,
                )
                await asyncio.sleep(delay)

        raise UnreachableLLMError("Unable to call OpenAI")

    async def _async_finalize_cycle(
        self,
        result: InferenceResult,
        now: datetime,
    ) -> dict[str, Any]:
        """Apply result to state, history, incidents, and notifications."""
        confident_unhealthy = is_confident_unhealthy(
            status=result.status,
            confidence=result.confidence,
            threshold=self.unhealthy_confidence_threshold,
        )
        incident_status = result.status
        if result.status == STATUS_UNHEALTHY and not confident_unhealthy:
            incident_status = STATUS_UNKNOWN

        transition = apply_incident_logic(
            current_status=incident_status,
            previous_consecutive_unhealthy=self._consecutive_unhealthy_count,
            incident_active=self._incident_active,
            unhealthy_consecutive_threshold=self.unhealthy_consecutive_threshold,
        )

        self._consecutive_unhealthy_count = transition.consecutive_unhealthy_count
        self._incident_active = transition.incident_active

        if transition.new_incident:
            self._incident_start_time = now
            self.hass.bus.async_fire(
                EVENT_INCIDENT,
                {
                    "entry_id": self.config_entry.entry_id,
                    "name": self.integration_name,
                    "status": result.status,
                    "confidence": result.confidence,
                    "reason": result.reason,
                    "short_explanation": result.short_explanation,
                    "timestamp": now.isoformat(),
                    "signals": result.signals,
                    "motion_detected": self._motion_detected,
                    "llm_reachable": self._llm_reachable,
                    "llm_provider": self.llm_provider,
                },
            )
            _LOGGER.warning(
                "Incident triggered for %s after %s consecutive unhealthy checks",
                self.integration_name,
                self._consecutive_unhealthy_count,
            )

        if transition.cleared_incident:
            self._incident_start_time = None
            _LOGGER.info("Incident cleared for %s", self.integration_name)

        should_notify = self.notify_on_incident and should_send_notification(
            incident_active=self._incident_active,
            new_incident=transition.new_incident,
            last_notification_time=self._last_notification_time,
            now=now,
            min_notification_interval_sec=self.min_notification_interval_sec,
        )

        if should_notify:
            await self._async_send_notification(result, now)
            self._last_notification_time = now
            _LOGGER.info(
                "Persistent notification emitted for %s",
                self.integration_name,
            )

        if self._last_llm_frame is not None and result.focus_region is not None:
            self._last_overlay_frame = await self.hass.async_add_executor_job(
                _render_concern_overlay,
                self._last_llm_frame,
                result.focus_region,
                result.confidence,
                result.short_explanation,
            )
        else:
            self._last_overlay_frame = None

        state = {
            "status": result.status,
            "confidence": result.confidence,
            "reason": result.reason,
            "short_explanation": result.short_explanation,
            "signals": result.signals,
            "focus_region": result.focus_region,
            "motion_detected": self._motion_detected,
            "motion_detection_enabled": self.motion_detection_enabled,
            "motion_score": self._motion_score,
            "llm_reachable": self._llm_reachable,
            "llm_provider": self.llm_provider,
            "vision_prompt_hash": _text_digest(self.vision_prompt),
            "using_default_prompt": self.vision_prompt == DEFAULT_VISION_PROMPT,
            "last_model_output_hash": self._last_model_output_hash,
            "last_model_output_excerpt": _text_excerpt(self._last_model_output),
            "last_update": now.isoformat(),
            "last_frame_time": self._last_frame_time.isoformat()
            if self._last_frame_time
            else None,
            "last_frame_hash": self._last_frame_hash,
            "last_llm_frame_time": self._last_llm_frame_time.isoformat()
            if self._last_llm_frame_time
            else None,
            "last_llm_frame_hash": self._last_llm_frame_hash,
            "same_frame_count": self._same_frame_count,
            "capture_reused_last_frame": self._capture_reused_last_frame,
            "overlay_available": self._last_overlay_frame is not None,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
            "unhealthy_confidence_threshold": self.unhealthy_confidence_threshold,
            "unhealthy_gate_passed": confident_unhealthy,
            "incident_active": self._incident_active,
            "incident_start_time": self._incident_start_time.isoformat()
            if self._incident_start_time
            else None,
            "last_notification_time": self._last_notification_time.isoformat()
            if self._last_notification_time
            else None,
        }

        history_record = {
            "timestamp": now.isoformat(),
            "status": result.status,
            "confidence": result.confidence,
            "reason": result.reason,
            "short_explanation": result.short_explanation,
            "signals": result.signals,
            "focus_region": result.focus_region,
            "motion_detected": self._motion_detected,
            "motion_detection_enabled": self.motion_detection_enabled,
            "motion_score": self._motion_score,
            "llm_reachable": self._llm_reachable,
            "llm_provider": self.llm_provider,
            "frame_time": state["last_frame_time"],
            "frame_hash": state["last_frame_hash"],
            "llm_frame_time": state["last_llm_frame_time"],
            "llm_frame_hash": state["last_llm_frame_hash"],
            "same_frame_count": state["same_frame_count"],
            "capture_reused_last_frame": state["capture_reused_last_frame"],
            "overlay_available": state["overlay_available"],
            "incident_active": self._incident_active,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
            "unhealthy_gate_passed": state["unhealthy_gate_passed"],
        }
        self._history.append(history_record)

        self.data = state
        self._store.async_delay_save(self._serialize_store, 5)
        return state

    async def _async_send_notification(
        self,
        result: InferenceResult,
        now: datetime,
    ) -> None:
        """Send Home Assistant persistent notification."""
        persistent_notification.async_create(
            self.hass,
            (
                f"Status: {result.status}\n"
                f"Confidence: {result.confidence if result.confidence is not None else 'n/a'}\n"
                f"Reason: {result.reason}\n"
                f"Short explanation: {result.short_explanation}\n"
                f"Time: {now.isoformat()}\n\n"
                "Open camera.sentry3d_last_frame (or your dashboard card) to inspect the print."
            ),
            title="Sentry3D Alert: Print Unhealthy",
            notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_incident",
        )

    def _build_safe_state(self, *, reason: str, now: datetime) -> dict[str, Any]:
        """Return a non-raising fallback state so entities stay available."""
        state = self._default_state(reason)
        state.update(
            {
                "motion_detected": self._motion_detected,
                "motion_detection_enabled": self.motion_detection_enabled,
                "motion_score": self._motion_score,
            "llm_reachable": self._llm_reachable,
            "llm_provider": self.llm_provider,
            "vision_prompt_hash": _text_digest(self.vision_prompt),
            "using_default_prompt": self.vision_prompt == DEFAULT_VISION_PROMPT,
            "last_model_output_hash": self._last_model_output_hash,
            "last_model_output_excerpt": _text_excerpt(self._last_model_output),
            "last_update": now.isoformat(),
                "last_frame_time": self._last_frame_time.isoformat()
                if self._last_frame_time
                else None,
                "last_frame_hash": self._last_frame_hash,
                "last_llm_frame_time": self._last_llm_frame_time.isoformat()
                if self._last_llm_frame_time
                else None,
                "last_llm_frame_hash": self._last_llm_frame_hash,
                "same_frame_count": self._same_frame_count,
                "capture_reused_last_frame": self._capture_reused_last_frame,
                "overlay_available": self._last_overlay_frame is not None,
                "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
                "unhealthy_confidence_threshold": self.unhealthy_confidence_threshold,
                "unhealthy_gate_passed": False,
                "incident_active": self._incident_active,
                "incident_start_time": self._incident_start_time.isoformat()
                if self._incident_start_time
                else None,
                "last_notification_time": self._last_notification_time.isoformat()
                if self._last_notification_time
                else None,
            }
        )
        self.data = state
        return state


def _extract_openai_content(content: Any) -> str:
    """Normalize OpenAI message content payload into plain text."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "output_text"}:
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
        return "\n".join(text_parts).strip()
    return ""


def _frame_digest(frame: bytes) -> str:
    """Return a short stable digest for a captured frame."""
    return hashlib.sha256(frame).hexdigest()[:12]


def _text_digest(text: str | None) -> str | None:
    """Return a short stable digest for text."""
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _text_excerpt(text: str | None, length: int = 280) -> str | None:
    """Return a compact excerpt for HA state attributes."""
    if text is None:
        return None
    normalized = " ".join(text.split())
    if len(normalized) <= length:
        return normalized
    return f"{normalized[: length - 3].rstrip()}..."


def _motion_cutoff_from_threshold(threshold: float) -> float:
    """Convert user sensitivity setting into a diff cutoff.

    Higher configured values should be more sensitive, so they must produce a
    lower required frame-difference cutoff.
    """
    safe_threshold = max(0.1, float(threshold))
    return 64.0 / safe_threshold


def _motion_signature(frame: bytes) -> list[int]:
    """Compute a compact grayscale signature for motion checks."""
    from PIL import Image  # pylint: disable=import-outside-toplevel

    with Image.open(BytesIO(frame)) as img:
        grayscale = img.convert("L").resize((32, 32))
        return list(grayscale.getdata())


def _render_concern_overlay(
    frame: bytes,
    focus_region: dict[str, float],
    confidence: float | None,
    short_explanation: str,
) -> bytes:
    """Render a concern rectangle and confidence label onto the frame."""
    from PIL import Image, ImageDraw, ImageFont  # pylint: disable=import-outside-toplevel

    with Image.open(BytesIO(frame)) as img:
        rendered = img.convert("RGB")
        draw = ImageDraw.Draw(rendered, "RGBA")
        font = ImageFont.load_default()

        image_width, image_height = rendered.size
        left = max(0, min(image_width - 1, round(focus_region["x"] * image_width)))
        top = max(0, min(image_height - 1, round(focus_region["y"] * image_height)))
        right = max(
            left + 1,
            min(image_width, round((focus_region["x"] + focus_region["width"]) * image_width)),
        )
        bottom = max(
            top + 1,
            min(
                image_height,
                round((focus_region["y"] + focus_region["height"]) * image_height),
            ),
        )

        outline_width = max(3, round(min(image_width, image_height) * 0.01))
        draw.rectangle(
            [(left, top), (right, bottom)],
            outline=(255, 64, 64, 255),
            fill=(255, 64, 64, 40),
            width=outline_width,
        )

        confidence_pct = "n/a" if confidence is None else f"{confidence * 100:.0f}%"
        label = f"Concern {confidence_pct}"
        if short_explanation:
            label = f"{label} - {short_explanation}"

        padding = 6
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        label_x = max(0, min(left, image_width - text_width - (padding * 2)))
        label_y = top - text_height - (padding * 2)
        if label_y < 0:
            label_y = min(image_height - text_height - (padding * 2), bottom + padding)

        draw.rounded_rectangle(
            [
                (label_x, label_y),
                (label_x + text_width + (padding * 2), label_y + text_height + (padding * 2)),
            ],
            radius=8,
            fill=(24, 24, 24, 220),
            outline=(255, 64, 64, 255),
            width=2,
        )
        draw.text(
            (label_x + padding, label_y + padding),
            label,
            fill=(255, 255, 255, 255),
            font=font,
        )

        output = BytesIO()
        rendered.save(output, format="JPEG", quality=92)
        return output.getvalue()


def _detect_motion_and_signature(
    previous_signature: list[int] | None,
    frame: bytes,
    threshold: float,
) -> tuple[bool, float | None, list[int] | None]:
    """Compute motion state from current frame and previous signature."""
    try:
        current_signature = _motion_signature(frame)
    except Exception:  # noqa: BLE001
        # If motion detection fails, default to inference enabled.
        return True, None, previous_signature

    if not previous_signature:
        return True, None, current_signature

    if len(previous_signature) != len(current_signature):
        return True, None, current_signature

    mean_abs_diff = sum(
        abs(curr - prev) for curr, prev in zip(current_signature, previous_signature)
    ) / len(current_signature)
    cutoff = _motion_cutoff_from_threshold(threshold)
    return mean_abs_diff >= cutoff, float(mean_abs_diff), current_signature


def _capture_frame_ffmpeg(rtsp_url: str, timeout: int) -> bytes:
    """Capture one frame using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-analyzeduration",
        "0",
        "-probesize",
        "32",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]

    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as err:
        raise RuntimeError("ffmpeg executable not found") from err
    except subprocess.TimeoutExpired as err:
        raise RuntimeError("ffmpeg capture timed out") from err

    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"ffmpeg exited with code {process.returncode}: {stderr}")

    if not process.stdout:
        raise RuntimeError("ffmpeg returned empty frame output")

    return process.stdout


def _capture_frame_opencv(rtsp_url: str) -> bytes:
    """Capture one frame with OpenCV."""
    try:
        import cv2  # pylint: disable=import-outside-toplevel
    except ImportError as err:
        raise RuntimeError("OpenCV capture selected but opencv-python is unavailable") from err

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("OpenCV failed to open RTSP stream")

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise RuntimeError("OpenCV failed to read frame")

    encoded, jpeg = cv2.imencode(".jpg", frame)
    if not encoded:
        raise RuntimeError("OpenCV JPEG encoding failed")

    return jpeg.tobytes()
