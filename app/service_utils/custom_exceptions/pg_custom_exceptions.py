
class DatabaseConnectionError(Exception):
    """Raised when a database connection fails."""
    pass

class DatabaseInsertError(Exception):
    """Raised when an insert operation fails."""
    pass

class DatabaseReadError(Exception):
    """Raised when a read operation fails."""
    pass

class DatabaseUpdateError(Exception):
    """Raised when an update operation fails."""
    pass

class DatabaseDeleteError(Exception):
    """Raised when a delete operation fails."""
    pass

class DatabaseTransactionError(Exception):
    """Raised when a transaction fails."""
    pass
