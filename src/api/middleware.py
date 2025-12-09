"""
Middleware for logging requests and responses to Google Sheets
"""
import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from loguru import logger

from .sheets_logger import get_sheets_logger


class SheetsLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests and responses to Google Sheets
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log to Google Sheets
        
        Args:
            request: The incoming request
            call_next: The next middleware/endpoint handler
            
        Returns:
            Response from the endpoint
        """
        # Start timing
        start_time = time.time()
        
        # Store request body if present (for POST requests)
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes.decode())
                # Important: we need to make the body available again for the endpoint
                # This is handled automatically by FastAPI's dependency injection
            except Exception as e:
                logger.debug(f"Could not parse request body: {e}")
        
        # Extract query parameters
        query_params = dict(request.query_params) if request.query_params else None
        
        # Get client info
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Process the request
        response = None
        error = None
        success = True
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            success = 200 <= status_code < 400
            
        except Exception as e:
            error = str(e)
            success = False
            logger.error(f"Error processing request: {e}")
            raise
        
        finally:
            # Calculate response time
            response_time = time.time() - start_time
            
            # Get cache hit status from response headers if available
            cache_hit = None
            response_size = None
            
            if response:
                cache_status = response.headers.get("X-Cache-Status")
                if cache_status:
                    cache_hit = cache_status == "HIT"
                
                # Try to get response size
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        response_size = int(content_length)
                    except ValueError:
                        pass
            
            # Log to Google Sheets (async)
            sheets_logger = get_sheets_logger()
            if sheets_logger and sheets_logger.enabled:
                try:
                    await sheets_logger.log_request_async(
                        method=request.method,
                        endpoint=request.url.path,
                        status_code=status_code,
                        query_params=query_params,
                        request_body=request_body,
                        response_time=response_time,
                        cache_hit=cache_hit,
                        success=success,
                        error=error,
                        client_ip=client_ip,
                        user_agent=user_agent,
                        response_size=response_size
                    )
                except Exception as e:
                    logger.error(f"Failed to log to Google Sheets: {e}")
        
        return response

