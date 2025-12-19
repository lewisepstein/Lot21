import redis
from db_utils.conf.redis_conf import REDIS_URL
from custom_exceptions.redis_custom_exceptions import (
    RedisConnectionError,
    RedisInsertError,
    RedisReadError,
    RedisUpdateError,
    RedisDeleteError,
    RedisZSetError
)
from typing import Any, Optional, Dict

class RedisDB:
    """
    Handles Redis connection and provides basic CRUD operations, including ZSET (sorted set) support.
    """

    def __init__(self) -> None:
        """
        Initialize the Redis connection using REDIS_URL.
        """
        try:
            self.client = redis.Redis.from_url(REDIS_URL)
            # Test connection
            self.client.ping()
        except Exception as e:
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")

    def create(self, key: str, value: Any) -> bool:
        """
        Set a value for a key in Redis.
        """
        if not key:
            raise ValueError("Key must not be empty.")
        try:
            return self.client.set(key, value)
        except Exception as e:
            raise RedisInsertError(f"Failed to set key '{key}': {e}")

    def read(self, key: str) -> Optional[Any]:
        """
        Get the value of a key from Redis.
        """
        if not key:
            raise ValueError("Key must not be empty.")
        try:
            value = self.client.get(key)
            return value if value is not None else None
        except Exception as e:
            raise RedisReadError(f"Failed to read key '{key}': {e}")

    def update(self, key: str, value: Any) -> bool:
        """
        Update the value of an existing key in Redis.
        """
        if not key:
            raise ValueError("Key must not be empty.")
        try:
            if self.client.exists(key):
                return self.client.set(key, value)
            else:
                raise RedisUpdateError(f"Key '{key}' does not exist.")
        except Exception as e:
            raise RedisUpdateError(f"Failed to update key '{key}': {e}")

    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.
        """
        if not key:
            raise ValueError("Key must not be empty.")
        try:
            return self.client.delete(key) > 0
        except Exception as e:
            raise RedisDeleteError(f"Failed to delete key '{key}': {e}")

    # ZSET (sorted set) operations
    def zadd(self, key: str, mapping: Dict[Any, float]) -> int:
        """
        Add one or more members to a sorted set, or update its score if it already exists.

        Args:
            key (str): The name of the sorted set.
            mapping (dict): Dictionary of member: score pairs.

        Returns:
            int: Number of elements added to the sorted set (not including score updates).
        """
        if not key or not isinstance(mapping, dict) or not mapping:
            raise ValueError("Key and mapping must not be empty, and mapping must be a dictionary.")
        try:
            return self.client.zadd(key, mapping)
        except Exception as e:
            raise RedisZSetError(f"Failed to zadd to '{key}': {e}")

    def zrange(self, key: str, start: int, end: int, withscores: bool = False) -> list:
        """
        Return a range of members in a sorted set, by index.

        Args:
            key (str): The name of the sorted set.
            start (int): Start index.
            end (int): End index.
            withscores (bool): Whether to include scores in the result.

        Returns:
            list: List of members (and optionally scores).
        """
        if not key:
            raise ValueError("Key must not be empty.")
        try:
            return self.client.zrange(key, start, end, withscores=withscores)
        except Exception as e:
            raise RedisZSetError(f"Failed to zrange on '{key}': {e}")

    def zrem(self, key: str, *members: Any) -> int:
        """
        Remove one or more members from a sorted set.

        Args:
            key (str): The name of the sorted set.
            members: Members to remove.

        Returns:
            int: Number of members removed.
        """
        if not key or not members:
            raise ValueError("Key and members must not be empty.")
        try:
            return self.client.zrem(key, *members)
        except Exception as e:
            raise RedisZSetError(f"Failed to zrem from '{key}': {e}")

    def close(self) -> None:
        """
        Close the Redis connection.
        """
        try:
            self.client.close()
        except Exception as e:
            raise RedisConnectionError(f"Failed to close Redis connection: {e}")

