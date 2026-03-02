"""Button platform for PrinterSentry."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrinterSentryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PrinterSentry button entities."""
    coordinator: PrinterSentryCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PrinterSentryForceUpdateButton(coordinator, entry)])


class PrinterSentryForceUpdateButton(CoordinatorEntity[PrinterSentryCoordinator], ButtonEntity):
    """Button entity to force a refresh cycle."""

    _attr_has_entity_name = True
    _attr_name = "Force Update"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_force_update"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.integration_name,
            "manufacturer": "Sentry3D",
            "model": "RTSP + Ollama Vision Monitor",
        }

    async def async_press(self) -> None:
        """Force an immediate status refresh."""
        await self.coordinator.async_request_refresh()
