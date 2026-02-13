"""Cover entity for the Home Theater projector screen."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SCREEN_CLOSING, SCREEN_DOWN, SCREEN_OPENING, SCREEN_UP
from .coordinator import HomeTheaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Theater projector screen from a config entry."""
    coordinator: HomeTheaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeTheaterProjectorScreen(coordinator, entry)])


class HomeTheaterProjectorScreen(CoverEntity):
    """Cover entity representing the projector screen.

    Semantics: "closed" = screen down (deployed for viewing),
               "open"   = screen up (retracted/stowed).
    """

    _attr_has_entity_name = True
    _attr_name = "Projector Screen"
    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self, coordinator: HomeTheaterCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_projector_screen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Home Theater",
            manufacturer="Custom",
            model="Home Theater State Manager",
        )
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        if coordinator.has_screen_stop:
            features |= CoverEntityFeature.STOP
        self._attr_supported_features = features

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
    def is_closed(self) -> bool:
        """Return True if the screen is down (deployed)."""
        return self._coordinator.screen_position == SCREEN_DOWN

    @property
    def is_opening(self) -> bool:
        """Return True if the screen is retracting."""
        return self._coordinator.screen_position == SCREEN_OPENING

    @property
    def is_closing(self) -> bool:
        """Return True if the screen is deploying."""
        return self._coordinator.screen_position == SCREEN_CLOSING

    # ── Commands ──────────────────────────────────────────────────────

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Retract the screen (open = screen up)."""
        await self._coordinator.async_screen_up()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Deploy the screen (close = screen down)."""
        await self._coordinator.async_screen_down()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the screen mid-travel."""
        await self._coordinator.async_screen_stop()
