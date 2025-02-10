from typing import Optional, Any, Dict
import json
import hashlib
from app.core.db import get_redis_client


class ToolResponseCache:
    def __init__(self):
        self.redis = None
        self.default_expiry = 1800  # 30 minutes
        self.cache_keys = {
            'LeadConfirmation': 'lead_cache',
            'PlacesSearch': 'places_cache',
            'BookingRequest': 'booking_cache'
        }

    async def initialize(self):
        """Initialize Redis client if not already initialized"""
        if not self.redis:
            self.redis = await get_redis_client()

    def _generate_cache_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Generate a unique cache key based on tool name and arguments"""
        # Sort dictionary keys to ensure consistent hashing
        args_str = json.dumps(args, sort_keys=True)
        # Create a unique hash combining tool name and arguments
        hash_key = hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()
        return f"{self.cache_keys.get(tool_name, 'general')}:{hash_key}"

    async def get_cached_response(self, tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
        """
        Retrieve cached tool response if available

        Args:
            tool_name: Name of the tool (e.g., 'LeadConfirmation')
            args: Dictionary of tool arguments

        Returns:
            Cached response if available and valid, None otherwise
        """
        await self.initialize()
        cache_key = self._generate_cache_key(tool_name, args)

        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        return None

    async def cache_response(self, tool_name: str, args: Dict[str, Any], response: Any,
                             expiry: Optional[int] = None) -> None:
        """
        Cache a tool response with the specified expiry time

        Args:
            tool_name: Name of the tool
            args: Dictionary of tool arguments
            response: Response to cache
            expiry: Cache expiry time in seconds (optional)
        """
        await self.initialize()
        cache_key = self._generate_cache_key(tool_name, args)

        # Use custom expiry time or default
        expiry_time = expiry if expiry is not None else self.default_expiry

        # Store response with expiry
        await self.redis.set(
            cache_key,
            json.dumps(response),
            ex=expiry_time
        )

    async def invalidate_cache(self, tool_name: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific tool or all tools

        Args:
            tool_name: Name of the tool to invalidate (optional, if None invalidates all)
        """
        await self.initialize()

        if tool_name:
            cache_prefix = self.cache_keys.get(tool_name)
            if cache_prefix:
                pattern = f"{cache_prefix}:*"
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)
        else:
            # Invalidate all tool caches
            for prefix in self.cache_keys.values():
                pattern = f"{prefix}:*"
                keys = await self.redis.keys(pattern)
                if keys:
                    await self.redis.delete(*keys)