"""
Custom exceptions for date/time operations.
"""


class DateConversionError(Exception):
    """Exception raised when date conversion fails."""
    
    def __init__(self, message: str = "Failed to convert date/time"):
        self.message = message
        super().__init__(self.message)


class InvalidDateFormatError(Exception):
    """Exception raised when date format is invalid."""
    
    def __init__(self, message: str = "Invalid date format"):
        self.message = message
        super().__init__(self.message)
