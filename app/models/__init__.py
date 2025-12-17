# Import all models so alembic can detect them
from models.base import Base
from models.users import User
from models.categories import Category
from models.pages import Page
from models.schedulers import Scheduler
from models.tasks import Task
from models.task_runs import TaskRun, TaskProcess
from models.prompt_history import PromptHistory
from models.content import Content
from models.weaviate_data import WeaviateData

__all__ = [
    "Base",
    "User",
    "Category",
    "Page",
    "Scheduler",
    "Task",
    "TaskRun",
    "Content",
    "PromptHistory",
    "TaskProcess",
    "WeaviateData",
]
