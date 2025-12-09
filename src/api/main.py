"""
Google Scholar REST API with Redis Caching
FastAPI application providing RESTful endpoints for Google Scholar searches
"""
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys

from google_scholar_lib import GoogleScholar
from google_scholar_lib.models import GoogleScholarResponse

from .config import settings
from .cache import cache_manager
from .sheets_logger import init_sheets_logger, get_sheets_logger
from .middleware import SheetsLoggingMiddleware
from .models import (
    ScholarSearchRequest,
    ProfileSearchRequest,
    ScholarSearchResponse,
    AuthorResponse,
    ProfileSearchResponse,
    CiteResponse,
    ErrorResponse,
    HealthResponse,
    CacheStatsResponse,
    APIResponse
)

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO" if not settings.debug else "DEBUG"
)

# Initialize FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Google Sheets logging middleware
app.add_middleware(SheetsLoggingMiddleware)

# Initialize Google Scholar client
scholar = GoogleScholar(backend='selenium')


# ========== Helper Functions ==========

def get_cached_or_fetch(
    cache_key: str,
    ttl: int,
    fetch_func,
    **kwargs
) -> tuple[GoogleScholarResponse, bool]:
    """
    Get from cache or fetch new data
    
    Args:
        cache_key: Redis cache key
        ttl: Time-to-live in seconds
        fetch_func: Function to call if cache miss
        **kwargs: Arguments to pass to fetch_func
        
    Returns:
        Tuple of (GoogleScholarResponse, cache_hit: bool)
    """
    # Try to get from cache
    cached_result = cache_manager.get(cache_key)
    if cached_result:
        return cached_result, True
    
    # Cache miss - fetch new data
    logger.info(f"Fetching fresh data for cache key: {cache_key}")
    result = fetch_func(**kwargs)
    
    # Store in cache
    cache_manager.set(cache_key, result, ttl)
    
    return result, False


# ========== API Endpoints ==========

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Google Scholar API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.api_version,
        cache_enabled=cache_manager.enabled,
        cache_stats=cache_manager.get_stats()
    )


@app.get("/api/v1/cache/stats", response_model=CacheStatsResponse, tags=["Cache"])
async def get_cache_stats():
    """Get cache statistics"""
    stats = cache_manager.get_stats()
    return CacheStatsResponse(**stats)


@app.post("/api/v1/cache/clear", response_model=APIResponse, tags=["Cache"])
async def clear_cache():
    """Clear all cached entries"""
    success = cache_manager.clear_all()
    if success:
        return APIResponse(
            success=True,
            message="Cache cleared successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@app.get("/api/v1/sheets/stats", response_model=APIResponse, tags=["Google Sheets"])
async def get_sheets_stats():
    """Get Google Sheets logging statistics"""
    sheets_logger = get_sheets_logger()
    if not sheets_logger or not sheets_logger.enabled:
        return APIResponse(
            success=False,
            message="Google Sheets logging is not enabled"
        )
    
    logs_count = sheets_logger.get_logs_count()
    return APIResponse(
        success=True,
        message=f"Google Sheets logging is active. Total logs: {logs_count}",
        data={
            "enabled": True,
            "spreadsheet_id": settings.sheets_spreadsheet_id,
            "sheet_name": settings.sheets_sheet_name,
            "total_logs": logs_count
        }
    )


@app.post("/api/v1/sheets/clear", response_model=APIResponse, tags=["Google Sheets"])
async def clear_sheets_logs():
    """Clear all logs from Google Sheets"""
    sheets_logger = get_sheets_logger()
    if not sheets_logger or not sheets_logger.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheets logging is not enabled"
        )
    
    success = sheets_logger.clear_logs()
    if success:
        return APIResponse(
            success=True,
            message="Google Sheets logs cleared successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear Google Sheets logs"
        )


