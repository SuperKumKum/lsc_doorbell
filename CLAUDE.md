# LSC Tuya Doorbell Development Guidelines

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Install development dependencies (testing, linting)
pip install pytest pytest-homeassistant-custom-component pylint flake8

# Run pytest
pytest tests/

# Run specific test
pytest tests/components/lsc_tuya_doorbell/test_init.py

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

# Test component communication with netcat
nc -vz <doorbell_ip> 6668

# Check network discovery
python -c "import netifaces; print(netifaces.interfaces())"
```

## Code Style Guidelines
- **Imports**: Standard library → Home Assistant → third-party → local
- **Typing**: Use type hints for all functions and class attributes
- **Async**: All IO operations must be async with proper exception handling
- **Constants**: Define in const.py, use UPPERCASE for constants
- **Naming**: Use snake_case for variables/functions, PascalCase for classes
- **Error Handling**: Catch specific exceptions, log appropriately with different levels
- **Logging**: Use self._LOGGER with appropriate level (debug, info, warning, error)

## Project Structure
This is a Home Assistant custom component that follows standard HA development patterns.