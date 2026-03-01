"""Data coordinator for PrinterSentry."""

from __future__ import annotations

import asyncio
import base64
from collections import deque
from datetime import datetime, timedelta
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
    CONF_MAX_BACKOFF_SEC,
    CONF_MIN_NOTIFICATION_INTERVAL_SEC,
    CONF_NOTIFY_ON_INCIDENT,
    CONF_OLLAMA_BASE_URL,
    CONF_OLLAMA_MODEL,
    CONF_OLLAMA_TIMEOUT_SEC,
    CONF_RTSP_URL,
    CONF_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    DEFAULT_CAPTURE_METHOD,
    DEFAULT_CHECK_INTERVAL_SEC,
    DEFAULT_HISTORY_SIZE,
    DEFAULT_MAX_BACKOFF_SEC,
    DEFAULT_MIN_NOTIFICATION_INTERVAL_SEC,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_ON_INCIDENT,
    DEFAULT_OLLAMA_TIMEOUT_SEC,
    DEFAULT_UNHEALTHY_CONSECUTIVE_THRESHOLD,
    DOMAIN,
    EVENT_INCIDENT,
    INVALID_JSON_RETRY_COUNT,
    MAX_HTTP_RETRIES,
    STATUS_UNKNOWN,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from .logic import (
    InferenceResult,
    apply_incident_logic,
    parse_model_output,
    should_send_notification,
    unknown_result,
)

_LOGGER = logging.getLogger(__name__)


class RetryableOllamaError(Exception):
    """Raised for retryable Ollama failures."""


class PrinterSentryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self._incident_active = False
        self._incident_start_time: datetime | None = None
        self._consecutive_unhealthy_count = 0
        self._last_notification_time: datetime | None = None
        self._capture_backoff_until: datetime | None = None
        self._capture_backoff_sec = 0

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
            "capture_backoff_until": self._capture_backoff_until.isoformat()
            if self._capture_backoff_until
            else None,
            "capture_backoff_sec": self._capture_backoff_sec,
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
        await self.async_request_refresh()

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

        if self._history:
            latest = self._history[-1]
            self.data = self._default_state("Restored from history")
            self.data.update(
                {
                    "status": latest.get("status", STATUS_UNKNOWN),
                    "confidence": latest.get("confidence"),
                    "reason": latest.get("reason", ""),
                    "signals": latest.get("signals", {}),
                    "last_update": latest.get("timestamp"),
                    "last_frame_time": latest.get("frame_time"),
                    "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
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
        }

    def _default_state(self, reason: str) -> dict[str, Any]:
        """Build default state payload."""
        return {
            "status": STATUS_UNKNOWN,
            "confidence": None,
            "reason": reason,
            "signals": {
                "bed_adhesion_ok": False,
                "spaghetti_detected": False,
                "layer_shift_detected": False,
                "detached_part_detected": False,
                "blob_detected": False,
                "supports_failed_detected": False,
                "print_missing_detected": False,
            },
            "last_update": None,
            "last_frame_time": None,
            "consecutive_unhealthy_count": 0,
            "incident_active": False,
            "incident_start_time": None,
            "last_notification_time": None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Run one full check cycle."""
        now = dt_util.utcnow()

        if self._capture_backoff_until and now < self._capture_backoff_until:
            remaining = (self._capture_backoff_until - now).total_seconds()
            result = unknown_result(
                f"Capture backoff active ({remaining:.1f}s remaining)"
            )
            return await self._async_finalize_cycle(result, now)

        try:
            frame = await self._async_capture_frame()
            self._last_frame = frame
            self._last_frame_time = now
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

        result = await self._async_infer_frame(frame)
        return await self._async_finalize_cycle(result, now)

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
                model_text = await self._async_ollama_chat(frame)
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
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Ollama inference failed for %s: %s",
                    self.integration_name,
                    err,
                )
                return unknown_result(f"Ollama inference failed: {err}")

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
                {"role": "system", "content": SYSTEM_PROMPT},
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
                    if response.status >= 500:
                        raise RetryableOllamaError(f"HTTP {response.status}")
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
                RetryableOllamaError,
            ) as err:
                if attempt >= MAX_HTTP_RETRIES - 1:
                    raise RuntimeError("Max retries reached for Ollama request") from err
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

        raise RuntimeError("Unable to call Ollama")

    async def _async_finalize_cycle(
        self,
        result: InferenceResult,
        now: datetime,
    ) -> dict[str, Any]:
        """Apply result to state, history, incidents, and notifications."""
        transition = apply_incident_logic(
            current_status=result.status,
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
                    "timestamp": now.isoformat(),
                    "signals": result.signals,
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

        state = {
            "status": result.status,
            "confidence": result.confidence,
            "reason": result.reason,
            "signals": result.signals,
            "last_update": now.isoformat(),
            "last_frame_time": self._last_frame_time.isoformat()
            if self._last_frame_time
            else None,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
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
            "signals": result.signals,
            "frame_time": state["last_frame_time"],
            "incident_active": self._incident_active,
            "consecutive_unhealthy_count": self._consecutive_unhealthy_count,
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
                f"Time: {now.isoformat()}\n\n"
                "Open camera.printersentry_last_frame (or your dashboard card) to inspect the print."
            ),
            title="PrinterSentry Alert: Print Unhealthy",
            notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_incident",
        )


def _capture_frame_ffmpeg(rtsp_url: str, timeout: int) -> bytes:
    """Capture one frame using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
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
