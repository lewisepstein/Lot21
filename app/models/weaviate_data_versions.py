from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, func, ForeignKey
from models.base import Base


class WeaviateDataVersion(Base):
    """
    WeaviateDataVersion model for tracking version history of weaviate_data records.
    
    This model implements version control using JSON diff technique to track changes
    made to training data records. Each update to a weaviate_data record creates a new
    version entry with the differences between old and new values.
    
    Attributes:
        id (int): Primary key, unique identifier for each version record.
        weaviate_data_id (int): Foreign key to the weaviate_data record being versioned.
        version_number (int): Sequential version number for the record (1, 2, 3, ...).
        changed_by (int): Foreign key to the user who made the changes.
        changed_at (datetime): Timestamp when the change was made.
        change_description (str): Optional description of what was changed.
        old_values (json): JSON object containing the previous values of changed fields.
        new_values (json): JSON object containing the new values of changed fields.
        diff (json): JSON object containing the structured diff between old and new values.
        operation (str): Type of operation ('UPDATE', 'DELETE', 'RESTORE').
    """
    __tablename__ = "weaviate_data_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    weaviate_data_id = Column(Integer, ForeignKey('weaviate_data.id'), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    changed_by = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    change_description = Column(Text, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    diff = Column(JSON, nullable=True)
    operation = Column(String(50), nullable=False, default='UPDATE')  # UPDATE, DELETE, RESTORE
    
    def __repr__(self):
        return f"<WeaviateDataVersion(id={self.id}, weaviate_data_id={self.weaviate_data_id}, version={self.version_number}, operation='{self.operation}')>"
    
    def to_dict(self):
        """Convert WeaviateDataVersion object to dictionary."""
        return {
            "id": self.id,
            "weaviate_data_id": self.weaviate_data_id,
            "version_number": self.version_number,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "change_description": self.change_description,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "diff": self.diff,
            "operation": self.operation
        }
    
    @staticmethod
    def create_diff(old_data, new_data):
        """
        Create a JSON diff between old and new data.
        
        Args:
            old_data (dict): Dictionary containing old values
            new_data (dict): Dictionary containing new values
            
        Returns:
            dict: Structured diff showing added, modified, and removed fields
        """
        diff = {
            "added": {},
            "modified": {},
            "removed": {}
        }
        
        # Find modified and removed fields
        for key, old_value in old_data.items():
            if key not in new_data:
                diff["removed"][key] = old_value
            elif old_value != new_data[key]:
                diff["modified"][key] = {
                    "old": old_value,
                    "new": new_data[key]
                }
        
        # Find added fields
        for key, new_value in new_data.items():
            if key not in old_data:
                diff["added"][key] = new_value
        
        return diff
    
    @staticmethod
    def get_changed_fields(diff):
        """
        Extract list of changed field names from diff.
        
        Args:
            diff (dict): Diff object created by create_diff
            
        Returns:
            list: List of field names that were changed
        """
        changed_fields = []
        changed_fields.extend(diff.get("added", {}).keys())
        changed_fields.extend(diff.get("modified", {}).keys())
        changed_fields.extend(diff.get("removed", {}).keys())
        return changed_fields
    
    @staticmethod
    def has_changes(diff):
        """
        Check if diff contains any changes.
        
        Args:
            diff (dict): Diff object created by create_diff
            
        Returns:
            bool: True if there are any changes, False otherwise
        """
        return bool(diff.get("added") or diff.get("modified") or diff.get("removed"))
