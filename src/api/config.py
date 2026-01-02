"""
Configuration management for the Google Scholar API
Uses Pydantic Settings for environment-based configuration
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file"""
    
    # API Settings
    api_title: str = "Google Scholar API"
    api_version: str = "1.0.0"
    api_description: str = "REST API for Google Scholar searches with Redis caching"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Redis Settings
    redis_host: str = Field(default="localhost", description="Redis server host")
    redis_port: int = Field(default=6379, description="Redis server port")
    redis_password: Optional[str] = Field(default=None, description="Redis password (optional)")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_enabled: bool = Field(default=True, description="Enable/disable Redis caching")
    
    # Cache TTL Settings (in seconds)
    cache_ttl_scholar: int = Field(default=86400, description="Cache TTL for scholar search (24 hours)")
    cache_ttl_author: int = Field(default=604800, description="Cache TTL for author profiles (7 days)")
    cache_ttl_profiles: int = Field(default=43200, description="Cache TTL for profile search (12 hours)")
    cache_ttl_cite: int = Field(default=2592000, description="Cache TTL for citations (30 days)")
    
    # CORS Settings
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins"
    )
    
    # Rate Limiting (optional - for future implementation)
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds
    
    # Google Sheets Logging Settings
    sheets_logging_enabled: bool = Field(
        default=False,
        description="Enable/disable Google Sheets logging"
    )
    sheets_spreadsheet_id: Optional[str] = Field(
        default=None,
        description="Google Sheets spreadsheet ID (from URL)"
    )
    sheets_credentials_path: str = Field(
        default="credentials/google-sheets-credentials.json",
        description="Path to Google Sheets service account credentials JSON"
    )
    sheets_sheet_name: str = Field(
        default="API Logs",
        description="Name of the sheet tab to log to"
    )

    # Selenium Pool Settings (optimized for 1GB RAM by default)
    selenium_pool_size: int = Field(
        default=1,
        description="Initial number of Selenium drivers in the pool (1 for 1GB RAM)"
    )
    selenium_max_pool_size: int = Field(
        default=2,
        description="Maximum number of drivers during load spikes (2 for 1GB RAM)"
    )
    selenium_max_requests_per_driver: int = Field(
        default=50,
        description="Recycle driver after N requests (memory optimization)"
    )
    selenium_driver_startup_timeout: int = Field(
        default=10,
        description="Driver initialization timeout (seconds)"
    )
    selenium_acquire_timeout: int = Field(
        default=10,
        description="Max wait time for driver acquisition (seconds) - triggers 503 if exceeded"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

