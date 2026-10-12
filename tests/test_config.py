"""Tests for configuration loading and validation."""

from pathlib import Path
import tempfile
import yaml
from flexradiolog.config import AppConfig


def test_default_config():
    config = AppConfig()
    assert config.radio.host == "192.168.84.24"
    assert config.radio.port == 4992
    assert "sqlite" in config.database.url
    assert config.api.port == 8000


def test_yaml_config_loading():
    data = {
        "radio": {
            "host": "192.168.1.100",
            "port": 4992,
        },
        "initial_allocations": [
            {
                "ip_address": "192.168.1.55",
                "callsign": "HB9ABC",
                "operator_name": "Test Op",
            }
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        temp_path = f.name

    try:
        config = AppConfig.load_from_yaml(temp_path)
        assert config.radio.host == "192.168.1.100"
        assert len(config.initial_allocations) == 1
        assert config.initial_allocations[0].callsign == "HB9ABC"
    finally:
        Path(temp_path).unlink(missing_ok=True)
