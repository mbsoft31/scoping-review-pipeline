"""Collaborative workspace management.

This package defines classes and utilities for managing multi‑user
workspaces.  A workspace can track users, assign papers to
reviewers, detect conflicts between decisions and store audit logs.
These features enable team‑based systematic reviews.
"""

from .workspace import Workspace, WorkspaceUser, UserRole, ConflictResolution  # noqa: F401