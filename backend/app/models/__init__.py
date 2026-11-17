"""Model registry.

Importing this package registers every model on `Base.metadata`, which Alembic needs
for autogenerate. Add new models here.
"""

from app.models.run import Change, ProcessedMessage, Run, RunKind, RunStatus, Snapshot
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus

__all__ = [
    "Change",
    "ProcessedMessage",
    "Run",
    "RunKind",
    "RunStatus",
    "Snapshot",
    "User",
    "Workspace",
    "WorkspaceStatus",
]
