"""
Centralized Configuration Management for pLayStorE Platform.

Provides:
- Environment-based configuration
- Type-safe configuration values
- Configuration validation
- Default values with overrides

Usage:
    from playstorE.core.config import Config
    
    config = Config.from_env()
    print(config.github_token)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security level enumeration"""
    STRICT = "strict"
    RELAXED = "relaxed"
    TRUSTED = "trusted"


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Config:
    """
    Centralized configuration for pLayStorE platform.

    All configuration values are loaded from environment variables
    with sensible defaults for development.

    Environment Variables:
        See field definitions for corresponding env vars.

    Example:
        config = Config.from_env()

        # Access configuration values
        if config.security_level == SecurityLevel.STRICT:
            enable_strict_mode()

        # Get raw dict
        config_dict = config.to_dict()
    """

    # ================================
    # API Configuration
    # ================================
    api_host: str = field(default="0.0.0.0")
    api_port: int = field(default=8000)
    frontend_url: str = field(default="http://localhost:3000")

    # ================================
    # GitHub Configuration
    # ================================
    github_token: Optional[str] = field(default=None)
    github_api_timeout: int = field(default=30)

    # ================================
    # Rate Limiting
    # ================================
    rate_limit_search: str = field(default="100/minute")
    rate_limit_analyze: str = field(default="30/minute")
    rate_limit_install: str = field(default="10/minute")

    # ================================
    # Storage Configuration
    # ================================
    storage_path: str = field(default="./altstore_storage")
    workflow_storage: str = field(default="./data/workflows")
    capsule_storage: str = field(default="./altstore_storage/capsules")

    # ================================
    # Security Configuration
    # ================================
    security_level: SecurityLevel = field(default=SecurityLevel.STRICT)
    master_key: Optional[str] = field(default=None)
    secret_key: Optional[str] = field(default=None)
    jwt_expiration_hours: int = field(default=24)
    session_timeout: int = field(default=3600)  # seconds
    cryptography_required: bool = field(default=True)

    # ================================
    # Timeouts
    # ================================
    build_timeout: int = field(default=300)  # 5 minutes
    install_timeout: int = field(default=600)  # 10 minutes
    wasm_timeout: int = field(default=30)  # 30 seconds
    docker_timeout: int = field(default=600)  # 10 minutes

    # ================================
    # Feature Flags
    # ================================
    enable_wasm_fallback: bool = field(default=True)
    enable_offline_capsules: bool = field(default=True)
    enable_federated_index: bool = field(default=False)
    enable_github_integration: bool = field(default=True)
    enable_formal_verification: bool = field(default=True)
    enable_reproducible_builds: bool = field(default=True)

    # ================================
    # Logging Configuration
    # ================================
    log_level: LogLevel = field(default=LogLevel.INFO)
    log_format: str = field(default="text")  # text or json
    log_file: Optional[str] = field(default=None)

    # ================================
    # Database Configuration (Optional)
    # ================================
    database_url: Optional[str] = field(default=None)
    redis_url: Optional[str] = field(default=None)

    # ================================
    # Monitoring Configuration (Optional)
    # ================================
    sentry_dsn: Optional[str] = field(default=None)
    enable_prometheus: bool = field(default=False)
    prometheus_port: int = field(default=9090)

    # ================================
    # Development Only
    # ================================
    dev_reload: bool = field(default=False)
    debug: bool = field(default=False)
    test_mode: bool = field(default=False)

    @classmethod
    def from_env(cls) -> 'Config':
        """
        Create configuration from environment variables.

        Environment variable names match field names in uppercase.
        Example: api_host -> API_HOST

        Returns:
            Config instance with values from environment
        """
        values = {}

        # API Configuration
        values['api_host'] = os.getenv('API_HOST', '0.0.0.0')
        values['api_port'] = int(os.getenv('API_PORT', '8000'))
        values['frontend_url'] = os.getenv('FRONTEND_URL', 'http://localhost:3000')

        # GitHub Configuration
        values['github_token'] = os.getenv('GITHUB_TOKEN')
        values['github_api_timeout'] = int(os.getenv('GITHUB_API_TIMEOUT', '30'))

        # Rate Limiting
        values['rate_limit_search'] = os.getenv('RATE_LIMIT_SEARCH', '100/minute')
        values['rate_limit_analyze'] = os.getenv('RATE_LIMIT_ANALYZE', '30/minute')
        values['rate_limit_install'] = os.getenv('RATE_LIMIT_INSTALL', '10/minute')

        # Storage Configuration
        values['storage_path'] = os.getenv('ALTSTORE_STORAGE', './altstore_storage')
        values['workflow_storage'] = os.getenv('WORKFLOW_STORAGE', './data/workflows')
        values['capsule_storage'] = os.getenv('CAPSULE_STORAGE', './altstore_storage/capsules')

        # Security Configuration
        security_level_str = os.getenv('SECURITY_LEVEL', 'strict').lower()
        try:
            values['security_level'] = SecurityLevel(security_level_str)
        except ValueError:
            logger.warning(f"Invalid SECURITY_LEVEL: {security_level_str}, using 'strict'")
            values['security_level'] = SecurityLevel.STRICT

        values['master_key'] = os.getenv('MASTER_KEY')
        values['secret_key'] = os.getenv('SECRET_KEY')
        values['jwt_expiration_hours'] = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
        values['session_timeout'] = int(os.getenv('SESSION_TIMEOUT', '3600'))
        values['cryptography_required'] = os.getenv('CRYPTOGRAPHY_REQUIRED', 'true').lower() == 'true'

        # Timeouts
        values['build_timeout'] = int(os.getenv('BUILD_TIMEOUT', '300'))
        values['install_timeout'] = int(os.getenv('INSTALL_TIMEOUT', '600'))
        values['wasm_timeout'] = int(os.getenv('WASM_TIMEOUT', '30'))
        values['docker_timeout'] = int(os.getenv('DOCKER_TIMEOUT', '600'))

        # Feature Flags
        values['enable_wasm_fallback'] = os.getenv('ENABLE_WASM_FALLBACK', 'true').lower() == 'true'
        values['enable_offline_capsules'] = os.getenv('ENABLE_OFFLINE_CAPSULES', 'true').lower() == 'true'
        values['enable_federated_index'] = os.getenv('ENABLE_FEDERATED_INDEX', 'false').lower() == 'true'
        values['enable_github_integration'] = os.getenv('ENABLE_GITHUB_INTEGRATION', 'true').lower() == 'true'
        values['enable_formal_verification'] = os.getenv('ENABLE_FORMAL_VERIFICATION', 'true').lower() == 'true'
        values['enable_reproducible_builds'] = os.getenv('ENABLE_REPRODUCIBLE_BUILDS', 'true').lower() == 'true'

        # Logging Configuration
        log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
        try:
            values['log_level'] = LogLevel(log_level_str)
        except ValueError:
            logger.warning(f"Invalid LOG_LEVEL: {log_level_str}, using 'INFO'")
            values['log_level'] = LogLevel.INFO

        values['log_format'] = os.getenv('LOG_FORMAT', 'text').lower()
        values['log_file'] = os.getenv('LOG_FILE')

        # Database Configuration
        values['database_url'] = os.getenv('DATABASE_URL')
        values['redis_url'] = os.getenv('REDIS_URL')

        # Monitoring Configuration
        values['sentry_dsn'] = os.getenv('SENTRY_DSN')
        values['enable_prometheus'] = os.getenv('ENABLE_PROMETHEUS', 'false').lower() == 'true'
        values['prometheus_port'] = int(os.getenv('PROMETHEUS_PORT', '9090'))

        # Development Only
        values['dev_reload'] = os.getenv('DEV_RELOAD', 'false').lower() == 'true'
        values['debug'] = os.getenv('DEBUG', 'false').lower() == 'true'
        values['test_mode'] = os.getenv('TEST_MODE', 'false').lower() == 'true'

        config = cls(**values)

        # Validate configuration
        config.validate()

        return config

    def validate(self):
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate storage paths are within safe directories
        for path_field in ['storage_path', 'workflow_storage', 'capsule_storage']:
            path_value = getattr(self, path_field)
            if '..' in path_value:
                raise ValueError(f"{path_field} contains directory traversal sequence")

            # Ensure path is relative or within home
            path_obj = Path(path_value)
            if path_obj.is_absolute():
                home = Path.home()
                if not str(path_obj).startswith(str(home)):
                    raise ValueError(f"{path_field} must be within user home directory")

        # Validate security keys in production
        if not self.test_mode and not self.debug:
            if self.cryptography_required and not self.secret_key:
                logger.warning("SECRET_KEY not set in production environment")

        # Validate timeouts are positive
        for timeout_field in ['build_timeout', 'install_timeout', 'wasm_timeout', 'docker_timeout']:
            timeout_value = getattr(self, timeout_field)
            if timeout_value <= 0:
                raise ValueError(f"{timeout_field} must be positive")

        # Validate port range
        if not (1 <= self.api_port <= 65535):
            raise ValueError(f"API port must be between 1 and 65535, got {self.api_port}")

        # Validate JWT expiration
        if self.jwt_expiration_hours <= 0:
            raise ValueError("JWT expiration must be positive")

        logger.info("Configuration validated successfully")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dictionary with all configuration values
        """
        return {
            'api_host': self.api_host,
            'api_port': self.api_port,
            'frontend_url': self.frontend_url,
            'github_token': self.github_token,
            'github_api_timeout': self.github_api_timeout,
            'rate_limit_search': self.rate_limit_search,
            'rate_limit_analyze': self.rate_limit_analyze,
            'rate_limit_install': self.rate_limit_install,
            'storage_path': self.storage_path,
            'workflow_storage': self.workflow_storage,
            'capsule_storage': self.capsule_storage,
            'security_level': self.security_level.value,
            'master_key': '***' if self.master_key else None,  # Mask sensitive values
            'secret_key': '***' if self.secret_key else None,
            'jwt_expiration_hours': self.jwt_expiration_hours,
            'session_timeout': self.session_timeout,
            'cryptography_required': self.cryptography_required,
            'build_timeout': self.build_timeout,
            'install_timeout': self.install_timeout,
            'wasm_timeout': self.wasm_timeout,
            'docker_timeout': self.docker_timeout,
            'enable_wasm_fallback': self.enable_wasm_fallback,
            'enable_offline_capsules': self.enable_offline_capsules,
            'enable_federated_index': self.enable_federated_index,
            'enable_github_integration': self.enable_github_integration,
            'enable_formal_verification': self.enable_formal_verification,
            'enable_reproducible_builds': self.enable_reproducible_builds,
            'log_level': self.log_level.value,
            'log_format': self.log_format,
            'log_file': self.log_file,
            'database_url': self.database_url,
            'redis_url': self.redis_url,
            'sentry_dsn': self.sentry_dsn,
            'enable_prometheus': self.enable_prometheus,
            'prometheus_port': self.prometheus_port,
            'dev_reload': self.dev_reload,
            'debug': self.debug,
            'test_mode': self.test_mode,
        }

    def to_safe_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary with sensitive values masked.

        Returns:
            Dictionary with safe-to-log configuration values
        """
        safe = self.to_dict()
        # Ensure sensitive values are masked
        for key in ['master_key', 'secret_key', 'github_token', 'database_url', 'redis_url', 'sentry_dsn']:
            if safe.get(key):
                safe[key] = '***'
        return safe

    def __post_init__(self):
        """Post-initialization validation"""
        # Auto-enable debug mode in test mode
        if self.test_mode:
            self.debug = True


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Creates instance from environment if not already initialized.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def init_config(config: Config = None) -> Config:
    """
    Initialize global configuration.

    Args:
        config: Optional Config instance to use

    Returns:
        Config instance
    """
    global _config
    if config:
        _config = config
    else:
        _config = Config.from_env()
    return _config


# Convenience function for logging configuration
def log_config_summary():
    """Log configuration summary (safe values only)"""
    config = get_config()
    safe_config = config.to_safe_dict()

    logger.info("=== Configuration Summary ===")
    for key, value in safe_config.items():
        if value is not None:
            logger.info(f"  {key}: {value}")
    logger.info("=============================")
