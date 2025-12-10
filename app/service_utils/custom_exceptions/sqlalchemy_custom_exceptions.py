# For SQLAlchemy-specific exceptions in pg_db
# Inherits from base PostgreSQL exceptions for consistent error handling

from service_utils.custom_exceptions.pg_custom_exceptions import (
    DatabaseConnectionError,
    DatabaseInsertError,
    DatabaseReadError,
    DatabaseUpdateError,
    DatabaseDeleteError,
    DatabaseTransactionError
)


class SQLAlchemyConnectionError(DatabaseConnectionError):
    """Raised when SQLAlchemy fails to connect to the database."""
    pass


class SQLAlchemyInsertError(DatabaseInsertError):
    """Raised when SQLAlchemy insert fails."""
    pass


class SQLAlchemyReadError(DatabaseReadError):
    """Raised when SQLAlchemy read fails."""
    pass


class SQLAlchemyUpdateError(DatabaseUpdateError):
    """Raised when SQLAlchemy update fails."""
    pass


class SQLAlchemyDeleteError(DatabaseDeleteError):
    """Raised when SQLAlchemy delete fails."""
    pass


class SQLAlchemyTransactionError(DatabaseTransactionError):
    """Raised when transaction fails."""
    pass


# Additional SQLAlchemy-specific exceptions
class SQLAlchemyTableCreationError(Exception):
    """Raised when SQLAlchemy table creation fails."""
    pass


class SQLAlchemyTableValidationError(Exception):
    """Raised when table definition validation fails."""
    pass


class SQLAlchemyTableExistsError(Exception):
    """Raised when attempting to create a table that already exists."""
    pass