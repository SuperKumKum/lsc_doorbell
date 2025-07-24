from homeassistant.const import CONF_NAME, CONF_HOST, CONF_DEVICE_ID, CONF_PORT

DOMAIN = "lsc_tuya_doorbell"

# Base event type names (not fired directly, used to create device-specific events)
EVENT_BUTTON_PRESS = "lsc_tuya_doorbell_button_press"
EVENT_MOTION_DETECT = "lsc_tuya_doorbell_motion"
EVENT_DEVICE_CONNECTED = "lsc_tuya_doorbell_connected"
EVENT_DEVICE_DISCONNECTED = "lsc_tuya_doorbell_disconnected"

# The integration fires device-specific events in this format:
# {EVENT_TYPE}_{device_name} where device_name is lowercase with underscores
# Examples:
# - lsc_tuya_doorbell_button_press_front_door
# - lsc_tuya_doorbell_motion_front_door
# - lsc_tuya_doorbell_connected_side_door
# - lsc_tuya_doorbell_disconnected_side_door

CONF_LOCAL_KEY = "local_key"
CONF_MAC = "mac"
CONF_LAST_IP = "last_ip"
CONF_DPS_MAP = "dps_map"
CONF_SUBNET = "subnet"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_FIRMWARE_VERSION = "firmware_version"
CONF_BUTTON_DP = "button_dp"
CONF_MOTION_DP = "motion_dp"
CONF_SHOW_ADVANCED = "show_advanced"

# Connection validation results
RESULT_WAITING = "waiting"
RESULT_CONNECTING = "connecting"
RESULT_SUCCESS = "success"
RESULT_AUTH_FAILED = "auth_failed"
RESULT_NOT_FOUND = "not_found"
RESULT_CONNECTION_FAILED = "connection_failed"

DEFAULT_PORT = 6668
DEFAULT_PROTOCOL_VERSION = "3.3"
DEFAULT_DPS_MAP = {
    "button": "185",
    "motion": "115"
}

# Protocol versions to try during discovery, in order of likelihood
PROTOCOL_VERSIONS = ["3.3", "3.1", "3.4", "3.2"]

# Firmware versions supported by the device
FIRMWARE_VERSIONS = ["Version 4", "Version 5", "Version 6"]
DEFAULT_FIRMWARE_VERSION = "Version 4"

# DPS options for each firmware version
V4_DPS_OPTIONS = {
    "button": [
        {"dp_id": "185", "description": "Alarm report (DP 185)"},
        {"dp_id": "136", "description": "Doorbell active (DP 136)"}
    ],
    "motion": [
        {"dp_id": "115", "description": "Motion detection (DP 115)"},
        {"dp_id": "134", "description": "Motion alert (DP 134)"}
    ]
}

V5_DPS_OPTIONS = {
    "button": [
        {"dp_id": "185", "description": "Alarm report (DP 185)"},
        {"dp_id": "136", "description": "Doorbell active (DP 136)"},
        {"dp_id": "154", "description": "Someone ring doorbell (DP 154)"}
    ],
    "motion": [
        {"dp_id": "115", "description": "Motion detection (DP 115)"},
        {"dp_id": "134", "description": "Motion alert (DP 134)"}
    ]
}

V6_DPS_OPTIONS = {
    "button": [
        {"dp_id": "185", "description": "Alarm report (DP 185)"},
        {"dp_id": "136", "description": "Doorbell active (DP 136)"},
        {"dp_id": "154", "description": "Doorbell snapshot (DP 154)"},
        {"dp_id": "212", "description": "Initiative message (DP 212)"}
    ],
    "motion": [
        {"dp_id": "115", "description": "Motion detection (DP 115)"},
        {"dp_id": "152", "description": "PIR sensitivity (DP 152)"},
        {"dp_id": "170", "description": "Human detection (DP 170)"}
    ]
}

# DPS mappings by firmware version
DPS_MAPPINGS = {
    "Version 4": {
        "button": "185",
        "motion": "115"
    },
    "Version 5": {
        "button": "185",
        "motion": "115"
    },
    "Version 6": {
        "button": "185",
        "motion": "115"
    }
}

ATTR_DEVICE_ID = "device_id"
ATTR_IMAGE_DATA = "image_data"
ATTR_TIMESTAMP = "timestamp"
SERVICE_GET_IMAGE_URL = "get_image_url"
DEFAULT_BUCKET = "ty-us-storage30-pic"
SENSOR_TYPES = ["motion", "button", "status"]
