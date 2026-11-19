"""Project Relational Entity & JSONB Manifest Model (TASK-1.2)."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, List

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models.base import Base, JSONBType, TimestampMixin

if TYPE_CHECKING:
    from server.models.context_artifact import ContextArtifact
    from server.models.job import JobQueueRecord
    from server.models.user import User


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


def generate_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:8]}"


class Project(Base, TimestampMixin):
    """Core video production project housing the transactional JSONB MasterManifest."""

    __tablename__ = "projects"
    __table_args__ = (
        Index(
            "idx_projects_manifest_gin",
            "manifest",
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_project_id,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="cinematic_drama",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    manifest: Mapped[Dict[str, Any]] = mapped_column(
        JSONBType,
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status_enum", native_enum=False),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="projects",
    )
    context_artifacts: Mapped[List["ContextArtifact"]] = relationship(
        "ContextArtifact",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    jobs: Mapped[List["JobQueueRecord"]] = relationship(
        "JobQueueRecord",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
