"""
PostgreSQL persistent connection and base CRUD class for the ETL tool.

Implements SQLAlchemy and custom exceptions from exceptions.py.
Features a singleton pattern for shared persistent connections across all database functions.
"""
import threading
import logging
from typing import Generator

from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import create_engine, Table, MetaData, select, insert, update, delete, text, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine
from typing import Optional, Dict, Any, List, Tuple, TypeVar

from service_utils.custom_exceptions.sqlalchemy_custom_exceptions import (
    SQLAlchemyConnectionError,
    SQLAlchemyInsertError,
    SQLAlchemyReadError,
    SQLAlchemyUpdateError,
    SQLAlchemyDeleteError,
    SQLAlchemyTransactionError
)

from service_utils.db_utils.conf.postgres_db_conf import POSTGRES_URL
from service_utils.log_management import get_logger

T = TypeVar('T')

# Set up logging
logger = get_logger(__name__)


class PostgresDB:
    """
    Handles persistent PostgreSQL connection and provides basic CRUD operations using SQLAlchemy.
    
    This class implements a singleton pattern to ensure a single shared database connection
    across all database functions in the system. The connection is thread-safe and persistent,
    reducing connection overhead and improving performance.

    Singleton Features:
        - Single shared database connection across the entire application
        - Thread-safe initialization and access
        - Automatic connection recovery on failures
        - Shared connection pool for optimal resource usage
        - Lazy initialization - connection created only when first accessed

    Transaction Support:
        - All write operations use SQLAlchemy's begin() context manager
        - Automatic rollback on any SQLAlchemyError
        - Manual transaction control available via execute_transaction()
        - Bulk operations supported with transactional safety

    Examples:
        >>> # Get the singleton instance (creates connection on first call)
        >>> db = PostgresDB()
        >>> 
        >>> # All subsequent calls return the same instance
        >>> db2 = PostgresDB()
        >>> assert db is db2  # Same instance
        >>> 
        >>> # Create a new user (transactional)
        >>> user_data = {'username': 'john', 'email': 'john@example.com'}
        >>> new_user = db.create('users', user_data)
        >>> 
        >>> # Read users (uses shared connection)
        >>> all_users = db.read('users')
        >>> active_users = db.read('users', {'is_active': True})
        >>> 
        >>> # Update user (transactional)
        >>> updated = db.update('users', {'email': 'new@example.com'}, {'id': 1})
        >>> 
        >>> # Delete user (transactional)
        >>> deleted = db.delete('users', {'id': 1})
        >>> 
        >>> # Connection is automatically managed - no need to close manually
        >>> # But you can still use as context manager if needed
        >>> with PostgresDB() as db:
        ...     users = db.read('users')
    """

    _instance = None
    _lock = threading.Lock()
    _engine = None
    _metadata = None
    _connection_initialized = False
    _table_cache = {}

    def __new__(cls):
        """
        Implement singleton pattern with thread-safe initialization.
        
        Returns:
            PostgresDB: The singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super(PostgresDB, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """
        Initialize the singleton PostgresDB instance with persistent connection.
        
        This method is called every time PostgresDB() is instantiated, but the actual
        initialization only happens once due to the singleton pattern.
        """
        if not self._connection_initialized:
            with self._lock:
                # Double-check locking for initialization
                if not self._connection_initialized:
                    self._initialize_connection()
                    self._connection_initialized = True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _initialize_connection(self) -> None:
        """
        Initialize the SQLAlchemy engine with persistent connection settings.
        
        This method sets up the database engine with optimized settings for
        persistent connections including connection pooling and error handling.
        
        Retries:
            - Maximum 3 attempts with exponential backoff
            - Initial wait: 4s, max wait: 10s between retries
        """
        try:
            logger.info("Initializing PostgresDB singleton with persistent connection")
            
            # Create engine with persistent connection settings
            self._engine: Engine = create_engine(
                POSTGRES_URL,
                # Connection pool settings for persistent connections
                pool_size=20,           # Number of connections to maintain in pool
                max_overflow=30,        # Additional connections beyond pool_size
                pool_timeout=30,        # Timeout for getting connection from pool
                pool_recycle=3600,      # Recycle connections after 1 hour
                pool_pre_ping=True,     # Validate connections before use
                # Performance settings
                echo=False,             # Set to True for SQL logging in development
                connect_args={
                    "connect_timeout": 10,
                    "application_name": "tiger_etl_persistent",
                    "keepalives": 1,              # Enable TCP keepalive
                    "keepalives_idle": 30,        # Idle time before sending keepalive
                    "keepalives_interval": 10,    # Interval between keepalives
                    "keepalives_count": 5         # Max number of keepalive retries
                },
                execution_options={
                    "timeout": 30                 # Query execution timeout in seconds
                }
            )
            
            self._metadata = MetaData()
            
            # Test the connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("PostgresDB singleton connection established successfully")
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to initialize PostgresDB singleton: {e}")
            raise SQLAlchemyConnectionError(f"Failed to connect to database: {e}") from e

    @property
    def engine(self) -> Engine:
        """
        Get the SQLAlchemy engine instance.
        
        Returns:
            Engine: The SQLAlchemy engine instance
        """
        if self._engine is None:
            self._initialize_connection()
        return self._engine

    @property
    def metadata(self) -> MetaData:
        """
        Get the SQLAlchemy metadata instance.
        
        Returns:
            MetaData: The SQLAlchemy metadata instance
        """
        if self._metadata is None:
            self._initialize_connection()
        return self._metadata

    def _get_table(self, table_name: str) -> Table:
        """
        Get table with caching and SQL injection prevention. Thread-safe implementation.
        
        Args:
            table_name (str): Name of the table to get
            
        Returns:
            Table: SQLAlchemy Table object
            
        Raises:
            ValueError: If table_name contains invalid characters
        """
        # Prevent SQL injection by validating table name
        if not table_name.isidentifier():
            raise ValueError(f"Invalid table name: {table_name}")
            
        # Thread-safe cache access
        with self._lock:
            # Check cache first
            if table_name in self._table_cache:
                return self._table_cache[table_name]
                
            # Create and cache table
            table = Table(table_name, self.metadata, autoload_with=self.engine)
            self._table_cache[table_name] = table
            return table

    def _validate_data(self, table: Table, data: Dict[str, Any]) -> None:
        """
        Validate data types and constraints before insert/update operations.
        
        Args:
            table (Table): SQLAlchemy Table object
            data (Dict[str, Any]): Data to validate
            
        Raises:
            ValueError: If column name is invalid or data type doesn't match
        """
        for column_name, value in data.items():
            if column_name not in table.columns:
                raise ValueError(f"Invalid column name: {column_name}")
            
            column = table.columns[column_name]
            if value is not None:  # Skip validation for NULL values
                expected_type = column.type.python_type
                
                # Check if value is already the correct type
                if not isinstance(value, expected_type):
                    try:
                        # Attempt to convert value to column's Python type
                        expected_type(value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"Invalid type for column {column_name}: "
                            f"expected {expected_type.__name__}, "
                            f"got {type(value).__name__}"
                        ) from e

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the current database connection and pool health.
        
        Returns:
            Dict[str, Any]: Connection information including pool status and health warnings
            
        Example:
            >>> info = db.get_connection_info()
            >>> if info["warnings"]:
            ...     for warning in info["warnings"]:
            ...         print(f"Warning: {warning}")
        """
        if self._engine is None:
            return {"status": "not_initialized"}
        
        pool = self._engine.pool
        stats = {
            "status": "connected",
            "pool_size": pool.size(),
            "checked_in_connections": pool.checkedin(),
            "checked_out_connections": pool.checkedout(),
            "overflow_connections": pool.overflow(),
            "invalid_connections": pool.invalid(),
            "url": str(self._engine.url).replace(self._engine.url.password, "***") if self._engine.url.password else str(self._engine.url)
        }
        
        # Add health warnings
        stats["warnings"] = []
        
        # Check pool saturation
        if pool.checkedout() > pool.size() * 0.8:
            stats["warnings"].append("Connection pool near capacity (>80% utilized)")
            
        # Check overflow usage
        if pool.overflow() > 0:
            stats["warnings"].append(f"Using {pool.overflow()} overflow connections")
            
        # Check invalid connections
        if pool.invalid() > 0:
            stats["warnings"].append(f"Found {pool.invalid()} invalid connections")
            
        return stats

    def test_connection(self) -> bool:
        """
        Test if the database connection is working.
        
        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def create(self, table_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Insert a new record into the specified table with transaction support and data validation.

        Args:
            table_name (str): Table name.
            data (dict): Data to insert.

        Returns:
            Optional[Dict[str, Any]]: The inserted record as a dictionary.

        Raises:
            SQLAlchemyInsertError: If the insert operation fails
            ValueError: If the data validation fails

        Example:
            >>> db = PostgresDB()
            >>> user_data = {
            ...     'username': 'john_doe',
            ...     'email': 'john@example.com',
            ...     'is_active': True
            ... }
            >>> created_user = db.create('users', user_data)
            >>> print(created_user['id'])  # Access the created user's ID
        """
        try:
            table = self._get_table(table_name)
            
            # Validate data before insert
            self._validate_data(table, data)
            
            stmt = insert(table).values(**data).returning(table)
            
            with self.engine.begin() as conn:
                result = conn.execute(stmt)
                row = result.fetchone()
                
                # Convert Row object to dictionary
                if row:
                    return dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(row.keys(), row))
                return None
        except ValueError as e:
            raise ValueError(f"Data validation failed: {e}")
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager
            raise SQLAlchemyInsertError(f"Insert failed: {e}")

    def _build_aggregation(self, table: Table, col: str, agg_func: str):
        """Build an aggregation expression for a column."""
        agg_funcs = {
            'count': func.count,
            'sum': func.sum,
            'avg': func.avg,
            'min': func.min,
            'max': func.max
        }
        if agg_func in agg_funcs:
            return agg_funcs[agg_func](table.c[col]).label(f"{col}_{agg_func}")
        return None

    def _build_select_columns(self, table: Table, columns: Optional[List[str]] = None,
                            aggregations: Optional[Dict[str, str]] = None):
        """
        Build the select clause with columns and aggregations.
        
        Args:
            table: SQLAlchemy Table object
            columns: Optional list of column names to select
            aggregations: Optional dict mapping column names to aggregation functions
            
        Returns:
            List of SQLAlchemy column expressions or table object
        """
        select_columns = []
        
        # Add requested columns
        if columns:
            select_columns.extend(table.c[col] for col in columns if col in table.c)
            
        # Add aggregations
        if aggregations:
            for col, agg_func in aggregations.items():
                if col in table.c:
                    agg_expr = self._build_aggregation(table, col, agg_func)
                    if agg_expr is not None:
                        select_columns.append(agg_expr)
        
        # If no specific columns or aggregations, return the table itself (selects all columns)
        if not select_columns:
            return table
        
        return select_columns

    def _build_filter_condition(self, table: Table, col: str, op: str, value: Any):
        """
        Build a filter condition based on operator and value.
        
        Args:
            table: SQLAlchemy Table object
            col: Column name
            op: Operator type ('gt', 'lt', etc.)
            value: Value to compare against
            
        Returns:
            SQLAlchemy filter condition or None if invalid
        """
        operators = {
            'gt': lambda c, v: c > v,
            'lt': lambda c, v: c < v,
            'gte': lambda c, v: c >= v,
            'lte': lambda c, v: c <= v,
            'ne': lambda c, v: c != v,
            'in': lambda c, v: c.in_(v),
            'like': lambda c, v: c.like(v)
        }
        
        if op in operators and col in table.c:
            return operators[op](table.c[col], value)
        return None

    def _apply_conditions(self, stmt, table: Table, conditions: Dict[str, Any]):
        """
        Apply filter conditions to the statement.
        
        Args:
            stmt: SQLAlchemy select statement
            table: SQLAlchemy Table object
            conditions: Dictionary of filter conditions
            
        Returns:
            Updated SQLAlchemy select statement
        """
        if not conditions:
            return stmt
        
        for key, value in conditions.items():
            if '__' in key:
                col, op = key.split('__')
                condition = self._build_filter_condition(table, col, op, value)
                if condition is not None:
                    stmt = stmt.where(condition)
            elif key in table.c:
                stmt = stmt.where(table.c[key] == value)
        return stmt

    def _apply_grouping(self, stmt, table: Table, group_by: Optional[List[str]] = None):
        """Apply group by clause to the statement."""
        if group_by:
            group_cols = [table.c[col] for col in group_by if col in table.c]
            if group_cols:
                stmt = stmt.group_by(*group_cols)
        return stmt

    def _apply_ordering(self, stmt, table: Table, order_by: Optional[List[Tuple[str, bool]]] = None):
        """Apply order by clause to the statement."""
        if order_by:
            order_cols = []
            for col, is_asc in order_by:
                if col in table.c:
                    order_cols.append(table.c[col].asc() if is_asc else table.c[col].desc())
            if order_cols:
                stmt = stmt.order_by(*order_cols)
        return stmt

    def _apply_pagination(self, stmt, limit: Optional[int] = None, offset: int = 0):
        """Apply pagination to the statement."""
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset > 0:
            stmt = stmt.offset(offset)
        return stmt

    def read(self, table_name: str, conditions: Optional[Dict[str, Any]] = None, 
             columns: Optional[List[str]] = None,
             group_by: Optional[List[str]] = None,
             order_by: Optional[List[Tuple[str, bool]]] = None,
             aggregations: Optional[Dict[str, str]] = None,
             join: int = 0, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Read records from the specified table with advanced filtering and aggregation support.

        Args:
            table_name (str): Table name.
            conditions (dict, optional): Conditions for filtering with operators.
                Format: {'column': value} for equality or
                       {'column__op': value} where op can be:
                       - 'gt' for >
                       - 'lt' for <
                       - 'gte' for >=
                       - 'lte' for <=
                       - 'ne' for !=
                       - 'in' for IN
                       - 'like' for LIKE
            columns (List[str], optional): Specific columns to return
            group_by (List[str], optional): Columns to group by
            order_by (List[Tuple[str, bool]], optional): List of (column, is_asc) tuples
            aggregations (Dict[str, str], optional): Dict of column:func pairs
                Supported functions: 'count', 'sum', 'avg', 'min', 'max'
            join (int): Join control (0: no joins, 1: forward, -1: backward)
            limit (int, optional): Maximum records to return
            offset (int): Number of records to skip

        Returns:
            List[Dict[str, Any]]: List of records as dictionaries

        Examples:
            >>> db = PostgresDB()
            >>> # Get all users (no joins)
            >>> all_users = db.read('users')
            >>> 
            >>> # Get active users only (no joins)
            >>> active_users = db.read('users', {'is_active': True})
            >>> 
            >>> # Get users with pagination
            >>> paginated_users = db.read('users', limit=10, offset=20)
            >>> 
            >>> # Get users with forward joins (e.g., fetch user's profile data)
            >>> users_with_profiles = db.read('users', {'is_active': True}, join=1)
            >>> 
            >>> # Get users with backward joins (e.g., fetch users who have orders)
            >>> users_with_orders = db.read('users', None, join=-1)
            >>> 
            >>> # Get specific user by ID (no joins)
            >>> user = db.read('users', {'id': 123})
            >>> if user:
            ...     print(f"Found user: {user[0].username}")
        """
        try:
            # Get table with validation and caching
            table = self._get_table(table_name)
            
            # Build select statement with columns and aggregations
            select_columns = self._build_select_columns(table, columns, aggregations)
            
            # Create select statement - handle both list and table object
            if isinstance(select_columns, list):
                stmt = select(*select_columns)
            else:
                stmt = select(select_columns)
            
            # Apply filters, grouping and sorting
            stmt = self._apply_conditions(stmt, table, conditions or {})
            stmt = self._apply_grouping(stmt, table, group_by)
            stmt = self._apply_ordering(stmt, table, order_by)
            stmt = self._apply_pagination(stmt, limit, offset)
            
            # Execute query and return results as dictionaries
            with self.engine.connect() as conn:
                result = conn.execute(stmt)
                return [dict(row) for row in result.mappings()]
                
        except SQLAlchemyError as e:
            raise SQLAlchemyReadError(f"Read failed: {e}") from e

    def update(self, table_name: str, data: Dict[str, Any], conditions: Dict[str, Any]) -> List[Any]:
        """
        Update records in the specified table based on conditions with transaction support and data validation.

        Args:
            table_name (str): Table name.
            data (dict): Data to update.
            conditions (dict): Conditions for updating.

        Returns:
            List[Any]: List of updated records.

        Raises:
            SQLAlchemyUpdateError: If the update operation fails
            ValueError: If the data validation fails

        Examples:
            >>> db = PostgresDB()
            >>> # Update a specific user's email
            >>> updated_users = db.update(
            ...     'users',
            ...     {'email': 'newemail@example.com'},
            ...     {'id': 123}
            ... )
            >>> 
            >>> # Deactivate all users with a specific role
            >>> deactivated_users = db.update(
            ...     'users',
            ...     {'is_active': False},
            ...     {'role': 'temp_user'}
            ... )
            >>> print(f"Updated {len(deactivated_users)} users")
        """
        try:
            table = self._get_table(table_name)
            
            # Validate update data before proceeding
            self._validate_data(table, data)
            
            # Also validate condition columns (but not their values)
            for key in conditions.keys():
                if key not in table.columns:
                    raise ValueError(f"Invalid condition column: {key}")
            
            stmt = update(table).values(**data)
            for key, value in conditions.items():
                stmt = stmt.where(table.c[key] == value)
            stmt = stmt.returning(table)
            
            with self.engine.begin() as conn:
                result = conn.execute(stmt)
                return result.fetchall()
        except ValueError as e:
            raise ValueError(f"Data validation failed: {e}")
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager
            raise SQLAlchemyUpdateError(f"Update failed: {e}")

    def delete(self, table_name: str, conditions: Dict[str, Any]) -> int:
        """
        Delete records from the specified table based on conditions with transaction support.

        Args:
            table_name (str): Table name.
            conditions (dict): Conditions for deletion.

        Returns:
            int: Number of deleted records.

        Raises:
            SQLAlchemyDeleteError: If the delete operation fails.

        Examples:
            >>> db = PostgresDB()
            >>> # Delete a specific user
            >>> deleted_count = db.delete('users', {'id': 123})
            >>> print(f"Deleted {deleted_count} users")
            >>> 
            >>> # Delete all inactive users
            >>> deleted_count = db.delete('users', {'is_active': False})
            >>> print(f"Deleted {deleted_count} inactive users")
            >>> 
            >>> # Delete users by multiple conditions
            >>> deleted_count = db.delete('users', {
            ...     'role': 'temp_user',
            ...     'created_date': '2024-01-01'
            ... })
        """
        try:
            table = Table(table_name, self.metadata, autoload_with=self.engine)
            stmt = delete(table)
            for key, value in conditions.items():
                stmt = stmt.where(table.c[key] == value)
            
            with self.engine.begin() as conn:
                result = conn.execute(stmt)
                return result.rowcount
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager
            raise SQLAlchemyDeleteError(f"Delete failed: {e}")

    def truncate_and_reset_identity(self, table_name: str, cascade: bool = True) -> None:
        """
        Truncate the specified table and reset its identity/auto-increment counter with transaction support.

        Args:
            table_name (str): Table name to truncate.
            cascade (bool): Whether to cascade the truncation to dependent tables.
                          Default is True to handle foreign key constraints.

        Returns:
            None

        Raises:
            SQLAlchemyDeleteError: If the truncate operation fails.

        Examples:
            >>> db = PostgresDB()
            >>> # Truncate users table and reset ID counter (with cascade)
            >>> db.truncate_and_reset_identity('users')
            >>> 
            >>> # Truncate without cascade (will fail if foreign keys exist)
            >>> db.truncate_and_reset_identity('users', cascade=False)
            >>> 
            >>> # Truncate a lookup table safely
            >>> db.truncate_and_reset_identity('user_roles', cascade=True)
            >>> 
            >>> # After truncation, next insert will start with ID = 1
            >>> new_user = db.create('users', {'username': 'first_user'})
            >>> print(new_user.id)  # Will be 1
        """
        try:
            cascade_clause = "CASCADE" if cascade else "RESTRICT"
            sql_statement = f"TRUNCATE TABLE {table_name} RESTART IDENTITY {cascade_clause};"
            
            with self.engine.begin() as conn:
                conn.execute(text(sql_statement))
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager
            raise SQLAlchemyDeleteError(f"Truncate and reset identity failed for table '{table_name}': {e}")

    def execute_transaction(self, operations: List[callable]) -> List[Dict[str, Any]]:
        """
        Execute multiple operations in a single transaction with automatic rollback on failure.

        Args:
            operations (List[callable]): List of functions that take a connection as parameter.
                                       Each function should return a result or None.

        Returns:
            List[Dict[str, Any]]: List of results from each operation as dictionaries.

        Raises:
            SQLAlchemyTransactionError: If any operation in the transaction fails.
            
        Example:
            >>> db = PostgresDB()
            >>> # Define operations
            >>> def create_user(conn):
            ...     stmt = insert(users).values(username='john').returning(users)
            ...     return conn.execute(stmt)
            >>> def update_profile(conn):
            ...     stmt = update(profiles).where(profiles.c.user_id == 1)
            ...     return conn.execute(stmt)
            >>> # Execute in transaction
            >>> try:
            ...     results = db.execute_transaction([create_user, update_profile])
            ... except SQLAlchemyTransactionError as e:
            ...     print(f"Transaction failed: {e}")
            ...     # Both operations are rolled back

        Example:
            >>> db = PostgresDB()
            >>> def create_user(conn):
            ...     stmt = insert(users_table).values(username='john').returning(users_table)
            ...     return conn.execute(stmt).fetchone()
            >>> 
            >>> def update_profile(conn):
            ...     stmt = update(profiles_table).values(bio='Updated bio').where(profiles_table.c.user_id == 1)
            ...     return conn.execute(stmt).fetchall()
            >>> 
            >>> results = db.execute_transaction([create_user, update_profile])
        """
        try:
            results = []
            with self.engine.begin() as conn:
                for operation in operations:
                    result = operation(conn)
                    if result and hasattr(result, 'mappings'):
                        results.append([dict(row) for row in result.mappings()])
                    else:
                        results.append(result)
                return results
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager
            raise SQLAlchemyTransactionError(
                f"Transaction failed and was rolled back: {str(e)}"
            ) from e    
        
    def bulk_create(self, table_name: str, data_list: List[Dict[str, Any]], 
                batch_size: int = 1000) -> List[Dict[str, Any]]:
        """
        Insert multiple records in batches with optimized performance.

        Args:
            table_name (str): Table name.
            data_list (List[Dict[str, Any]]): List of dictionaries containing data to insert.
            batch_size (int): Number of records to insert in each batch.

        Returns:
            List[Dict[str, Any]]: List of inserted records as dictionaries.

        Raises:
            SQLAlchemyInsertError: If the bulk insert operation fails.

        Example:
            >>> db = PostgresDB()
            >>> users_data = [
            ...     {'username': 'user1', 'email': 'user1@example.com'},
            ...     {'username': 'user2', 'email': 'user2@example.com'},
            ...     {'username': 'user3', 'email': 'user3@example.com'}
            ... ]
            >>> created_users = db.bulk_create('users', users_data)
            >>> print(f"Created {len(created_users)} users")
        """
        if not data_list:
            return []

        try:
            table = self._get_table(table_name)
            all_results = []
            
            # Process in batches for better performance
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                with self.engine.begin() as conn:
                    stmt = insert(table).values(batch).returning(table)
                    result = conn.execute(stmt)
                    # Convert to dictionaries
                    all_results.extend([dict(row) for row in result.mappings()])
                    
            return all_results
            
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by context manager
            raise SQLAlchemyInsertError(f"Bulk insert failed: {e}") from e

    def execute_raw_sql(self, sql_query: str, parameters: Optional[Dict[str, Any]] = None, 
                       fetch_results: bool = True, use_transaction: bool = False) -> Optional[List[Any]]:
        """
        Execute a raw SQL query with optional parameters and transaction control.

        Args:
            sql_query (str): The raw SQL query to execute.
            parameters (dict, optional): Parameters to bind to the query for safety.
            fetch_results (bool): Whether to fetch and return results (default: True).
                                Set to False for INSERT/UPDATE/DELETE operations where you only need affected row count.
            use_transaction (bool): Whether to wrap the query in a transaction (default: False).
                                  Set to True for write operations that need rollback capability.

        Returns:
            Optional[List[Any]]: Query results if fetch_results=True, None otherwise.

        Raises:
            SQLAlchemyError: If the query execution fails.

        Examples:
            >>> db = PostgresDB()
            >>> 
            >>> # Simple SELECT query
            >>> results = db.execute_raw_sql("SELECT * FROM users WHERE is_active = :active", 
            ...                             {"active": True})
            >>> 
            >>> # Complex JOIN query
            >>> complex_query = '''
            ...     SELECT u.username, p.bio, r.role_name 
            ...     FROM users u 
            ...     LEFT JOIN profiles p ON u.id = p.user_id 
            ...     LEFT JOIN roles r ON u.role_id = r.id 
            ...     WHERE u.created_at > :date
            ... '''
            >>> users_with_details = db.execute_raw_sql(complex_query, {"date": "2024-01-01"})
            >>> 
            >>> # Aggregation query
            >>> count_query = "SELECT COUNT(*) as total_users FROM users WHERE is_active = :active"
            >>> user_count = db.execute_raw_sql(count_query, {"active": True})
            >>> print(f"Active users: {user_count[0].total_users}")
            >>> 
            >>> # Write operation with transaction
            >>> update_query = "UPDATE users SET last_login = NOW() WHERE id = :user_id"
            >>> db.execute_raw_sql(update_query, {"user_id": 123}, 
            ...                   fetch_results=False, use_transaction=True)
            >>> 
            >>> # Bulk update with transaction
            >>> bulk_update = '''
            ...     UPDATE users 
            ...     SET is_active = false 
            ...     WHERE last_login < :cutoff_date
            ... '''
            >>> db.execute_raw_sql(bulk_update, {"cutoff_date": "2023-01-01"}, 
            ...                   fetch_results=False, use_transaction=True)
            >>> 
            >>> # Complex analytical query
            >>> analytics_query = '''
            ...     SELECT 
            ...         DATE_TRUNC('month', created_at) as month,
            ...         COUNT(*) as new_users,
            ...         COUNT(CASE WHEN is_active THEN 1 END) as active_users
            ...     FROM users 
            ...     WHERE created_at >= :start_date
            ...     GROUP BY DATE_TRUNC('month', created_at)
            ...     ORDER BY month DESC
            ... '''
            >>> monthly_stats = db.execute_raw_sql(analytics_query, {"start_date": "2024-01-01"})
        """
        try:
            # Convert parameters dict to SQLAlchemy text parameters if provided
            stmt = text(sql_query)
            
            if use_transaction:
                # Use transaction for write operations
                with self.engine.begin() as conn:
                    if parameters:
                        result = conn.execute(stmt, parameters)
                    else:
                        result = conn.execute(stmt)
                    
                    if fetch_results:
                        return result.fetchall()
                    else:
                        return None
            else:
                # Use regular connection for read operations
                with self.engine.connect() as conn:
                    if parameters:
                        result = conn.execute(stmt, parameters)
                    else:
                        result = conn.execute(stmt)
                    
                    if fetch_results:
                        return result.fetchall()
                    else:
                        return None
                        
        except SQLAlchemyError as e:
            # Transaction automatically rolled back by the context manager if use_transaction=True
            raise SQLAlchemyError(f"Raw SQL execution failed: {e}")

    def cleanup_stale_connections(self) -> None:
        """
        Clean up stale connections in the pool that have been idle for too long.
        
        This method will:
        1. Identify connections that have been idle for over 1 hour
        2. Terminate those connections safely
        3. Log the cleanup activity
        
        Example:
            >>> db = PostgresDB()
            >>> db.cleanup_stale_connections()  # Run during low-traffic periods
        """
        try:
            if self._engine:
                with self._engine.connect() as conn:
                    result = conn.execute(text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND state = 'idle' "
                        "AND state_change < NOW() - INTERVAL '1 hour'"
                    ))
                    terminated = result.rowcount
                    if terminated > 0:
                        logger.info(f"Cleaned up {terminated} stale connections")
        except SQLAlchemyError as e:
            logger.error(f"Failed to cleanup stale connections: {e}")

    def close(self) -> None:
        """
        Close the singleton database connection.
        
        Note: In singleton mode, this will close the connection for all instances.
        Use with caution as it affects the entire application.
        """
        if self._engine:
            logger.info("Closing PostgresDB singleton connection")
            self._engine.dispose()
            self._engine = None
            self._metadata = None
            with self._lock:
                self._connection_initialized = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - connection is persistent, so no automatic close."""
        # In singleton mode, we don't automatically close the connection
        # as it's shared across the entire application
        pass


# Convenience function to get the singleton instance
def get_session() -> PostgresDB:
    """
    Get the singleton PostgresDB instance.
    
    This function provides a convenient way to get the shared database
    connection instance without needing to instantiate the class.
    
    Returns:
        PostgresDB: The singleton PostgresDB instance
        
    Example:
        >>> db = get_session()
        >>> users = db.read('users')
        >>> # Connection is automatically shared across all get_session() calls
    """
    return PostgresDB()


# Global instance management
def close_global_connection() -> None:
    """
    Close the global singleton database connection.
    
    This function should be called at application shutdown to properly
    close the database connection and clean up resources.
    
    Example:
        >>> # At application startup
        >>> db = PostgresDB()
        >>> 
        >>> # ... application runs ...
        >>> 
        >>> # At application shutdown
        >>> close_global_connection()
    """
    if PostgresDB._instance:
        PostgresDB._instance.close()


    def read_in_chunks(self, table_name: str, conditions: Optional[Dict[str, Any]] = None,
                      chunk_size: int = 1000) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Read large result sets in chunks to prevent memory issues.
        
        Args:
            table_name (str): Name of the table to read from
            conditions (Dict[str, Any], optional): Filter conditions
            chunk_size (int): Number of records per chunk
            
        Yields:
            List[Dict[str, Any]]: Chunks of records
            
        Example:
            >>> db = PostgresDB()
            >>> for chunk in db.read_in_chunks('large_table', chunk_size=5000):
            ...     process_chunk(chunk)
        """
        offset = 0
        while True:
            chunk = self.read(table_name, conditions, limit=chunk_size, offset=offset)
            if not chunk:
                break
            yield chunk
            offset += chunk_size
