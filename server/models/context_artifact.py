"""ContextArtifact Relational Entity (TASK-1.2)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models.base import Base, JSONBType, utc_now

if TYPE_CHECKING:
    from server.models.project import Project


class ContextSourceType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    HTML = "html"
    URL = "url"
    VIDEO = "video"
    AUDIO = "audio"


def generate_context_id() -> str:
    return f"ctx_{uuid.uuid4().hex[:8]}"


class ContextArtifact(Base):
    """Content-addressed multimodal ingestion artifact cached via SHA-256."""

    __tablename__ = "context_artifacts"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_context_id,
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    source_type: Mapped[ContextSourceType] = mapped_column(
        Enum(ContextSourceType, name="context_source_type_enum", native_enum=False),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    extracted_markdown: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    summary_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONBType,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="context_artifacts",
    )
