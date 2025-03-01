from homeassistant.const import CONF_NAME, CONF_HOST, CONF_DEVICE_ID, CONF_PORT

DOMAIN = "lsc_tuya_doorbell"
EVENT_BUTTON_PRESS = "lsc_tuya_doorbell_button_press"
EVENT_MOTION_DETECT = "lsc_tuya_doorbell_motion"

CONF_LOCAL_KEY = "local_key"
CONF_MAC = "mac"
CONF_LAST_IP = "last_ip"
CONF_DPS_MAP = "dps_map"

DEFAULT_PORT = 6668
DEFAULT_DPS_MAP = {
    "button": "185",
    "motion": "115"
}

ATTR_DEVICE_ID = "device_id"
ATTR_IMAGE_DATA = "image_data"
ATTR_TIMESTAMP = "timestamp"
SERVICE_GET_IMAGE_URL = "get_image_url"
DEFAULT_BUCKET = "ty-us-storage30-pic"
SENSOR_TYPES = ["motion", "button", "status"]
