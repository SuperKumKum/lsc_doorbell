"""Number entities for LSC Tuya Doorbell."""
from typing import Any, Optional
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_DEVICE_ID, CONF_FIRMWARE_VERSION
from .entity import TuyaDoorbellEntity
from .dp_entities import DPType, DPCategory, get_dp_definitions

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities based on a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    device_id = config_entry.data[CONF_DEVICE_ID]
    firmware_version = config_entry.data.get(CONF_FIRMWARE_VERSION, "Version 4")
    
    # Get DP definitions based on firmware version
    dp_definitions = get_dp_definitions(firmware_version)
    
    entities = []
    
    # Add DP-based number entities (integer type and status & function category)
    for dp_id, dp_def in dp_definitions.items():
        if dp_def.dp_type == DPType.INTEGER and dp_def.category == DPCategory.STATUS_FUNCTION:
            entity = TuyaDoorbellNumber(hub, device_id, dp_def)
            _LOGGER.info(f"Creating number entity: {dp_def.name} (DP {dp_id}) with range: {dp_def.min_value}-{dp_def.max_value}")
            entities.append(entity)
    
    if entities:
        async_add_entities(entities)


class TuyaDoorbellNumber(TuyaDoorbellEntity, NumberEntity):
    """Representation of a Tuya doorbell number entity."""
    
    def __init__(self, hub, device_id, dp_definition):
        """Initialize the number entity."""
        super().__init__(hub, device_id, dp_definition)
        
        # Set up number characteristics
        self._attr_native_min_value = dp_definition.min_value if dp_definition.min_value is not None else 0
        self._attr_native_max_value = dp_definition.max_value if dp_definition.max_value is not None else 100
        self._attr_native_step = dp_definition.step if dp_definition.step is not None else 1
        self._attr_mode = NumberMode.SLIDER
        
        # For volume controls, only use percentage if no unit is specified
        if "volume" in dp_definition.code:
            if dp_definition.unit is not None:
                self._attr_native_unit_of_measurement = dp_definition.unit
            else:
                self._attr_native_unit_of_measurement = "%"
            
        # Set initial value if available and can be converted to float
        if self._state is not None and isinstance(self._state, (int, float, bool)) and self._state != "unknown":
            try:
                self._attr_native_value = float(self._state)
            except (ValueError, TypeError):
                # If conversion fails, don't set an initial value
                pass
        
    @property
    def native_value(self) -> Optional[float]:
        """Return the current value."""
        if self._state is None or not isinstance(self._state, (int, float, bool)) or self._state == "unknown":
            return None
        try:
            return float(self._state)
        except (ValueError, TypeError):
            # If conversion fails, return None instead of raising an error
            return None
        
    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Schedule a refresh of this entity's state after a brief delay
        # This helps ensure we have the latest state from the device
        async def delayed_refresh():
            import asyncio
            await asyncio.sleep(1)  # Small delay to avoid overwhelming the device
            await self.async_refresh_state()
            
        self.hass.async_create_task(delayed_refresh())
            
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        # Store the time of this manual update to prevent automatic overrides
        from datetime import datetime
        self._last_manual_update = datetime.now().timestamp()
        
        # Update state immediately for better UI responsiveness
        self._state = int(value)
        self._attr_native_value = float(value)
        self.async_write_ha_state()
        
        # Send command to the device
        _LOGGER.info(f"Setting value for {self.entity_id} to {int(value)}")
        success = await self._hub.set_dp(self._dp_definition.id, int(value))
            
        if success:
            _LOGGER.debug(f"Value for {self.entity_id} set successfully")
            # Schedule a refresh after a brief delay to verify
            async def delayed_refresh():
                import asyncio
                await asyncio.sleep(2)  # Wait 2 seconds before refreshing
                await self.async_refresh_state()
                
            self.hass.async_create_task(delayed_refresh())
        else:
            _LOGGER.warning(f"Failed to set value for {self.entity_id}")