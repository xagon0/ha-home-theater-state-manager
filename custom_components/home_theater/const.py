"""Constants for the Home Theater State Manager integration."""

DOMAIN = "home_theater"

# Storage
STORAGE_KEY = "home_theater_state"
STORAGE_VERSION = 1

# Volume defaults
DEFAULT_VOLUME_MAX_STEPS = 50
VOLUME_MIN = 0.0
VOLUME_MAX = 1.0
DEFAULT_VOLUME = 0.3

# Screen
DEFAULT_SCREEN_TRAVEL_TIME = 15  # seconds

# Volume stepping delay between IR commands (seconds)
VOLUME_STEP_DELAY = 0.15

# Amp power-on settle time (seconds)
AMP_POWER_ON_DELAY = 1.0

# Persistence debounce (seconds)
SAVE_DELAY = 1

# Config keys - Amplifier
CONF_AMP_DEVICE_ID = "amp_device_id"
CONF_AMP_POWER_ON = "amp_power_on_cmd"
CONF_AMP_POWER_OFF = "amp_power_off_cmd"
CONF_AMP_VOLUME_UP = "amp_volume_up_cmd"
CONF_AMP_VOLUME_DOWN = "amp_volume_down_cmd"
CONF_AMP_MUTE = "amp_mute_cmd"
CONF_VOLUME_MAX_STEPS = "volume_max_steps"

# Config keys - HDMI Switch
CONF_HDMI_DEVICE_ID = "hdmi_switch_device_id"
CONF_SOURCES = "sources"

# Config keys - Projector Screen
CONF_SCREEN_DEVICE_ID = "screen_device_id"
CONF_SCREEN_DOWN_CMD = "screen_down_cmd"
CONF_SCREEN_UP_CMD = "screen_up_cmd"
CONF_SCREEN_TRAVEL_TIME = "screen_travel_time"

# Config keys - Lights
CONF_LIGHT_ENTITIES = "light_entities"

# Config keys - Scenes
CONF_SCENES = "scenes"

# Scene keys
SCENE_AMP_POWER = "amp_power"
SCENE_VOLUME = "volume"
SCENE_SOURCE = "source"
SCENE_SCREEN = "screen"
SCENE_LIGHTS = "lights"

# Screen positions
SCREEN_UP = "up"
SCREEN_DOWN = "down"
SCREEN_OPENING = "opening"
SCREEN_CLOSING = "closing"

# Max sources
MAX_SOURCES = 5
