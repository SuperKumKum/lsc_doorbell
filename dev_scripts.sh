#!/bin/bash
set -e

HA_CONFIG_DIR="./config"
REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

function install_deps() {
    echo "Installing dependencies..."
    pip install -r requirements.txt --break-system-packages
    pip install homeassistant-core[dev] --break-system-packages
}

function validate_integration() {
    echo "Validating integration..."
    hassfest .
    python3 -m script.hassfest -p custom_components/lcs_tuya_doorbell
    hass --script check_config --config "$HA_CONFIG_DIR"
}

function setup_environment() {
    echo "Setting up development environment..."
    mkdir -p "$HA_CONFIG_DIR/custom_components"
    ln -sf "$REPO_ROOT/custom_components/lcs_tuya_doorbell" "$HA_CONFIG_DIR/custom_components/lcs_tuya_doorbell"
    
    if [ ! -f "$HA_CONFIG_DIR/configuration.yaml" ]; then
        cat > "$HA_CONFIG_DIR/configuration.yaml" <<EOL
default_config:

logger:
  default: info
  logs:
    custom_components.lcs_tuya_doorbell: debug

lcs_tuya_doorbell:
  devices:
    - name: "Test Doorbell"
      device_id: "your_device_id"
      local_key: "your_local_key" 
      mac: "device_mac_address"
EOL
    fi
}

function run_hass() {
    echo "Starting Home Assistant..."
    python3 -m homeassistant --config "$HA_CONFIG_DIR" --debug
}

function run_tests() {
    echo "Running tests..."
    pytest tests/components/lcs_tuya_doorbell/ --cov=custom_components/lcs_tuya_doorbell
}

function show_help() {
    echo "Development Script for LCS Tuya Doorbell Integration"
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install     Install dependencies"
    echo "  setup       Setup development environment"
    echo "  validate    Validate integration configuration"
    echo "  run         Start Home Assistant with debug mode"
    echo "  test        Run integration tests"
    echo "  all         Run setup, validate and start HA"
    echo "  help        Show this help message"
}

case "$1" in
    install)
        install_deps
        ;;
    setup)
        setup_environment
        ;;
    validate)
        validate_integration
        ;;
    run)
        run_hass
        ;;
    test)
        run_tests
        ;;
    all)
        setup_environment
        validate_integration
        run_hass
        ;;
    help|*)
        show_help
        ;;
esac
