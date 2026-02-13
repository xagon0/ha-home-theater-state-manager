"""Config flow for Home Theater State Manager."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
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
    DEFAULT_VOLUME_MAX_STEPS,
    DOMAIN,
    MAX_SOURCES,
)

TEXT = TextSelector(TextSelectorConfig(type="text"))

IR_DOMAIN = "remote_ir_device_manager"


# ── Helpers to query remote_ir_device_manager ─────────────────────────


def _get_ir_devices(hass: HomeAssistant) -> dict[str, str]:
    """Return {device_id: device_name} for all remote_ir_device_manager devices."""
    devices: dict[str, str] = {}
    for entry_data in hass.data.get(IR_DOMAIN, {}).values():
        coordinator = entry_data.get("coordinator")
        if coordinator:
            for device in coordinator.devices.values():
                devices[device.id] = device.name
    return devices


def _get_device_commands(hass: HomeAssistant, device_id: str) -> list[str]:
    """Return command names for a specific device."""
    for entry_data in hass.data.get(IR_DOMAIN, {}).values():
        coordinator = entry_data.get("coordinator")
        if coordinator:
            device = coordinator.get_device(device_id)
            if device:
                return list(device.commands.keys())
    return []


def _device_selector(hass: HomeAssistant, default: str = "") -> SelectSelector:
    """Build a dropdown selector of all IR/RF devices."""
    devices = _get_ir_devices(hass)
    options = [
        SelectOptionDict(value=did, label=name) for did, name in devices.items()
    ]
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


def _command_selector(
    hass: HomeAssistant, device_id: str
) -> SelectSelector:
    """Build a dropdown selector of commands for a specific device."""
    commands = _get_device_commands(hass, device_id)
    options = [SelectOptionDict(value=cmd, label=cmd) for cmd in commands]
    return SelectSelector(
        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    )


# ── Schema builders ──────────────────────────────────────────────────


def _device_pick_schema(
    hass: HomeAssistant, key: str, default: str = ""
) -> vol.Schema:
    """Schema with a single device picker dropdown."""
    return vol.Schema(
        {vol.Required(key, default=default): _device_selector(hass, default)}
    )


def _amp_commands_schema(
    hass: HomeAssistant, device_id: str, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    d = defaults or {}
    cmd_sel = _command_selector(hass, device_id)
    return vol.Schema(
        {
            vol.Required(
                CONF_AMP_POWER_ON, default=d.get(CONF_AMP_POWER_ON, "")
            ): cmd_sel,
            vol.Required(
                CONF_AMP_POWER_OFF, default=d.get(CONF_AMP_POWER_OFF, "")
            ): cmd_sel,
            vol.Required(
                CONF_AMP_VOLUME_UP, default=d.get(CONF_AMP_VOLUME_UP, "")
            ): cmd_sel,
            vol.Required(
                CONF_AMP_VOLUME_DOWN, default=d.get(CONF_AMP_VOLUME_DOWN, "")
            ): cmd_sel,
            vol.Required(
                CONF_AMP_MUTE, default=d.get(CONF_AMP_MUTE, "")
            ): cmd_sel,
            vol.Required(
                CONF_VOLUME_MAX_STEPS,
                default=d.get(CONF_VOLUME_MAX_STEPS, DEFAULT_VOLUME_MAX_STEPS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10, max=200, step=1, mode=NumberSelectorMode.SLIDER
                )
            ),
        }
    )


def _hdmi_sources_schema(
    hass: HomeAssistant, device_id: str, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    d = defaults or {}
    existing_sources = d.get(CONF_SOURCES, {})
    cmd_sel = _command_selector(hass, device_id)
    fields: dict[vol.Marker, Any] = {}
    existing_names = list(existing_sources.keys())
    existing_cmds = list(existing_sources.values())
    for i in range(1, MAX_SOURCES + 1):
        name_default = existing_names[i - 1] if i - 1 < len(existing_names) else ""
        cmd_default = existing_cmds[i - 1] if i - 1 < len(existing_cmds) else ""
        fields[vol.Optional(f"source_{i}_name", default=name_default)] = TEXT
        fields[vol.Optional(f"source_{i}_cmd", default=cmd_default)] = cmd_sel
    return vol.Schema(fields)


def _screen_commands_schema(
    hass: HomeAssistant, device_id: str, defaults: dict[str, Any] | None = None
) -> vol.Schema:
    d = defaults or {}
    cmd_sel = _command_selector(hass, device_id)
    return vol.Schema(
        {
            vol.Required(
                CONF_SCREEN_DOWN_CMD, default=d.get(CONF_SCREEN_DOWN_CMD, "")
            ): cmd_sel,
            vol.Required(
                CONF_SCREEN_UP_CMD, default=d.get(CONF_SCREEN_UP_CMD, "")
            ): cmd_sel,
            vol.Optional(
                CONF_SCREEN_STOP_CMD, default=d.get(CONF_SCREEN_STOP_CMD, "")
            ): cmd_sel,
            vol.Required(
                CONF_SCREEN_TRAVEL_TIME,
                default=d.get(CONF_SCREEN_TRAVEL_TIME, DEFAULT_SCREEN_TRAVEL_TIME),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5, max=60, step=1, mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="s",
                )
            ),
        }
    )


def _lights_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_LIGHT_ENTITIES,
                default=d.get(CONF_LIGHT_ENTITIES, []),
            ): EntitySelector(
                EntitySelectorConfig(domain=["light", "switch"], multiple=True)
            ),
        }
    )


def _scenes_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    default_scenes = d.get(CONF_SCENES, "[]")
    if isinstance(default_scenes, list):
        default_scenes = json.dumps(default_scenes, indent=2)
    return vol.Schema(
        {
            vol.Optional(
                CONF_SCENES,
                default=default_scenes,
            ): TextSelector(
                TextSelectorConfig(type="text", multiline=True)
            ),
        }
    )


def _parse_sources(user_input: dict[str, Any]) -> dict[str, str]:
    """Extract source name->command pairs from flat form fields."""
    sources: dict[str, str] = {}
    for i in range(1, MAX_SOURCES + 1):
        name = user_input.get(f"source_{i}_name", "").strip()
        cmd = user_input.get(f"source_{i}_cmd", "").strip()
        if name and cmd:
            sources[name] = cmd
    return sources


# ── Config flow ──────────────────────────────────────────────────────


class HomeTheaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Theater."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # Step 1: Pick amplifier device
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._data[CONF_AMP_DEVICE_ID] = user_input[CONF_AMP_DEVICE_ID]
            return await self.async_step_amp_commands()

        return self.async_show_form(
            step_id="user",
            data_schema=_device_pick_schema(self.hass, CONF_AMP_DEVICE_ID),
        )

    # Step 2: Pick amplifier commands + volume step
    async def async_step_amp_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_hdmi_device()

        return self.async_show_form(
            step_id="amp_commands",
            data_schema=_amp_commands_schema(
                self.hass, self._data[CONF_AMP_DEVICE_ID]
            ),
        )

    # Step 3: Pick HDMI switch device
    async def async_step_hdmi_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_HDMI_DEVICE_ID] = user_input[CONF_HDMI_DEVICE_ID]
            return await self.async_step_hdmi_sources()

        return self.async_show_form(
            step_id="hdmi_device",
            data_schema=_device_pick_schema(self.hass, CONF_HDMI_DEVICE_ID),
        )

    # Step 4: Map HDMI sources to commands
    async def async_step_hdmi_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_SOURCES] = _parse_sources(user_input)
            return await self.async_step_screen_device()

        return self.async_show_form(
            step_id="hdmi_sources",
            data_schema=_hdmi_sources_schema(
                self.hass, self._data[CONF_HDMI_DEVICE_ID]
            ),
        )

    # Step 5: Pick screen device
    async def async_step_screen_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_SCREEN_DEVICE_ID] = user_input[CONF_SCREEN_DEVICE_ID]
            return await self.async_step_screen_commands()

        return self.async_show_form(
            step_id="screen_device",
            data_schema=_device_pick_schema(self.hass, CONF_SCREEN_DEVICE_ID),
        )

    # Step 6: Pick screen commands + travel time
    async def async_step_screen_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_lights()

        return self.async_show_form(
            step_id="screen_commands",
            data_schema=_screen_commands_schema(
                self.hass, self._data[CONF_SCREEN_DEVICE_ID]
            ),
        )

    # Step 7: Light entity selection
    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_LIGHT_ENTITIES] = user_input.get(
                CONF_LIGHT_ENTITIES, []
            )
            return await self.async_step_scenes()

        return self.async_show_form(
            step_id="lights",
            data_schema=_lights_schema(),
        )

    # Step 8: Scene definitions
    async def async_step_scenes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = user_input.get(CONF_SCENES, "[]")
            try:
                scenes = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(scenes, list):
                    raise ValueError("Not a list")
            except (json.JSONDecodeError, TypeError, ValueError):
                errors[CONF_SCENES] = "invalid_json"
            else:
                self._data[CONF_SCENES] = scenes
                return self.async_create_entry(
                    title="Home Theater",
                    data=self._data,
                )

        return self.async_show_form(
            step_id="scenes",
            data_schema=_scenes_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeTheaterOptionsFlow(config_entry)


# ── Options flow ─────────────────────────────────────────────────────


class HomeTheaterOptionsFlow(OptionsFlow):
    """Handle options flow for reconfiguration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        self._data: dict[str, Any] = dict(config_entry.data)

    # Step 1: Amp device
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_AMP_DEVICE_ID] = user_input[CONF_AMP_DEVICE_ID]
            return await self.async_step_amp_commands()

        return self.async_show_form(
            step_id="init",
            data_schema=_device_pick_schema(
                self.hass, CONF_AMP_DEVICE_ID,
                default=self._data.get(CONF_AMP_DEVICE_ID, ""),
            ),
        )

    # Step 2: Amp commands
    async def async_step_amp_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_hdmi_device()

        return self.async_show_form(
            step_id="amp_commands",
            data_schema=_amp_commands_schema(
                self.hass, self._data[CONF_AMP_DEVICE_ID], self._data
            ),
        )

    # Step 3: HDMI device
    async def async_step_hdmi_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_HDMI_DEVICE_ID] = user_input[CONF_HDMI_DEVICE_ID]
            return await self.async_step_hdmi_sources()

        return self.async_show_form(
            step_id="hdmi_device",
            data_schema=_device_pick_schema(
                self.hass, CONF_HDMI_DEVICE_ID,
                default=self._data.get(CONF_HDMI_DEVICE_ID, ""),
            ),
        )

    # Step 4: HDMI sources
    async def async_step_hdmi_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_SOURCES] = _parse_sources(user_input)
            return await self.async_step_screen_device()

        return self.async_show_form(
            step_id="hdmi_sources",
            data_schema=_hdmi_sources_schema(
                self.hass, self._data[CONF_HDMI_DEVICE_ID], self._data
            ),
        )

    # Step 5: Screen device
    async def async_step_screen_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_SCREEN_DEVICE_ID] = user_input[CONF_SCREEN_DEVICE_ID]
            return await self.async_step_screen_commands()

        return self.async_show_form(
            step_id="screen_device",
            data_schema=_device_pick_schema(
                self.hass, CONF_SCREEN_DEVICE_ID,
                default=self._data.get(CONF_SCREEN_DEVICE_ID, ""),
            ),
        )

    # Step 6: Screen commands
    async def async_step_screen_commands(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_lights()

        return self.async_show_form(
            step_id="screen_commands",
            data_schema=_screen_commands_schema(
                self.hass, self._data[CONF_SCREEN_DEVICE_ID], self._data
            ),
        )

    # Step 7: Lights
    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_LIGHT_ENTITIES] = user_input.get(
                CONF_LIGHT_ENTITIES, []
            )
            return await self.async_step_scenes()

        return self.async_show_form(
            step_id="lights",
            data_schema=_lights_schema(self._data),
        )

    # Step 8: Scenes
    async def async_step_scenes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = user_input.get(CONF_SCENES, "[]")
            try:
                scenes = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(scenes, list):
                    raise ValueError("Not a list")
            except (json.JSONDecodeError, TypeError, ValueError):
                errors[CONF_SCENES] = "invalid_json"
            else:
                self._data[CONF_SCENES] = scenes
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=self._data
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="scenes",
            data_schema=_scenes_schema(self._data),
            errors=errors,
        )
