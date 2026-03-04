"""Camera platform for Sentry3D."""

from __future__ import annotations

from homeassistant.components.camera import Camera
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
    """Set up Sentry3D camera entity."""
    coordinator: Sentry3DCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Sentry3DLastFrameCamera(coordinator, entry)])


class Sentry3DLastFrameCamera(CoordinatorEntity[Sentry3DCoordinator], Camera):
    """Camera entity exposing the latest frame sent to the LLM."""

    _attr_has_entity_name = True
    _attr_name = "Last LLM Frame"
    _attr_icon = "mdi:cctv"
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: Sentry3DCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_last_frame"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.integration_name,
            "manufacturer": "Sentry3D",
            "model": "RTSP + Ollama Vision Monitor",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_llm_frame is not None
            or self.coordinator.last_frame is not None
        )

    @property
    def is_streaming(self) -> bool:
        return False

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the latest JPEG frame bytes sent to the LLM."""
        return self.coordinator.last_llm_frame or self.coordinator.last_frame

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        frame_source = None
        if self.coordinator.last_llm_frame is not None:
            frame_source = "llm"
        elif self.coordinator.last_frame is not None:
            frame_source = "capture_fallback"

        return {
            "frame_source": frame_source,
            "last_frame_time": self.coordinator.data.get("last_frame_time"),
            "last_llm_frame_time": self.coordinator.data.get("last_llm_frame_time"),
            "last_update": self.coordinator.data.get("last_update"),
        }
