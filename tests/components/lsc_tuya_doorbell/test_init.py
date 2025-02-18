from homeassistant.core import HomeAssistant
from custom_components.lsc_tuya_doorbell import async_setup_entry

async def test_basic_setup(hass: HomeAssistant):
    """Test basic setup of the integration."""
    assert await async_setup_entry(hass, None) is True
