"""Switch entity for the Home Theater projector power."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
    """Set up the Home Theater projector switch from a config entry."""
    coordinator: HomeTheaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeTheaterProjector(coordinator, entry)])


class HomeTheaterProjector(SwitchEntity):
    """Switch entity representing the projector power."""

    _attr_has_entity_name = True
    _attr_name = "Projector"
    _attr_assumed_state = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self, coordinator: HomeTheaterCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_projector"
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

    @property
    def is_on(self) -> bool:
        """Return True if the projector is on."""
        return self._coordinator.projector_power

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""
        await self._coordinator.async_projector_power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""
        await self._coordinator.async_projector_power_off()
