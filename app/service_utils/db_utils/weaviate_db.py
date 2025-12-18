"""
Weaviate vector database connection and collection management class.

Implements a singleton pattern for shared persistent connections to Weaviate.
Provides methods for connection management, collection existence checks, and collection creation.
"""
import threading
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.exceptions import WeaviateBaseError, WeaviateConnectionError

from service_utils.db_utils.conf.weaviate_conf import WEAVIATE_URL
from service_utils.log_management import get_logger

# Set up logging
logger = get_logger(__name__)


class WeaviateDB:
    """
    Handles persistent Weaviate connection and provides collection management operations.
    
    This class implements a singleton pattern to ensure a single shared database connection
    across all database functions in the system. The connection is thread-safe and persistent.

    Singleton Features:
        - Single shared database connection across the entire application
        - Thread-safe initialization and access
        - Automatic connection recovery on failures
        - Lazy initialization - connection created only when first accessed

    Examples:
        >>> # Get the singleton instance (creates connection on first call)
        >>> weaviate_db = WeaviateDB()
        >>> 
        >>> # Check if collection exists
        >>> exists = weaviate_db.collection_exists("MyCollection")
        >>> 
        >>> # Create collection if it doesn't exist
        >>> collection = weaviate_db.create_collection(
        ...     name="MyCollection",
        ...     properties=[
        ...         {"name": "title", "data_type": "text"},
        ...         {"name": "content", "data_type": "text"}
        ...     ]
        ... )
        >>> 
        >>> # Connection is automatically managed
    """

    _instance = None
    _lock = threading.Lock()
    _client = None
    _connection_initialized = False

    def __new__(cls):
        """
        Implement singleton pattern with thread-safe initialization.
        
        Returns:
            WeaviateDB: The singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super(WeaviateDB, cls).__new__(cls)
                    cls._instance._initialize_connection()
        return cls._instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _initialize_connection(self):
        """
        Initialize the Weaviate client connection with retry logic.
        
        Raises:
            WeaviateException: If connection fails after retries
        """
        if not self._connection_initialized:
            try:
                logger.info(f"Initializing Weaviate connection to {WEAVIATE_URL}")
                
                # Connect to local Weaviate instance
                self._client = weaviate.connect_to_local()
                
                # Check if connection is ready
                if self._client.is_ready():
                    self._connection_initialized = True
                    logger.info("Weaviate connection established successfully")
                else:
                    raise WeaviateConnectionError("Weaviate client is not ready")
                    
            except Exception as e:
                logger.error(f"Failed to initialize Weaviate connection: {e}")
                raise WeaviateConnectionError(f"Weaviate connection failed: {e}")

    @property
    def client(self):
        """
        Get the Weaviate client instance.
        
        Returns:
            weaviate.Client: The Weaviate client
            
        Raises:
            WeaviateConnectionError: If client is not initialized
        """
        if not self._connection_initialized or self._client is None:
            raise WeaviateConnectionError("Weaviate client not initialized")
        return self._client

    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if a collection exists in Weaviate.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            bool: True if collection exists, False otherwise
            
        Examples:
            >>> weaviate_db = WeaviateDB()
            >>> if weaviate_db.collection_exists("Articles"):
            ...     print("Collection exists")
        """
        try:
            result = self.client.collections.exists(collection_name)
            return result
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False

    def create_collection(
        self,
        name: str,
        properties: Optional[List[Dict[str, Any]]] = None,
        vectorizer: Optional[str] = "none",
        description: Optional[str] = None
    ) -> Any:
        """
        Create a new collection in Weaviate if it doesn't exist.
        
        Args:
            name: Name of the collection
            properties: List of property definitions. Each dict should have:
                - name (str): Property name
                - data_type (str): Data type (text, number, int, boolean, date, etc.)
                - description (str, optional): Property description
            vectorizer: Vectorizer to use (default: "none" for custom vectors)
            description: Collection description
            
        Returns:
            Collection object if created/exists, None on failure
            
        Raises:
            WeaviateBaseError: If collection creation fails
            
        Examples:
            >>> weaviate_db = WeaviateDB()
            >>> collection = weaviate_db.create_collection(
            ...     name="Articles",
            ...     description="News articles collection",
            ...     properties=[
            ...         {
            ...             "name": "title",
            ...             "data_type": "text",
            ...             "description": "Article title"
            ...         },
            ...         {
            ...             "name": "content",
            ...             "data_type": "text",
            ...             "description": "Article content"
            ...         },
            ...         {
            ...             "name": "author",
            ...             "data_type": "text"
            ...         },
            ...         {
            ...             "name": "published_date",
            ...             "data_type": "date"
            ...         }
            ...     ],
            ...     vectorizer="text2vec-transformers"
            ... )
        """
        try:
            # Check if collection already exists
            if self.collection_exists(name):
                logger.info(f"Collection '{name}' already exists")
                return self.client.collections.get(name)
            
            # Prepare properties
            property_list = []
            if properties:
                for prop in properties:
                    prop_name = prop.get("name")
                    prop_data_type = prop.get("data_type", "text").upper()
                    prop_description = prop.get("description", "")
                    
                    # Map string data types to DataType enums
                    data_type_mapping = {
                        "TEXT": DataType.TEXT,
                        "NUMBER": DataType.NUMBER,
                        "INT": DataType.INT,
                        "BOOLEAN": DataType.BOOL,
                        "DATE": DataType.DATE,
                        "UUID": DataType.UUID,
                        "OBJECT": DataType.OBJECT,
                    }
                    
                    dt = data_type_mapping.get(prop_data_type, DataType.TEXT)
                    
                    property_list.append(
                        Property(
                            name=prop_name,
                            data_type=dt,
                            description=prop_description
                        )
                    )
            
            # Configure vectorizer
            vectorizer_config = None
            if vectorizer and vectorizer != "none":
                vectorizer_config = Configure.Vectorizer.text2vec_transformers()
            
            # Create collection
            collection = self.client.collections.create(
                name=name,
                description=description,
                properties=property_list,
                vectorizer_config=vectorizer_config
            )
            
            logger.info(f"Collection '{name}' created successfully")
            return collection
            
        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            raise WeaviateBaseError(f"Collection creation failed: {e}")

    def get_collection(self, name: str) -> Any:
        """
        Get an existing collection by name.
        
        Args:
            name: Name of the collection
            
        Returns:
            Collection object if exists, None otherwise
            
        Examples:
            >>> weaviate_db = WeaviateDB()
            >>> collection = weaviate_db.get_collection("Articles")
        """
        try:
            exists = self.client.collections.exists(name)
            if exists:
                return self.client.collections.get(name)
            else:
                logger.warning(f"Collection '{name}' does not exist")
                return None
        except Exception as e:
            logger.error(f"Error getting collection '{name}': {e}")
            return None

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection from Weaviate.
        
        Args:
            name: Name of the collection to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
            
        Examples:
            >>> weaviate_db = WeaviateDB()
            >>> success = weaviate_db.delete_collection("OldCollection")
        """
        try:
            exists = self.client.collections.exists(name)
            if exists:
                self.client.collections.delete(name)
                logger.info(f"Collection '{name}' deleted successfully")
                return True
            else:
                logger.warning(f"Collection '{name}' does not exist")
                return False
        except Exception as e:
            logger.error(f"Failed to delete collection '{name}': {e}")
            return False

    def close(self):
        """
        Close the Weaviate connection and reset instance for reconnection.
        
        Examples:
            >>> weaviate_db = WeaviateDB()
            >>> weaviate_db.close()
        """
        if self._client:
            try:
                self._client.close()
                WeaviateDB._connection_initialized = False
                WeaviateDB._client = None
                logger.info("Weaviate connection closed")
            except Exception as e:
                logger.error(f"Error closing Weaviate connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
