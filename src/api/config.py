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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

