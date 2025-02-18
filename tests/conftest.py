import sys
from pathlib import Path
import pytest
from homeassistant.core import HomeAssistant
import homeassistant.core as ha

# Add custom_components to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

@pytest.fixture
def hass(tmpdir):
    """Fixture to provide a test instance of Home Assistant."""
    config_dir = tmpdir.mkdir("config")
    hass = ha.HomeAssistant(str(config_dir))
    return hass
