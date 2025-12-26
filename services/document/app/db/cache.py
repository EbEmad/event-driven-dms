import json
import logging
from typing import Any
import redis.asyncio as aioredis
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RedisCache:

    def __init__(self):
        self.redis: aioredis.Redis | None=None

    async def connect(self):
        """Initialize Redis connection."""
        try:
            self.redis=await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )

            await self.redis.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis disconnected")

    async def get(self,key:str)->Any|None:
        """Get value from cache."""
        try:
            value= await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get value from cache: {e}")
            return None
    async def set(self,key:str,value:Any,ttl:int|None=None)->bool:
        """Set value in cache with optional TTL."""
        try:
            ttl = ttl or settings.redis_cache_ttl
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key,ttl,serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to set value in cache: {e}")
            return False

    async def delete(self,key:str)->bool:
        """Delete key from cache."""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key from cache: {e}")
            return False
    
            
    async def delete_pattern(self,pattern:str)->int:
        """Delete all keys matching pattern."""
        try:
            keys=[]
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Failed to delete keys matching pattern: {e}")
            return 0
    
    async def incr(self,key:str)->int:
        """Increment counter atomically."""
        try:
            return await self.redis.incr(key)
        except Exception as e:
            logger.error(f"Failed to increment counter: {e}")
            return 0
    async def pfadd(self,key:str,*values:str)->int:
        """Add values to HyperLogLog."""
        try:
            return await self.redis.pfadd(key, *values)
        except Exception as e:
            logger.error(f"Cache pfadd error for key {key}: {e}")
            return 0
    async def pfcount(self, key: str) -> int:
        """Count unique values in HyperLogLog."""
        try:
            return await self.redis.pfcount(key)
        except Exception as e:
            logger.error(f"Cache pfcount error for key {key}: {e}")
            return 0
cache = RedisCache()
