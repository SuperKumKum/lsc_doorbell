from homeassistant.const import CONF_NAME, CONF_HOST, CONF_DEVICE_ID, CONF_PORT

DOMAIN = "lcs_tuya_doorbell"
EVENT_BUTTON_PRESS = "lcs_tuya_doorbell_button_press"
EVENT_MOTION_DETECT = "lcs_tuya_doorbell_motion"

CONF_LOCAL_KEY = "local_key"
CONF_MAC = "mac"
CONF_DPS_MAP = "dps_map"

DEFAULT_PORT = 6668
DEFAULT_DPS_MAP = {
    "button": 185,
    "motion": 115
}

ATTR_DEVICE_ID = "device_id"
ATTR_IMAGE_DATA = "image_data"
ATTR_TIMESTAMP = "timestamp"
