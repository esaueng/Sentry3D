"""Binary sensor platform for Sentry3D."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_UNHEALTHY
from .coordinator import Sentry3DCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sentry3D binary sensors."""
    coordinator: Sentry3DCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Sentry3DUnhealthyBinarySensor(coordinator, entry),
            Sentry3DIncidentBinarySensor(coordinator, entry),
            Sentry3DMotionDetectedBinarySensor(coordinator, entry),
            Sentry3DLlmReachableBinarySensor(coordinator, entry),
        ]
    )


class Sentry3DBinaryBaseEntity(CoordinatorEntity[Sentry3DCoordinator], BinarySensorEntity):
    """Base binary sensor entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.integration_name,
            "manufacturer": "Sentry3D",
            "model": "RTSP + Ollama Vision Monitor",
        }


class Sentry3DUnhealthyBinarySensor(Sentry3DBinaryBaseEntity):
    """True when latest status is UNHEALTHY."""

    _attr_name = "Unhealthy"
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unhealthy"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("status") == STATUS_UNHEALTHY


class Sentry3DIncidentBinarySensor(Sentry3DBinaryBaseEntity):
    """True while incident is active."""

    _attr_name = "Incident Active"
    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_incident_active"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("incident_active", False))


class Sentry3DMotionDetectedBinarySensor(Sentry3DBinaryBaseEntity):
    """True when motion was detected in the latest frame comparison."""

    _attr_name = "Motion Detected"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_motion_detected"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("motion_detected", False))


class Sentry3DLlmReachableBinarySensor(Sentry3DBinaryBaseEntity):
    """True when the selected LLM endpoint was reachable on last inference attempt."""

    _attr_name = "LLM Reachable"
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_llm_reachable"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("llm_reachable", False))
