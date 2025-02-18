from unittest.mock import Mock
from homeassistant.core import HomeAssistant
import pytest
from custom_components.lsc_tuya_doorbell import async_setup_entry
from homeassistant.config_entries import ConfigEntry

async def test_basic_setup(hass: HomeAssistant):
    """Test basic setup of the integration."""
    entry = ConfigEntry(
        version=1,
        domain="lsc_tuya_doorbell",
        title="Test Doorbell",
        data={
            "name": "Test Doorbell",
            "device_id": "test123",
            "local_key": "testkey123",
            "host": "192.168.1.100"
        },
        source="user",
        options={},
        unique_id="test123"
    )
    assert await async_setup_entry(hass, entry) is True
