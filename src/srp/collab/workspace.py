"""Collaborative workspace management.

This module provides basic structures for managing a collaborative
review workspace.  Each workspace maintains a list of users and
supports assignment of papers to reviewers, detection of conflicts
between screening decisions and resolution of those conflicts.  This
enables multiple reviewers to work together on a systematic review
while ensuring transparency and accountability.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

from ..utils.logging import get_logger

logger = get_logger(__name__)


class UserRole(str, Enum):
    """Possible roles a user can have in a workspace."""

    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class WorkspaceUser(BaseModel):
    """Representation of a user who is part of a workspace."""

    user_id: str
    email: str
    name: str
    role: UserRole
    joined_at: datetime
    last_active: Optional[datetime] = None


class ConflictResolution(BaseModel):
    """Record describing a conflict between two reviewers."""

    paper_id: str
    reviewer1_id: str
    reviewer1_decision: str
    reviewer2_id: str
    reviewer2_decision: str
    resolved: bool = False
    final_decision: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class Workspace:
    """Container for managing collaborative reviews."""

    def __init__(self, workspace_id: str, name: str, owner_id: str) -> None:
        self.workspace_id = workspace_id
        self.name = name
        self.owner_id = owner_id
        self.users: List[WorkspaceUser] = []
        self.created_at = datetime.utcnow()

    def add_user(self, user: WorkspaceUser) -> None:
        """Add a user to the workspace."""
        self.users.append(user)
        logger.info(f"Added user {user.email} to workspace {self.workspace_id}")

    def assign_papers(
        self,
        paper_ids: List[str],
        reviewer_ids: List[str],
        strategy: str = "round_robin",
    ) -> Dict[str, List[str]]:
        """Assign a list of papers to reviewers using a simple strategy."""
        assignments: Dict[str, List[str]] = {rid: [] for rid in reviewer_ids}
        if not reviewer_ids:
            return assignments
        if strategy == "round_robin":
            for i, paper_id in enumerate(paper_ids):
                reviewer_id = reviewer_ids[i % len(reviewer_ids)]
                assignments[reviewer_id].append(paper_id)
        elif strategy == "dual_review":
            for paper_id in paper_ids:
                for rid in reviewer_ids[:2]:
                    assignments[rid].append(paper_id)
        return assignments

    def detect_conflicts(self, screening_results: List) -> List[ConflictResolution]:
        """Detect conflicts in decisions between reviewers for the same paper."""
        by_paper: Dict[str, List] = {}
        for result in screening_results:
            by_paper.setdefault(result.paper_id, []).append(result)
        conflicts: List[ConflictResolution] = []
        for paper_id, results in by_paper.items():
            if len(results) >= 2:
                decisions = {r.decision for r in results}
                if len(decisions) > 1:
                    conflicts.append(
                        ConflictResolution(
                            paper_id=paper_id,
                            reviewer1_id=results[0].reviewed_by or "unknown",
                            reviewer1_decision=str(results[0].decision),
                            reviewer2_id=results[1].reviewed_by or "unknown",
                            reviewer2_decision=str(results[1].decision),
                        )
                    )
        return conflicts