"""Media player entity for the Home Theater amplifier."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomeTheaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Theater media player from a config entry."""
    coordinator: HomeTheaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeTheaterAmplifier(coordinator, entry)])


class HomeTheaterAmplifier(MediaPlayerEntity):
    """Media player entity representing the home theater amplifier."""

    _attr_has_entity_name = True
    _attr_name = "Amplifier"
    _attr_assumed_state = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(
        self, coordinator: HomeTheaterCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_amplifier"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Home Theater",
            manufacturer="Custom",
            model="Home Theater State Manager",
        )

    async def async_added_to_hass(self) -> None:
        """Register as a coordinator listener."""
        self.async_on_remove(
            self._coordinator.register_listener(self._on_coordinator_update)
        )

    @callback
    def _on_coordinator_update(self) -> None:
        """Handle coordinator state change."""
        self.async_write_ha_state()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def state(self) -> MediaPlayerState:
        return (
            MediaPlayerState.ON
            if self._coordinator.amp_power
            else MediaPlayerState.OFF
        )

    @property
    def volume_level(self) -> float:
        return self._coordinator.volume

    @property
    def is_volume_muted(self) -> bool:
        return self._coordinator.muted

    @property
    def source(self) -> str | None:
        return self._coordinator.source

    @property
    def source_list(self) -> list[str]:
        return self._coordinator.source_list

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"active_scene": self._coordinator.active_scene}

    # ── Commands ──────────────────────────────────────────────────────

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._coordinator.async_amp_power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._coordinator.async_amp_power_off()

    async def async_volume_up(self) -> None:
        await self._coordinator.async_volume_up()

    async def async_volume_down(self) -> None:
        await self._coordinator.async_volume_down()

    async def async_mute_volume(self, mute: bool) -> None:
        # IR mute is a toggle, so we only send if the desired state differs
        if mute != self._coordinator.muted:
            await self._coordinator.async_mute_toggle()

    async def async_set_volume_level(self, volume: float) -> None:
        await self._coordinator.async_volume_set_level(volume)

    async def async_select_source(self, source: str) -> None:
        await self._coordinator.async_select_source(source)
