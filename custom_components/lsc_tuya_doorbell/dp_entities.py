"""DP (Data Point) entity definitions for different firmware versions."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

# Define DP types
class DPType(str, Enum):
    """DP data types."""
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"
    ENUM = "enum"
    RAW = "raw"

# Define DP categories
class DPCategory(str, Enum):
    """DP categories."""
    STATUS_ONLY = "status_only"
    STATUS_FUNCTION = "status_function"

@dataclass
class DPDefinition:
    """Definition for a Tuya DP (Data Point)."""
    id: str  # DP ID as string
    code: str  # DP code name
    name: str  # Display name
    dp_type: DPType  # Data type
    category: DPCategory  # Category
    icon: str = "mdi:help-circle"  # Default icon
    unit: Optional[str] = None  # Unit of measurement
    options: Optional[Dict[str, str]] = None  # Options for enum type
    min_value: Optional[int] = None  # For integer types
    max_value: Optional[int] = None  # For integer types
    step: Optional[int] = None  # For integer types
    momentary: bool = False  # Whether this is a momentary switch that auto-resets

# Version 4.0.7 DPs
V4_DP_DEFINITIONS = {
    "101": DPDefinition(
        id="101",
        code="basic_indicator",
        name="Indicator",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:led-on",
        momentary=True  # Mark as momentary switch
    ),
    "103": DPDefinition(
        id="103",
        code="basic_flip",
        name="Vision Flip",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:flip-horizontal"
    ),
    "104": DPDefinition(
        id="104",
        code="basic_osd",
        name="OSD Watermark",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:watermark"
    ),
    "106": DPDefinition(
        id="106",
        code="motion_sensitivity",
        name="Motion Sensitivity",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:motion-sensor",
        options={
            "0": "Low",
            "1": "Medium",
            "2": "High"
        }
    ),
    "108": DPDefinition(
        id="108",
        code="basic_nightvision",
        name="Night Vision",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:weather-night",
        options={
            "0": "Auto",
            "1": "Off",
            "2": "On"
        }
    ),
    "109": DPDefinition(
        id="109",
        code="sd_storge",
        name="SD Card Capacity",
        dp_type=DPType.STRING,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:micro-sd"
    ),
    "110": DPDefinition(
        id="110",
        code="sd_status",
        name="SD Card Status",
        dp_type=DPType.INTEGER,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:micro-sd"
    ),
    "111": DPDefinition(
        id="111",
        code="sd_format",
        name="Format SD Card",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_ONLY,  # Changed to STATUS_ONLY to prevent interactive format
        icon="mdi:format-color-fill"
    ),
    "115": DPDefinition(
        id="115",
        code="movement_detect_pic",
        name="Motion Detected",
        dp_type=DPType.RAW,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:motion-sensor"
    ),
    "117": DPDefinition(
        id="117",
        code="sd_format_state",
        name="SD Format State",
        dp_type=DPType.INTEGER,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:format-color-fill"
    ),
    "134": DPDefinition(
        id="134",
        code="motion_switch",
        name="Motion Alert",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:motion-sensor"
    ),
    "136": DPDefinition(
        id="136",
        code="doorbell_active",
        name="Doorbell Active",
        dp_type=DPType.STRING,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:doorbell"
    ),
    "150": DPDefinition(
        id="150",
        code="record_switch",
        name="Record Switch",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:record-rec"
    ),
    "151": DPDefinition(
        id="151",
        code="record_mode",
        name="Recording Mode",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:record-rec",
        options={
            "0": "Event Recording",
            "1": "Continuous Recording"
        }
    ),
    "156": DPDefinition(
        id="156",
        code="chime_ring_tune",
        name="Chime Tune",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:bell-ring",
        options={
            "0": "Tune 1",
            "1": "Tune 2",
            "2": "Tune 3",
            "3": "Tune 4"
        }
    ),
    "157": DPDefinition(
        id="157",
        code="chime_ring_volume",
        name="Chime Volume",
        dp_type=DPType.INTEGER,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:volume-high",
        min_value=1,
        max_value=10,
        step=1
    ),
    "160": DPDefinition(
        id="160",
        code="basic_device_volume",
        name="Device Volume",
        dp_type=DPType.INTEGER,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:volume-high",
        min_value=1,
        max_value=10,
        step=1,
        unit=""
    ),
    "165": DPDefinition(
        id="165",
        code="chime_settings",
        name="Bell Selection",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:bell-ring",
        options={
            "0": "Option 1",
            "1": "Option 2",
            "2": "Option 3"
        }
    ),
    "168": DPDefinition(
        id="168",
        code="motion_area_switch",
        name="Motion Area Switch",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:motion-sensor"
    ),
    "169": DPDefinition(
        id="169",
        code="motion_area",
        name="Motion Area",
        dp_type=DPType.STRING,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:motion-sensor"
    ),
    "185": DPDefinition(
        id="185",
        code="alarm_message",
        name="Alarm Report",
        dp_type=DPType.RAW,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:alarm-light"
    ),
    "244": DPDefinition(
        id="244",
        code="EVENT_LINKAGE_TYPE_E",
        name="Event Linkage",
        dp_type=DPType.ENUM,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:link"
    ),
    "253": DPDefinition(
        id="253",
        code="onvif_change_pwd",
        name="ONVIF Password",
        dp_type=DPType.STRING,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:form-textbox-password"
    ),
    "254": DPDefinition(
        id="254",
        code="onvif_ip_addr",
        name="ONVIF IP",
        dp_type=DPType.STRING,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:ip-network"
    ),
    "255": DPDefinition(
        id="255",
        code="onvif_switch",
        name="ONVIF Switch",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:toggle-switch"
    ),
}

# Version 5.0.5 DPs (same as v4 with a few additions)
V5_DP_DEFINITIONS = {
    **V4_DP_DEFINITIONS,  # Include all v4 DPs
    "154": DPDefinition(
        id="154",
        code="someone_ring_doorbell",
        name="Someone Ring Doorbell",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_ONLY,
        icon="mdi:doorbell-video"
    ),
    "155": DPDefinition(
        id="155",
        code="bell_pairing",
        name="Bell Pairing",
        dp_type=DPType.BOOLEAN,
        category=DPCategory.STATUS_FUNCTION,
        icon="mdi:bell-plus"
    ),
}

# Function to get DP definitions based on firmware version
def get_dp_definitions(firmware_version: str) -> Dict[str, DPDefinition]:
    """Return the appropriate DP definitions based on firmware version."""
    if firmware_version == "Version 5":
        return V5_DP_DEFINITIONS
    else:  # Default to Version 4
        return V4_DP_DEFINITIONS