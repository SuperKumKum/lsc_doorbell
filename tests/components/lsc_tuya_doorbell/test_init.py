from homeassistant.core import HomeAssistant
import pytest
from custom_components.lsc_tuya_doorbell import async_setup_entry

@pytest.mark.asyncio
async def test_basic_setup(hass: HomeAssistant):
    """Test basic setup of the integration."""
    await hass.async_start()
    assert await async_setup_entry(hass, None) is True
    await hass.async_stop()
