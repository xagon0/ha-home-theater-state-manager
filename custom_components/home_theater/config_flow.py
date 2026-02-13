"""Config flow for Home Theater State Manager."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
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
    CONF_SCREEN_TRAVEL_TIME,
    CONF_SCREEN_UP_CMD,
    CONF_SOURCES,
    CONF_VOLUME_STEP,
    DEFAULT_SCREEN_TRAVEL_TIME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    MAX_SOURCES,
)

TEXT = TextSelector(TextSelectorConfig(type="text"))


def _amp_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_AMP_DEVICE_ID, default=d.get(CONF_AMP_DEVICE_ID, "")
            ): TEXT,
            vol.Required(
                CONF_AMP_POWER_ON, default=d.get(CONF_AMP_POWER_ON, "power_on")
            ): TEXT,
            vol.Required(
                CONF_AMP_POWER_OFF, default=d.get(CONF_AMP_POWER_OFF, "power_off")
            ): TEXT,
            vol.Required(
                CONF_AMP_VOLUME_UP, default=d.get(CONF_AMP_VOLUME_UP, "volume_up")
            ): TEXT,
            vol.Required(
                CONF_AMP_VOLUME_DOWN,
                default=d.get(CONF_AMP_VOLUME_DOWN, "volume_down"),
            ): TEXT,
            vol.Required(
                CONF_AMP_MUTE, default=d.get(CONF_AMP_MUTE, "mute")
            ): TEXT,
            vol.Required(
                CONF_VOLUME_STEP,
                default=d.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.01, max=0.10, step=0.01, mode=NumberSelectorMode.SLIDER
                )
            ),
        }
    )


def _hdmi_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    existing_sources = d.get(CONF_SOURCES, {})
    fields: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_HDMI_DEVICE_ID, default=d.get(CONF_HDMI_DEVICE_ID, "")
        ): TEXT,
    }
    for i in range(1, MAX_SOURCES + 1):
        # Find existing values for this slot
        source_name_key = f"source_{i}_name"
        source_cmd_key = f"source_{i}_cmd"
        # Try to get defaults from existing sources dict
        existing_names = list(existing_sources.keys())
        existing_cmds = list(existing_sources.values())
        name_default = existing_names[i - 1] if i - 1 < len(existing_names) else ""
        cmd_default = existing_cmds[i - 1] if i - 1 < len(existing_cmds) else ""

        fields[vol.Optional(source_name_key, default=name_default)] = TEXT
        fields[vol.Optional(source_cmd_key, default=cmd_default)] = TEXT

    return vol.Schema(fields)


def _screen_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SCREEN_DEVICE_ID, default=d.get(CONF_SCREEN_DEVICE_ID, "")
            ): TEXT,
            vol.Required(
                CONF_SCREEN_DOWN_CMD,
                default=d.get(CONF_SCREEN_DOWN_CMD, "screen_down"),
            ): TEXT,
            vol.Required(
                CONF_SCREEN_UP_CMD, default=d.get(CONF_SCREEN_UP_CMD, "screen_up")
            ): TEXT,
            vol.Required(
                CONF_SCREEN_TRAVEL_TIME,
                default=d.get(CONF_SCREEN_TRAVEL_TIME, DEFAULT_SCREEN_TRAVEL_TIME),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5, max=60, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="s"
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
                EntitySelectorConfig(domain="light", multiple=True)
            ),
        }
    )


def _scenes_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Scene config as JSON text.

    Each scene is an object with name, amp_power, volume, source, screen, and
    lights (list of {entity_id, state, brightness}).  Entering these as JSON
    keeps the config flow manageable while still being fully expressive.
    """
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



class HomeTheaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Theater."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 - Amplifier IR config."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_hdmi()

        return self.async_show_form(
            step_id="user",
            data_schema=_amp_schema(),
        )

    async def async_step_hdmi(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 - HDMI Switch IR config."""
        if user_input is not None:
            self._data[CONF_HDMI_DEVICE_ID] = user_input[CONF_HDMI_DEVICE_ID]
            self._data[CONF_SOURCES] = _parse_sources(user_input)
            return await self.async_step_screen()

        return self.async_show_form(
            step_id="hdmi",
            data_schema=_hdmi_schema(),
        )

    async def async_step_screen(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3 - Projector Screen RF config."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_lights()

        return self.async_show_form(
            step_id="screen",
            data_schema=_screen_schema(),
        )

    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4 - Light entity selection."""
        if user_input is not None:
            self._data[CONF_LIGHT_ENTITIES] = user_input.get(
                CONF_LIGHT_ENTITIES, []
            )
            return await self.async_step_scenes()

        return self.async_show_form(
            step_id="lights",
            data_schema=_lights_schema(),
        )

    async def async_step_scenes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 5 - Scene definitions."""
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
        """Get the options flow handler."""
        return HomeTheaterOptionsFlow(config_entry)


class HomeTheaterOptionsFlow(OptionsFlow):
    """Handle options flow for reconfiguration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._config_entry = config_entry
        self._data: dict[str, Any] = dict(config_entry.data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start options flow at amplifier step."""
        return await self.async_step_amp(user_input)

    async def async_step_amp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options Step 1 - Amplifier IR config."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_hdmi()

        return self.async_show_form(
            step_id="amp",
            data_schema=_amp_schema(self._data),
        )

    async def async_step_hdmi(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options Step 2 - HDMI Switch IR config."""
        if user_input is not None:
            self._data[CONF_HDMI_DEVICE_ID] = user_input[CONF_HDMI_DEVICE_ID]
            self._data[CONF_SOURCES] = _parse_sources(user_input)
            return await self.async_step_screen()

        return self.async_show_form(
            step_id="hdmi",
            data_schema=_hdmi_schema(self._data),
        )

    async def async_step_screen(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options Step 3 - Projector Screen RF config."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_lights()

        return self.async_show_form(
            step_id="screen",
            data_schema=_screen_schema(self._data),
        )

    async def async_step_lights(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options Step 4 - Light entity selection."""
        if user_input is not None:
            self._data[CONF_LIGHT_ENTITIES] = user_input.get(
                CONF_LIGHT_ENTITIES, []
            )
            return await self.async_step_scenes()

        return self.async_show_form(
            step_id="lights",
            data_schema=_lights_schema(self._data),
        )

    async def async_step_scenes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options Step 5 - Scene definitions."""
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
