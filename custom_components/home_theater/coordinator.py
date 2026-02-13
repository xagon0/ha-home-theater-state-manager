"""Coordinator for Home Theater State Manager.

Central state brain: owns all theater state, dispatches IR/RF commands via
remote_ir_device_manager, persists state across restarts, and notifies
entity listeners on every change.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import (
    AMP_POWER_ON_DELAY,
    CONF_AMP_DEVICE_ID,
    CONF_AMP_MUTE,
    CONF_AMP_POWER_OFF,
    CONF_AMP_POWER_ON,
    CONF_AMP_VOLUME_DOWN,
    CONF_AMP_VOLUME_UP,
    CONF_HDMI_DEVICE_ID,
    CONF_LIGHT_ENTITIES,
    CONF_SCENES,
    CONF_SCREEN_DEVICE_ID,
    CONF_SCREEN_DOWN_CMD,
    CONF_SCREEN_STOP_CMD,
    CONF_SCREEN_TRAVEL_TIME,
    CONF_SCREEN_UP_CMD,
    CONF_SOURCES,
    CONF_VOLUME_MAX_STEPS,
    DEFAULT_SCREEN_TRAVEL_TIME,
    DEFAULT_VOLUME,
    DEFAULT_VOLUME_MAX_STEPS,
    SAVE_DELAY,
    SCENE_AMP_POWER,
    SCENE_LIGHTS,
    SCENE_SCREEN,
    SCENE_SOURCE,
    SCENE_VOLUME,
    SCREEN_CLOSING,
    SCREEN_DOWN,
    SCREEN_OPENING,
    SCREEN_UP,
    STORAGE_KEY,
    STORAGE_VERSION,
    VOLUME_MAX,
    VOLUME_MIN,
    VOLUME_STEP_DELAY,
)

_LOGGER = logging.getLogger(__name__)


class HomeTheaterCoordinator:
    """Central state manager for the home theater."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self._config = config
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

        # State
        self.amp_power: bool = False
        self.volume: float = DEFAULT_VOLUME
        self.muted: bool = False
        self.source: str | None = None
        self.screen_position: str = SCREEN_UP
        self.active_scene: str | None = None

        # Listeners
        self._listeners: list[Callable[[], None]] = []

        # Screen timer handle
        self._screen_timer: CALLBACK_TYPE | None = None

        # Scene activation guard - prevents sub-commands from clearing active_scene
        self._in_scene_activation: bool = False

    # ── Config accessors ─────────────────────────────────────────────

    @property
    def source_list(self) -> list[str]:
        return list(self._config.get(CONF_SOURCES, {}).keys())

    @property
    def scene_names(self) -> list[str]:
        return [s["name"] for s in self._config.get(CONF_SCENES, []) if "name" in s]

    @property
    def light_entities(self) -> list[str]:
        return self._config.get(CONF_LIGHT_ENTITIES, [])

    def update_config(self, config: dict[str, Any]) -> None:
        """Update config after options flow change."""
        self._config = config

    # ── Persistence ──────────────────────────────────────────────────

    async def async_load(self) -> None:
        """Load persisted state from storage."""
        data = await self._store.async_load()
        if data:
            self.amp_power = data.get("amp_power", False)
            self.volume = data.get("volume", DEFAULT_VOLUME)
            self.muted = data.get("muted", False)
            self.source = data.get("source")
            self.active_scene = data.get("active_scene")
            # Reset transitional screen states to safe default
            pos = data.get("screen_position", SCREEN_UP)
            if pos in (SCREEN_OPENING, SCREEN_CLOSING):
                pos = SCREEN_UP
            self.screen_position = pos

    def _schedule_save(self) -> None:
        """Debounced save (1s window) to batch rapid changes like volume presses."""
        self._store.async_delay_save(self._state_to_dict, SAVE_DELAY)

    def _state_to_dict(self) -> dict[str, Any]:
        return {
            "amp_power": self.amp_power,
            "volume": self.volume,
            "muted": self.muted,
            "source": self.source,
            "screen_position": self.screen_position,
            "active_scene": self.active_scene,
        }

    # ── Listener pattern ─────────────────────────────────────────────

    @callback
    def register_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a callback; returns an unregister function."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        """Notify all entity listeners and schedule a debounced save."""
        self._schedule_save()
        for listener in list(self._listeners):
            listener()

    # ── IR/RF dispatch ───────────────────────────────────────────────

    async def _send_command(self, device_id: str, command_name: str) -> None:
        """Send a command via remote_ir_device_manager."""
        await self.hass.services.async_call(
            "remote_ir_device_manager",
            "send_command",
            {"device_id": device_id, "command_name": command_name},
            blocking=True,
        )

    # ── Amplifier commands ───────────────────────────────────────────

    async def async_amp_power_on(self) -> None:
        if self.amp_power:
            return
        await self._send_command(
            self._config[CONF_AMP_DEVICE_ID],
            self._config[CONF_AMP_POWER_ON],
        )
        self.amp_power = True
        self._notify()

    async def async_amp_power_off(self) -> None:
        if not self.amp_power:
            return
        await self._send_command(
            self._config[CONF_AMP_DEVICE_ID],
            self._config[CONF_AMP_POWER_OFF],
        )
        self.amp_power = False
        self.active_scene = None
        self._notify()

    async def async_volume_up(self) -> None:
        await self._send_command(
            self._config[CONF_AMP_DEVICE_ID],
            self._config[CONF_AMP_VOLUME_UP],
        )
        max_steps = self._config.get(CONF_VOLUME_MAX_STEPS, DEFAULT_VOLUME_MAX_STEPS)
        step = 1.0 / max_steps
        self.volume = min(VOLUME_MAX, round(self.volume + step, 4))
        if not self._in_scene_activation:
            self.active_scene = None
        self._notify()

    async def async_volume_down(self) -> None:
        await self._send_command(
            self._config[CONF_AMP_DEVICE_ID],
            self._config[CONF_AMP_VOLUME_DOWN],
        )
        max_steps = self._config.get(CONF_VOLUME_MAX_STEPS, DEFAULT_VOLUME_MAX_STEPS)
        step = 1.0 / max_steps
        self.volume = max(VOLUME_MIN, round(self.volume - step, 4))
        if not self._in_scene_activation:
            self.active_scene = None
        self._notify()

    async def async_mute_toggle(self) -> None:
        await self._send_command(
            self._config[CONF_AMP_DEVICE_ID],
            self._config[CONF_AMP_MUTE],
        )
        self.muted = not self.muted
        self._notify()

    # ── Source selection ──────────────────────────────────────────────

    async def async_select_source(self, source: str) -> None:
        sources = self._config.get(CONF_SOURCES, {})
        cmd = sources.get(source)
        if cmd is None:
            _LOGGER.warning("Unknown source: %s", source)
            return
        await self._send_command(self._config[CONF_HDMI_DEVICE_ID], cmd)
        self.source = source
        if not self._in_scene_activation:
            self.active_scene = None
        self._notify()

    # ── Projector screen ─────────────────────────────────────────────

    async def async_screen_down(self) -> None:
        """Deploy the screen (close the cover)."""
        if self.screen_position == SCREEN_DOWN:
            return
        self._cancel_screen_timer()
        await self._send_command(
            self._config[CONF_SCREEN_DEVICE_ID],
            self._config[CONF_SCREEN_DOWN_CMD],
        )
        self.screen_position = SCREEN_CLOSING
        self._notify()
        travel = self._config.get(CONF_SCREEN_TRAVEL_TIME, DEFAULT_SCREEN_TRAVEL_TIME)
        self._screen_timer = async_call_later(
            self.hass, travel, self._screen_arrived_down
        )

    async def async_screen_up(self) -> None:
        """Retract the screen (open the cover)."""
        if self.screen_position == SCREEN_UP:
            return
        self._cancel_screen_timer()
        await self._send_command(
            self._config[CONF_SCREEN_DEVICE_ID],
            self._config[CONF_SCREEN_UP_CMD],
        )
        self.screen_position = SCREEN_OPENING
        self._notify()
        travel = self._config.get(CONF_SCREEN_TRAVEL_TIME, DEFAULT_SCREEN_TRAVEL_TIME)
        self._screen_timer = async_call_later(
            self.hass, travel, self._screen_arrived_up
        )

    @callback
    def _screen_arrived_down(self, _now: Any = None) -> None:
        self._screen_timer = None
        self.screen_position = SCREEN_DOWN
        self._notify()

    @callback
    def _screen_arrived_up(self, _now: Any = None) -> None:
        self._screen_timer = None
        self.screen_position = SCREEN_UP
        self._notify()

    @property
    def has_screen_stop(self) -> bool:
        """Return True if a screen stop command is configured."""
        return bool(self._config.get(CONF_SCREEN_STOP_CMD))

    async def async_screen_stop(self) -> None:
        """Stop the screen mid-travel."""
        stop_cmd = self._config.get(CONF_SCREEN_STOP_CMD)
        if not stop_cmd:
            return
        self._cancel_screen_timer()
        await self._send_command(
            self._config[CONF_SCREEN_DEVICE_ID], stop_cmd
        )
        # Leave position as the transitional state — we don't know where it stopped
        # but clear the timer so it won't auto-complete
        self._notify()

    def _cancel_screen_timer(self) -> None:
        if self._screen_timer is not None:
            self._screen_timer()
            self._screen_timer = None

    # ── Volume sync (manual correction) ──────────────────────────────

    @callback
    def sync_volume(self, volume_level: float) -> None:
        """Manually set tracked volume without sending IR (drift correction)."""
        self.volume = max(VOLUME_MIN, min(VOLUME_MAX, round(volume_level, 4)))
        self._notify()

    # ── Volume set level (step to absolute) ──────────────────────────

    async def async_volume_set_level(self, target: float) -> None:
        """Step volume to an absolute level via repeated IR commands."""
        target = max(VOLUME_MIN, min(VOLUME_MAX, round(target, 4)))
        max_steps = self._config.get(CONF_VOLUME_MAX_STEPS, DEFAULT_VOLUME_MAX_STEPS)
        step = 1.0 / max_steps
        diff = target - self.volume
        steps_needed = int(abs(diff) / step)

        for _ in range(steps_needed):
            if diff > 0:
                await self.async_volume_up()
            else:
                await self.async_volume_down()
            await asyncio.sleep(VOLUME_STEP_DELAY)

        # Snap to exact target to avoid floating-point drift
        if self.volume != target:
            self.volume = target
            self._notify()

    # ── Scene activation ─────────────────────────────────────────────

    @callback
    def async_cleanup(self) -> None:
        """Cancel pending timers. Called on integration unload."""
        self._cancel_screen_timer()

    async def async_activate_scene(self, scene_name: str) -> None:
        """Orchestrate all theater components for a named scene."""
        scenes = self._config.get(CONF_SCENES, [])
        scene = next((s for s in scenes if s.get("name") == scene_name), None)
        if scene is None:
            _LOGGER.warning("Unknown scene: %s", scene_name)
            return

        self._in_scene_activation = True
        try:
            await self._execute_scene(scene, scene_name)
        finally:
            self._in_scene_activation = False

    async def _execute_scene(
        self, scene: dict[str, Any], scene_name: str
    ) -> None:
        """Execute all steps of a scene."""
        # 1. Amp power
        if SCENE_AMP_POWER in scene:
            if scene[SCENE_AMP_POWER]:
                await self.async_amp_power_on()
                await asyncio.sleep(AMP_POWER_ON_DELAY)
            else:
                await self.async_amp_power_off()

        # 2. Source selection
        if SCENE_SOURCE in scene and scene[SCENE_SOURCE]:
            await self.async_select_source(scene[SCENE_SOURCE])

        # 3. Volume stepping to target
        if SCENE_VOLUME in scene and scene[SCENE_VOLUME] is not None:
            await self.async_volume_set_level(scene[SCENE_VOLUME])

        # 4. Screen position
        if SCENE_SCREEN in scene:
            if scene[SCENE_SCREEN] == SCREEN_DOWN:
                await self.async_screen_down()
            elif scene[SCENE_SCREEN] == SCREEN_UP:
                await self.async_screen_up()

        # 5. Lights and switches
        if SCENE_LIGHTS in scene:
            for light_cfg in scene[SCENE_LIGHTS]:
                entity_id = light_cfg.get("entity_id")
                if not entity_id:
                    continue
                domain = entity_id.split(".")[0]
                if domain not in ("light", "switch"):
                    continue
                state = light_cfg.get("state", "off")
                if state == "on":
                    service_data: dict[str, Any] = {"entity_id": entity_id}
                    if domain == "light" and "brightness" in light_cfg:
                        service_data["brightness"] = int(
                            light_cfg["brightness"] * 255 / 100
                        )
                    await self.hass.services.async_call(
                        domain, "turn_on", service_data, blocking=True
                    )
                else:
                    await self.hass.services.async_call(
                        domain,
                        "turn_off",
                        {"entity_id": entity_id},
                        blocking=True,
                    )

        # 6. Update active scene
        self.active_scene = scene_name
        self._notify()
