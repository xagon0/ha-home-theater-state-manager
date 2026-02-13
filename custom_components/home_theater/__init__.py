"""Home Theater State Manager integration.

Single source of truth for all theater state. ESP32 touchscreens connect via
HA's native WebSocket API; IR/RF commands route through remote_ir_device_manager.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import HomeTheaterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "cover", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Theater from a config entry."""
    coordinator = HomeTheaterCoordinator(hass, dict(entry.data))
    await coordinator.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass, entry)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HomeTheaterCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator:
            coordinator.async_cleanup()
        # Remove services if no entries remain
        if not hass.data[DOMAIN]:
            for service in ("activate_scene", "sync_volume", "volume_set_level"):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options flow update — push new config into coordinator."""
    coordinator: HomeTheaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_config(dict(entry.data))


def _get_coordinator(hass: HomeAssistant) -> HomeTheaterCoordinator:
    """Get the first available coordinator (single-instance integration)."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise ValueError("Home Theater integration not loaded")
    return next(iter(entries.values()))


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register custom services (idempotent — safe to call multiple times)."""

    if hass.services.has_service(DOMAIN, "activate_scene"):
        return

    async def handle_activate_scene(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        scene_name = call.data["scene_name"]
        await coordinator.async_activate_scene(scene_name)

    async def handle_sync_volume(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        coordinator.sync_volume(call.data["volume_level"])

    async def handle_volume_set_level(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.async_volume_set_level(call.data["volume_level"])

    hass.services.async_register(
        DOMAIN,
        "activate_scene",
        handle_activate_scene,
        schema=vol.Schema(
            {vol.Required("scene_name"): cv.string}
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "sync_volume",
        handle_sync_volume,
        schema=vol.Schema(
            {vol.Required("volume_level"): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=1.0)
            )}
        ),
    )

    hass.services.async_register(
        DOMAIN,
        "volume_set_level",
        handle_volume_set_level,
        schema=vol.Schema(
            {vol.Required("volume_level"): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=1.0)
            )}
        ),
    )
