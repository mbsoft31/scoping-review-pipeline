# Collaboration Module

The **collab** module provides basic constructs to support multi‑user collaboration during the screening and review process.  While the current implementation is lightweight, it lays the groundwork for more sophisticated role management and conflict resolution.

## Workspace

[`workspace.py`](../../src/srp/collab/workspace.py) defines the `Workspace` class and related data models:

- **`UserRole`**: Enum of user roles (`OWNER`, `ADMIN`, `REVIEWER`, `VIEWER`).  Roles determine permissions within the workspace.
- **`WorkspaceUser`**: Records user metadata (ID, email, name, role) and timestamps for when the user joined and last acted.
- **`ConflictResolution`**: Captures disagreements between two reviewers on the same paper.  It records the conflicting decisions and tracks whether the conflict has been resolved.
- **`Workspace`**: Represents a collaborative environment where multiple users can work on a set of papers.  Key features include:
  - Maintaining a list of users and their roles.
  - Assigning papers to reviewers using strategies like round robin or dual review (`assign_papers()`).  Dual review assigns each paper to two reviewers to facilitate conflict detection.
  - Detecting conflicts via `detect_conflicts()`, which scans screening results and returns a list of `ConflictResolution` objects where reviewers disagree.
  - Providing a log of assignments and activities (planned for future extension).

## Use cases

Although the pipeline currently uses the `HITLReviewer` for human‑in‑the‑loop screening, you can integrate the `Workspace` class into bespoke review interfaces.  For example, you could assign papers evenly among multiple reviewers, then compare their decisions and surface conflicts for resolution.  The module is designed to be extensible as collaboration features mature.