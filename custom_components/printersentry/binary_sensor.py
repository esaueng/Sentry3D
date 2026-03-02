"""Binary sensor platform for PrinterSentry."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_UNHEALTHY
from .coordinator import PrinterSentryCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PrinterSentry binary sensors."""
    coordinator: PrinterSentryCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PrinterSentryUnhealthyBinarySensor(coordinator, entry),
            PrinterSentryIncidentBinarySensor(coordinator, entry),
            PrinterSentryMotionDetectedBinarySensor(coordinator, entry),
            PrinterSentryLlmReachableBinarySensor(coordinator, entry),
        ]
    )


class PrinterSentryBinaryBaseEntity(CoordinatorEntity[PrinterSentryCoordinator], BinarySensorEntity):
    """Base binary sensor entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.integration_name,
            "manufacturer": "Sentry3D",
            "model": "RTSP + Ollama Vision Monitor",
        }


class PrinterSentryUnhealthyBinarySensor(PrinterSentryBinaryBaseEntity):
    """True when latest status is UNHEALTHY."""

    _attr_name = "Unhealthy"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unhealthy"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("status") == STATUS_UNHEALTHY


class PrinterSentryIncidentBinarySensor(PrinterSentryBinaryBaseEntity):
    """True while incident is active."""

    _attr_name = "Incident Active"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_incident_active"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("incident_active", False))


class PrinterSentryMotionDetectedBinarySensor(PrinterSentryBinaryBaseEntity):
    """True when motion was detected in the latest frame comparison."""

    _attr_name = "Motion Detected"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_motion_detected"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("motion_detected", False))


class PrinterSentryLlmReachableBinarySensor(PrinterSentryBinaryBaseEntity):
    """True when the selected LLM endpoint was reachable on last inference attempt."""

    _attr_name = "LLM Reachable"
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator: PrinterSentryCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_llm_reachable"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("llm_reachable", False))
