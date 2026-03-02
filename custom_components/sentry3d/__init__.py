"""Sentry3D integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_CONTROL_STUB,
    PLATFORMS,
    SERVICE_CANCEL_PRINT,
    SERVICE_PAUSE_PRINT,
)
from .coordinator import Sentry3DCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sentry3D integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sentry3D from a config entry."""
    coordinator = Sentry3DCoordinator(hass, entry)
    await coordinator.async_initialize()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(
        coordinator.async_refresh(),
        name=f"{DOMAIN}_{entry.entry_id}_initial_refresh",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: Sentry3DCoordinator | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )

    if coordinator is not None:
        await coordinator.async_shutdown()

    if not hass.data.get(DOMAIN):
        if hass.services.has_service(DOMAIN, SERVICE_PAUSE_PRINT):
            hass.services.async_remove(DOMAIN, SERVICE_PAUSE_PRINT)
        if hass.services.has_service(DOMAIN, SERVICE_CANCEL_PRINT):
            hass.services.async_remove(DOMAIN, SERVICE_CANCEL_PRINT)

    return unload_ok


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry options updates."""
    coordinator: Sentry3DCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_handle_config_update(entry)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_PAUSE_PRINT):
        return

    async def _async_service_stub(call: ServiceCall, action: str) -> None:
        _LOGGER.warning(
            "Service '%s.%s' is a stub and does not control the printer.",
            DOMAIN,
            action,
        )
        hass.bus.async_fire(
            EVENT_CONTROL_STUB,
            {
                "action": action,
                "service_data": dict(call.data),
                "timestamp": dt_util.utcnow().isoformat(),
            },
        )

    async def _async_pause_print(call: ServiceCall) -> None:
        await _async_service_stub(call, SERVICE_PAUSE_PRINT)

    async def _async_cancel_print(call: ServiceCall) -> None:
        await _async_service_stub(call, SERVICE_CANCEL_PRINT)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_PRINT,
        _async_pause_print,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_PRINT,
        _async_cancel_print,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
    )
