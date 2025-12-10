"""
Custom exceptions for handling CRUD operations in Redis.
"""

class RedisConnectionError(Exception):
    """Raised when a Redis connection fails."""
    pass

class RedisInsertError(Exception):
    """Raised when a Redis insert/set operation fails."""
    pass

class RedisReadError(Exception):
    """Raised when a Redis read/get operation fails."""
    pass

class RedisUpdateError(Exception):
    """Raised when a Redis update operation fails."""
    pass

class RedisDeleteError(Exception):
    """Raised when a Redis delete operation fails."""
    pass

class RedisZSetError(Exception):
    """Raised when a Redis ZSET operation fails."""
    pass