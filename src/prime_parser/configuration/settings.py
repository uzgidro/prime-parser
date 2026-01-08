"""Configuration management for the PDF parser service."""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..utils.exceptions import ConfigurationError


class ApiConfig(BaseModel):
    """API server configuration."""

    host: str = Field(..., description="API host")
    port: int = Field(..., description="API port")
    incoming_api_key: str = Field(..., description="API key for incoming requests")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR)")
    format: str = Field(..., description="Log format (json or text)")


class RetryConfig(BaseModel):
    """Retry configuration for HTTP client."""

    max_attempts: int = Field(..., description="Maximum number of retry attempts")
    backoff_factor: float = Field(..., description="Exponential backoff factor")
    max_delay: float = Field(..., description="Maximum delay between retries in seconds")


class ForwardingConfig(BaseModel):
    """Configuration for forwarding data to external service."""

    endpoint: str = Field(..., description="External service endpoint URL")
    api_key: str = Field(..., description="API key for outgoing requests")
    timeout: int = Field(..., description="Request timeout in seconds")
    retry: RetryConfig = Field(..., description="Retry configuration")


class Settings(BaseSettings):
    """Application settings."""

    environment: str = Field(..., description="Environment name (dev, prod)")
    api: ApiConfig = Field(..., description="API configuration")
    logging: LoggingConfig = Field(..., description="Logging configuration")
    forwarding: ForwardingConfig = Field(..., description="Forwarding configuration")

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    @classmethod
    def from_yaml(cls, config_file: Path) -> "Settings":
        """Load settings from YAML file with environment variable expansion.

        Args:
            config_file: Path to YAML configuration file

        Returns:
            Settings instance

        Raises:
            ConfigurationError: If configuration file is invalid
        """
        try:
            with open(config_file, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                raise ConfigurationError(f"Empty configuration file: {config_file}")

            # Expand environment variables
            config_data = cls._expand_env_vars(config_data)

            return cls(**config_data)

        except FileNotFoundError:
            raise ConfigurationError(f"Configuration file not found: {config_file}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {config_file}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    @staticmethod
    def _expand_env_vars(data: Any) -> Any:
        """Recursively expand ${VAR:-default} patterns in configuration.

        Args:
            data: Configuration data (dict, list, or string)

        Returns:
            Configuration data with expanded environment variables
        """
        if isinstance(data, dict):
            return {k: Settings._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [Settings._expand_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            # Parse ${VAR:-default} format
            match = re.match(r"\$\{([^:}]+)(?::-(.*))?\}", data)
            if match:
                var_name, default = match.groups()
                return os.getenv(var_name, default or "")
        return data


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance for current environment

    Raises:
        ConfigurationError: If configuration cannot be loaded
    """
    env = os.getenv("ENVIRONMENT", "dev")
    config_filename = f"{env}.yaml"

    # Priority 1: CONFIG_DIR environment variable
    if config_dir_env = os.getenv("CONFIG_DIR"):
        config_file = Path(config_dir_env) / config_filename
        if config_file.exists():
            return Settings.from_yaml(config_file)

    # Priority 2: /app/config (Docker standard)
    docker_config_file = Path("/app/config") / config_filename
    if docker_config_file.exists():
        return Settings.from_yaml(docker_config_file)

    # Priority 3: Relative to source (Local development)
    local_config_dir = Path(__file__).parent.parent.parent.parent / "config"
    local_config_file = local_config_dir / config_filename
    if local_config_file.exists():
        return Settings.from_yaml(local_config_file)

    # If none found
    raise ConfigurationError(
        f"Configuration file {config_filename} not found in any of the expected locations: "
        f"CONFIG_DIR env var, /app/config, or {local_config_dir}."
    )
