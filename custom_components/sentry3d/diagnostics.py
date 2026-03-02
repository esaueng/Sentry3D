"""Diagnostics support for Sentry3D."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_OLLAMA_BASE_URL,
    CONF_OPENAI_API_KEY,
    CONF_OPENAI_BASE_URL,
    CONF_RTSP_URL,
    DOMAIN,
)
from .coordinator import Sentry3DCoordinator

REDACT_KEYS = {CONF_USERNAME, CONF_OPENAI_API_KEY}


def _redact_url_credentials(value: str) -> str:
    """Redact username/password in URL while preserving host/path."""
    parts = urlsplit(value)
    if not parts.netloc or "@" not in parts.netloc:
        return value

    host_part = parts.netloc.split("@", 1)[1]
    redacted_netloc = f"***:***@{host_part}"
    return urlunsplit((parts.scheme, redacted_netloc, parts.path, parts.query, parts.fragment))


def _sanitize_config_dict(data: dict[str, Any]) -> dict[str, Any]:
    sanitized = deepcopy(data)
    for key in (CONF_RTSP_URL, CONF_OLLAMA_BASE_URL, CONF_OPENAI_BASE_URL):
        value = sanitized.get(key)
        if isinstance(value, str):
            sanitized[key] = _redact_url_credentials(value)
    return sanitized


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: Sentry3DCoordinator = hass.data[DOMAIN][entry.entry_id]

    data = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": _sanitize_config_dict(dict(entry.data)),
            "options": _sanitize_config_dict(dict(entry.options)),
        },
        "runtime": coordinator.runtime_state,
        "state": coordinator.data,
        "history": coordinator.history,
    }

    return async_redact_data(data, REDACT_KEYS)
