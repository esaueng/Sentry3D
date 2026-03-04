"""Sensor platform for Sentry3D."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Sentry3DCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sentry3D sensors."""
    coordinator: Sentry3DCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            Sentry3DStatusSensor(coordinator, entry),
            Sentry3DConfidenceSensor(coordinator, entry),
            Sentry3DShortExplanationSensor(coordinator, entry),
        ]
    )


class Sentry3DBaseEntity(CoordinatorEntity[Sentry3DCoordinator]):
    """Base entity for Sentry3D."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.integration_name,
            "manufacturer": "Sentry3D",
            "model": "RTSP + Ollama Vision Monitor",
            "configuration_url": coordinator.ollama_base_url,
        }


class Sentry3DStatusSensor(Sentry3DBaseEntity, SensorEntity):
    """Represents latest print health status."""

    _attr_name = "Status"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_icon = "mdi:printer-3d"

    @property
    def native_value(self) -> str:
        return str(self.coordinator.data.get("status", "UNKNOWN"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "confidence": data.get("confidence"),
            "reason": data.get("reason"),
            "short_explanation": data.get("short_explanation"),
            "last_update": data.get("last_update"),
            "signals": data.get("signals", {}),
            "motion_detected": data.get("motion_detected"),
            "motion_score": data.get("motion_score"),
            "llm_reachable": data.get("llm_reachable"),
            "llm_provider": data.get("llm_provider"),
            "consecutive_unhealthy_count": data.get("consecutive_unhealthy_count", 0),
            "incident_active": data.get("incident_active", False),
            "last_notification_time": data.get("last_notification_time"),
            "last_frame_time": data.get("last_frame_time"),
            "last_llm_frame_time": data.get("last_llm_frame_time"),
        }


class Sentry3DConfidenceSensor(Sentry3DBaseEntity, SensorEntity):
    """Represents latest confidence score."""

    _attr_name = "Confidence"
    _attr_icon = "mdi:chart-line"
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_confidence"

    @property
    def native_value(self) -> float | None:
        confidence = self.coordinator.data.get("confidence")
        if confidence is None:
            return None
        return round(float(confidence), 3)


class Sentry3DShortExplanationSensor(Sentry3DBaseEntity, SensorEntity):
    """Represents the short explanation returned by inference."""

    _attr_name = "Short Explanation"
    _attr_icon = "mdi:text-short"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_short_explanation"

    @property
    def native_value(self) -> str:
        return str(self.coordinator.data.get("short_explanation", ""))
