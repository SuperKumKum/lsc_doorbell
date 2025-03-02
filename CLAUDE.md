# LSC Tuya Doorbell Development Guidelines

## Project Overview
Home Assistant custom component for LSC Smart Connect video doorbells using the Tuya protocol.
Communicates locally with doorbells to detect button presses and motion events without cloud connections.

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt  # netifaces>=0.11.0

# Install development dependencies
pip install pytest pytest-homeassistant-custom-component pylint flake8

# Test direct device connection
python test_doorbell.py --ip <doorbell_ip> --id <device_id> --key <local_key>

# Lint code
flake8 custom_components/
pylint custom_components/
```

## Debugging Commands
```bash
# Enable debug logging in configuration.yaml
logger:
  default: info
  logs:
    custom_components.lsc_tuya_doorbell: debug

# Monitor logs in real-time
tail -f /config/home-assistant.log | grep lsc_tuya_doorbell

# Test device connectivity
nc -vz <doorbell_ip> 6668
```

## Code Style Guidelines
- **Imports**: Standard library → Home Assistant → third-party → local
- **Typing**: Use type hints for all functions and class attributes
- **Async**: All IO operations must be async with proper exception handling
- **Constants**: Define in const.py, use UPPERCASE for constants
- **Naming**: Use snake_case for variables/functions, PascalCase for classes
- **Error Handling**: Catch specific exceptions, log appropriately
- **Logging**: Use self._LOGGER with appropriate level (debug, info, warning, error)

## Project Structure
- `__init__.py`: Component setup and initialization
- `config_flow.py`: UI configuration flow
- `const.py`: Constants and default values
- `network.py`: Tuya device communication
- `sensor.py`: Sensor entity implementation
- `pytuya/`: Local implementation of Tuya protocol
