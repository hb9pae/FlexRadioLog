"""Configuration management for FlexRadioLog."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RadioConfig(BaseModel):
    """Configuration for FlexRadio connection."""
    host: str = Field(default="192.168.84.24", description="IP address of the FlexRadio")
    port: int = Field(default=4992, description="TCP port for SmartSDR commands")
    reconnect_interval_sec: float = Field(default=3.0, description="Initial reconnect delay in seconds")
    reconnect_max_backoff_sec: float = Field(default=30.0, description="Max reconnect backoff delay")
    timeout_sec: float = Field(default=10.0, description="Socket connect timeout")


class DatabaseConfig(BaseModel):
    """Configuration for database persistence."""
    url: str = Field(default="sqlite+aiosqlite:///flexradiolog.db", description="SQLAlchemy database URL")
    echo: bool = Field(default=False, description="Log SQL queries")


class ApiConfig(BaseModel):
    """Configuration for FastAPI REST interface."""
    host: str = Field(default="0.0.0.0", description="Bind IP for API server")
    port: int = Field(default=8000, description="Port for API server")
    title: str = Field(default="FlexRadioLog API", description="API title")


class LoggingConfig(BaseModel):
    """Configuration for logging."""
    level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    file_path: Optional[str] = Field(default="flexradiolog.log", description="Path to log file or null")


class IpAllocationItem(BaseModel):
    """Initial IP to Callsign mapping item."""
    ip_address: str
    callsign: str
    operator_name: Optional[str] = ""
    notes: Optional[str] = ""


class AppConfig(BaseSettings):
    """Master application configuration."""
    model_config = SettingsConfigDict(
        env_prefix="FLEXLOG_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    radio: RadioConfig = Field(default_factory=RadioConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    initial_allocations: List[IpAllocationItem] = Field(default_factory=list)

    @classmethod
    def load_from_yaml(cls, file_path: str | Path = "config.yaml") -> "AppConfig":
        """Load configuration from YAML file with fallback to defaults."""
        path = Path(file_path)
        if not path.is_file():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls.model_validate(data)
