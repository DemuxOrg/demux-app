"""Model registry.

Importing this package registers every model on `Base.metadata`, which Alembic needs
for autogenerate. Add new models here.
"""

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus

__all__ = ["User", "Workspace", "WorkspaceStatus"]
