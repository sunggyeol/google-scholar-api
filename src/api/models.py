"""
API request and response models
Defines Pydantic models for API validation and documentation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Re-export models from the library for convenience
from google_scholar_lib.models import (
    GoogleScholarResponse,
    OrganicResult,
    Author,
    AuthorProfile,
    SearchMetadata,
    SearchParameters,
    SearchInformation,
    InlineLinks
)


# ========== Request Models ==========

class ScholarSearchRequest(BaseModel):
    """Request model for scholar publication search"""
    q: str = Field(..., description="Search query", min_length=1, max_length=500)
    num: int = Field(default=10, description="Number of results", ge=1, le=100)
    start: int = Field(default=0, description="Start position for pagination", ge=0)
    hl: str = Field(default="en", description="Language code")
    as_ylo: Optional[str] = Field(None, description="Start year filter")
    as_yhi: Optional[str] = Field(None, description="End year filter")
    scisbd: Optional[int] = Field(None, description="Sort by date (0=relevance, 1=date)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "q": "machine learning",
                "num": 10,
                "start": 0,
                "hl": "en"
            }
        }


class ProfileSearchRequest(BaseModel):
    """Request model for author profile search"""
    q: str = Field(..., description="Author name to search", min_length=1, max_length=200)
    hl: str = Field(default="en", description="Language code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "q": "Andrew Ng",
                "hl": "en"
            }
        }


# ========== Response Models ==========

class APIResponse(BaseModel):
    """Base API response wrapper"""
    success: bool = Field(default=True, description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Optional message")
    cache_hit: bool = Field(default=False, description="Whether response came from cache")
    data: Optional[Any] = Field(None, description="Response data")


class ScholarSearchResponse(APIResponse):
    """Response model for scholar search"""
    data: Optional[GoogleScholarResponse] = None


class AuthorResponse(APIResponse):
    """Response model for author profile"""
    data: Optional[GoogleScholarResponse] = None


class ProfileSearchResponse(APIResponse):
    """Response model for profile search"""
    data: Optional[GoogleScholarResponse] = None


class CiteResponse(APIResponse):
    """Response model for citation information"""
    data: Optional[GoogleScholarResponse] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(default=False)
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Invalid request",
                "detail": "Query parameter 'q' is required"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="healthy", description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="API version")
    cache_enabled: bool = Field(..., description="Whether Redis caching is enabled")
    cache_stats: Optional[Dict[str, Any]] = Field(None, description="Cache statistics")


class CacheStatsResponse(BaseModel):
    """Cache statistics response"""
    enabled: bool
    hits: int
    misses: int
    errors: int
    total_requests: int
    hit_rate_percent: float

