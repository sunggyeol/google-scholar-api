"""
Redis caching layer for Google Scholar API
Handles cache storage, retrieval, and serialization of responses
"""
import json
import hashlib
from typing import Optional, Any, Dict
from datetime import datetime
import redis
from loguru import logger

from google_scholar_lib.models import GoogleScholarResponse
from .config import settings


class CacheManager:
    """Manages Redis caching for API responses"""
    
    def __init__(self):
        self.enabled = settings.redis_enabled
        self.client: Optional[redis.Redis] = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0
        }
        
        if self.enabled:
            try:
                self.client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    password=settings.redis_password,
                    db=settings.redis_db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.client.ping()
                logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}. Caching disabled.")
                self.enabled = False
                self.client = None
    
    def _generate_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """
        Generate a unique cache key from parameters
        
        Args:
            prefix: Key prefix (e.g., 'scholar', 'author', 'profiles', 'cite')
            params: Dictionary of parameters to hash
            
        Returns:
            Cache key string
        """
        # Sort params for consistent hashing
        sorted_params = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"gscholar:{prefix}:{param_hash}"
    
    def get(self, key: str) -> Optional[GoogleScholarResponse]:
        """
        Retrieve cached response
        
        Args:
            key: Cache key
            
        Returns:
            GoogleScholarResponse if found, None otherwise
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            cached_data = self.client.get(key)
            if cached_data:
                self.stats["hits"] += 1
                logger.debug(f"Cache HIT: {key}")
                # Deserialize JSON back to GoogleScholarResponse
                data_dict = json.loads(cached_data)
                return GoogleScholarResponse(**data_dict)
            else:
                self.stats["misses"] += 1
                logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: GoogleScholarResponse, ttl: int) -> bool:
        """
        Store response in cache
        
        Args:
            key: Cache key
            value: GoogleScholarResponse to cache
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            # Serialize GoogleScholarResponse to JSON
            json_data = value.model_dump_json()
            self.client.setex(key, ttl, json_data)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a cache entry
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            result = self.client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return bool(result)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_all(self) -> bool:
        """
        Clear all cache entries with gscholar prefix
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
        
        try:
            # Find all keys with our prefix
            keys = self.client.keys("gscholar:*")
            if keys:
                self.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
            return True
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "enabled": self.enabled,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2)
        }
    
    def get_ttl_for_engine(self, engine: str) -> int:
        """
        Get TTL for a specific engine type
        
        Args:
            engine: Engine name (google_scholar, google_scholar_author, etc.)
            
        Returns:
            TTL in seconds
        """
        ttl_map = {
            "google_scholar": settings.cache_ttl_scholar,
            "google_scholar_author": settings.cache_ttl_author,
            "google_scholar_profiles": settings.cache_ttl_profiles,
            "google_scholar_cite": settings.cache_ttl_cite,
        }
        return ttl_map.get(engine, settings.cache_ttl_scholar)


# Global cache manager instance
cache_manager = CacheManager()

