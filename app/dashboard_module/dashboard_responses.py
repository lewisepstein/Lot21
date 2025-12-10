from pydantic import BaseModel


class DashboardResponse(BaseModel):
    """
    Response model for dashboard data.
    
    Attributes:
        message (str): Welcome or informational message for the dashboard.
        user (dict): Dictionary containing authenticated user information.
        timestamp (str): ISO format timestamp of when the response was generated.
        data (dict): Dictionary containing dashboard-specific data and metrics.
    """
    message: str
    user: dict
    timestamp: str
    data: dict