@app.post("/api/v1/search/scholar", response_model=ScholarSearchResponse, tags=["Search"])
async def search_scholar(request: ScholarSearchRequest, response: Response):
    """
    Search for scholarly publications
    
    - **q**: Search query (required)
    - **num**: Number of results (1-100, default: 10)
    - **start**: Start position for pagination (default: 0)
    - **hl**: Language code (default: en)
    - **as_ylo**: Start year filter (optional)
    - **as_yhi**: End year filter (optional)
    - **scisbd**: Sort by date - 0=relevance, 1=date (optional)
    """
    try:
        # Generate cache key
        cache_key = cache_manager._generate_cache_key(
            "scholar",
            request.model_dump()
        )
        
        # Get TTL for this engine type
        ttl = cache_manager.get_ttl_for_engine("google_scholar")
        
        # Get cached or fetch new
        result, cache_hit = get_cached_or_fetch(
            cache_key=cache_key,
            ttl=ttl,
            fetch_func=scholar.search,
            engine="google_scholar",
            **request.model_dump()
        )
        
        # Set cache status header
        response.headers["X-Cache-Status"] = "HIT" if cache_hit else "MISS"
        
        return ScholarSearchResponse(
            success=True,
            cache_hit=cache_hit,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Scholar search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/v1/author/{author_id}", response_model=AuthorResponse, tags=["Author"])
async def get_author(author_id: str, response: Response):
    """
    Get author profile by Google Scholar ID
    
    - **author_id**: Google Scholar author ID (e.g., JicYPdAAAAAJ for Geoffrey Hinton)
    
    Common author IDs:
    - JicYPdAAAAAJ - Geoffrey Hinton
    - WLN3QrAAAAAJ - Yann LeCun
    - kukA0LcAAAAJ - Yoshua Bengio
    """
    try:
        # Generate cache key
        cache_key = cache_manager._generate_cache_key(
            "author",
            {"author_id": author_id}
        )
        
        # Get TTL for this engine type
        ttl = cache_manager.get_ttl_for_engine("google_scholar_author")
        
        # Get cached or fetch new
        result, cache_hit = get_cached_or_fetch(
            cache_key=cache_key,
            ttl=ttl,
            fetch_func=scholar.search_author,
            author_id=author_id
        )
        
        # Set cache status header
        response.headers["X-Cache-Status"] = "HIT" if cache_hit else "MISS"
        
        return AuthorResponse(
            success=True,
            cache_hit=cache_hit,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Author fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/v1/search/profiles", response_model=ProfileSearchResponse, tags=["Search"])
async def search_profiles(request: ProfileSearchRequest, response: Response):
    """
    Search for author profiles by name
    
    - **q**: Author name to search (required)
    - **hl**: Language code (default: en)
    """
    try:
        # Generate cache key
        cache_key = cache_manager._generate_cache_key(
            "profiles",
            request.model_dump()
        )
        
        # Get TTL for this engine type
        ttl = cache_manager.get_ttl_for_engine("google_scholar_profiles")
        
        # Get cached or fetch new
        result, cache_hit = get_cached_or_fetch(
            cache_key=cache_key,
            ttl=ttl,
            fetch_func=scholar.search,
            engine="google_scholar_profiles",
            **request.model_dump()
        )
        
        # Set cache status header
        response.headers["X-Cache-Status"] = "HIT" if cache_hit else "MISS"
        
        return ProfileSearchResponse(
            success=True,
            cache_hit=cache_hit,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Profile search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/v1/cite/{cite_id}", response_model=CiteResponse, tags=["Citations"])
async def get_citation(cite_id: str, response: Response):
    """
    Get citation formats for a publication
    
    - **cite_id**: Citation ID (data-cid from a paper)
    """
    try:
        # Generate cache key
        cache_key = cache_manager._generate_cache_key(
            "cite",
            {"cite_id": cite_id}
        )
        
        # Get TTL for this engine type
        ttl = cache_manager.get_ttl_for_engine("google_scholar_cite")
        
        # Get cached or fetch new
        result, cache_hit = get_cached_or_fetch(
            cache_key=cache_key,
            ttl=ttl,
            fetch_func=scholar.search_cite,
            data_cid=cite_id
        )
        
        # Set cache status header
        response.headers["X-Cache-Status"] = "HIT" if cache_hit else "MISS"
        
        return CiteResponse(
            success=True,
            cache_hit=cache_hit,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Citation fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========== Error Handlers ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.debug else None
        ).model_dump()
    )


# ========== Startup/Shutdown Events ==========

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Redis caching: {'enabled' if cache_manager.enabled else 'disabled'}")
    if cache_manager.enabled:
        logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")
    
    # Initialize Google Sheets logging
    if settings.sheets_logging_enabled and settings.sheets_spreadsheet_id:
        logger.info("Initializing Google Sheets logging...")
        init_sheets_logger(
            spreadsheet_id=settings.sheets_spreadsheet_id,
            credentials_path=settings.sheets_credentials_path,
            sheet_name=settings.sheets_sheet_name,
            enabled=True
        )
        sheets_logger = get_sheets_logger()
        if sheets_logger and sheets_logger.enabled:
            logger.info(f"Google Sheets logging enabled: Sheet '{settings.sheets_sheet_name}'")
        else:
            logger.warning("Google Sheets logging failed to initialize")
    else:
        logger.info("Google Sheets logging disabled")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("Shutting down API server")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

