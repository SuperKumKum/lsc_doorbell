# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Home Assistant custom component for LSC Smart Connect video doorbells using the Tuya protocol.
Communicates locally with doorbells to detect button presses and motion events without cloud connections.

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt  # netifaces>=0.11.0

# Install development dependencies
pip install pytest pytest-homeassistant-custom-component pylint flake8

# Lint code
flake8 custom_components/
pylint custom_components/

# Run all tests 
pytest

# Run a single test
pytest tests/test_file.py::test_specific_function
```

## Debugging Commands
```bash
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
- **Formatting**: 4 spaces for indentation, 120 character line limit