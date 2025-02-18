from unittest.mock import Mock
from homeassistant.core import HomeAssistant
import pytest
from custom_components.lsc_tuya_doorbell import async_setup_entry
from homeassistant.config_entries import ConfigEntry

from unittest.mock import patch, AsyncMock

async def test_basic_setup(hass: HomeAssistant):
    """Test basic setup of the integration."""
    with patch('tinytuya.Device') as mock_device:
        mock_device.return_value = AsyncMock()
        
        entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain="lsc_tuya_doorbell",
            title="Test Doorbell",
            data={
                "name": "Test Doorbell",
                "device_id": "eb3b64e26aad0ee4c8b7vg",
                "local_key": "41357a04f9fafa62",
                "host": "192.168.113.8",
                "port": 6668
            },
            source="user",
            options={},
            unique_id="eb3b64e26aad0ee4c8b7vg",
            discovery_keys=None
        )
        
        result = await async_setup_entry(hass, entry)
        assert result is True
