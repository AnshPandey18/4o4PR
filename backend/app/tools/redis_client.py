"""Redis client wrapper for GitHub clone metadata caching."""
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime
import redis
from redis.exceptions import RedisError


class RedisClient:
    """Redis client for caching GitHub repository clone metadata."""
    
    def __init__(self):
        """Initialize Redis connection from environment variables."""
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self.db = int(os.getenv("REDIS_DB", "4"))
        self.decode_responses = os.getenv("REDIS_DECODE_RESPONSES", "True").lower() == "true"
        self.cache_ttl = int(os.getenv("REDIS_CACHE_TTL", "604800"))  # 7 days default
        
        # Initialize Redis connection
        self._client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish Redis connection."""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=self.decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self._client.ping()
            print(f"✓ Redis connected: {self.host}:{self.port} (DB {self.db})")
        except RedisError as e:
            print(f"✗ Redis connection failed: {e}")
            self._client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except RedisError:
            return False
    
    def _get_clone_key(self, user_id: int, repo_id: int) -> str:
        """Generate Redis key for clone metadata."""
        return f"clone:{user_id}:{repo_id}"
    
    def get_clone_metadata(self, user_id: int, repo_id: int) -> Optional[Dict[str, Any]]:
        """
        Get clone metadata from Redis cache.
        
        Args:
            user_id: User ID who owns the repository
            repo_id: Repository ID
            
        Returns:
            Clone metadata dict or None if not cached
        """
        if not self.is_connected():
            return None
        
        try:
            key = self._get_clone_key(user_id, repo_id)
            data = self._client.get(key)
            
            if data:
                metadata = json.loads(data) if isinstance(data, str) else data
                print(f"✓ Cache HIT: {key}")
                return metadata
            else:
                print(f"✗ Cache MISS: {key}")
                return None
                
        except (RedisError, json.JSONDecodeError) as e:
            print(f"✗ Redis GET error: {e}")
            return None
    
    def set_clone_metadata(
        self,
        user_id: int,
        repo_id: int,
        metadata: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store clone metadata in Redis cache.
        
        Args:
            user_id: User ID who owns the repository
            repo_id: Repository ID
            metadata: Clone metadata to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (defaults to REDIS_CACHE_TTL)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = self._get_clone_key(user_id, repo_id)
            ttl = ttl or self.cache_ttl
            
            # Add timestamp to metadata
            metadata["cached_at"] = datetime.utcnow().isoformat()
            
            # Serialize and store
            data = json.dumps(metadata)
            self._client.setex(key, ttl, data)
            
            print(f"✓ Cache SET: {key} (TTL: {ttl}s)")
            return True
            
        except (RedisError, TypeError, ValueError) as e:
            print(f"✗ Redis SET error: {e}")
            return False
    
    def delete_clone_metadata(self, user_id: int, repo_id: int) -> bool:
        """
        Delete clone metadata from Redis cache.
        
        Args:
            user_id: User ID who owns the repository
            repo_id: Repository ID
            
        Returns:
            True if deleted, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = self._get_clone_key(user_id, repo_id)
            result = self._client.delete(key)
            
            if result > 0:
                print(f"✓ Cache DELETE: {key}")
                return True
            else:
                print(f"✗ Cache DELETE failed: {key} (key not found)")
                return False
                
        except RedisError as e:
            print(f"✗ Redis DELETE error: {e}")
            return False
    
    def refresh_ttl(self, user_id: int, repo_id: int, ttl: Optional[int] = None) -> bool:
        """
        Refresh TTL for cached clone metadata.
        
        Args:
            user_id: User ID who owns the repository
            repo_id: Repository ID
            ttl: New time-to-live in seconds (defaults to REDIS_CACHE_TTL)
            
        Returns:
            True if TTL refreshed, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            key = self._get_clone_key(user_id, repo_id)
            ttl = ttl or self.cache_ttl
            
            result = self._client.expire(key, ttl)
            
            if result:
                print(f"✓ TTL refreshed: {key} (new TTL: {ttl}s)")
                return True
            else:
                print(f"✗ TTL refresh failed: {key} (key not found)")
                return False
                
        except RedisError as e:
            print(f"✗ Redis EXPIRE error: {e}")
            return False
    
    def get_all_clone_keys(self, user_id: Optional[int] = None) -> list[str]:
        """
        Get all clone metadata keys (for debugging/monitoring).
        
        Args:
            user_id: Optional user ID to filter keys
            
        Returns:
            List of Redis keys
        """
        if not self.is_connected():
            return []
        
        try:
            pattern = f"clone:{user_id}:*" if user_id else "clone:*"
            keys = self._client.keys(pattern)
            return keys if keys else []
            
        except RedisError as e:
            print(f"✗ Redis KEYS error: {e}")
            return []
    
    def flush_all_clones(self) -> bool:
        """
        Delete ALL clone metadata from Redis (use with caution!).
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            keys = self.get_all_clone_keys()
            if keys:
                self._client.delete(*keys)
                print(f"✓ Flushed {len(keys)} clone cache entries")
                return True
            else:
                print("✓ No clone cache entries to flush")
                return True
                
        except RedisError as e:
            print(f"✗ Redis FLUSH error: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get Redis cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        if not self.is_connected():
            return {"connected": False}
        
        try:
            info = self._client.info("stats")
            total_keys = len(self.get_all_clone_keys())
            
            return {
                "connected": True,
                "total_clone_keys": total_keys,
                "total_connections": info.get("total_connections_received", 0),
                "total_commands": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
            
        except RedisError as e:
            print(f"✗ Redis INFO error: {e}")
            return {"connected": False, "error": str(e)}
    
    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        return round((hits / total * 100), 2) if total > 0 else 0.0
    
    def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            try:
                self._client.close()
                print("✓ Redis connection closed")
            except RedisError as e:
                print(f"✗ Redis close error: {e}")


# Singleton instance
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """
    Get singleton Redis client instance.
    
    Returns:
        RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis_client() -> None:
    """Close the singleton Redis client."""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None
