from homeassistant.const import CONF_NAME, CONF_HOST, CONF_DEVICE_ID, CONF_PORT

DOMAIN = "lsc_tuya_doorbell"
EVENT_BUTTON_PRESS = "lsc_tuya_doorbell_button_press"
EVENT_MOTION_DETECT = "lsc_tuya_doorbell_motion"
EVENT_DEVICE_CONNECTED = "lsc_tuya_doorbell_connected"
EVENT_DEVICE_DISCONNECTED = "lsc_tuya_doorbell_disconnected"

CONF_LOCAL_KEY = "local_key"
CONF_MAC = "mac"
CONF_LAST_IP = "last_ip"
CONF_DPS_MAP = "dps_map"
CONF_SUBNET = "subnet"
CONF_PROTOCOL_VERSION = "protocol_version"

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

ATTR_DEVICE_ID = "device_id"
ATTR_IMAGE_DATA = "image_data"
ATTR_TIMESTAMP = "timestamp"
SERVICE_GET_IMAGE_URL = "get_image_url"
DEFAULT_BUCKET = "ty-us-storage30-pic"
SENSOR_TYPES = ["motion", "button", "status"]
