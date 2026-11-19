"""JobQueueRecord Relational Entity (TASK-1.2)."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from server.models.project import Project


class JobStage(str, enum.Enum):
    PLANNER = "planner"
    CONSISTENCIES = "consistencies"
    KEYFRAMES = "keyframes"
    AUDIO = "audio"
    VIDEO = "video"
    ASSEMBLY = "assembly"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobQueueRecord(Base, TimestampMixin):
    """Persistent execution record for ARQ distributed background tasks."""

    __tablename__ = "job_queue_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage: Mapped[JobStage] = mapped_column(
        Enum(JobStage, name="job_stage_enum", native_enum=False),
        nullable=False,
    )
    target_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    arq_job_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum", native_enum=False),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="jobs",
    )
