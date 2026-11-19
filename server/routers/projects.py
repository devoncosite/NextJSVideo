"""Projects API Router (TASK-1.3 & Phase 6/7 Support)."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.database import get_db
from server.core.patch_engine import apply_json_patches
from server.models.project import Project, ProjectStatus
from server.routers.context import DEFAULT_USER_ID, ensure_default_user_exists
from server.schemas.manifest import ProjectFormat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    format: ProjectFormat = "cinematic_drama"
    aspect_ratio: str = Field(default="16:9")
    visual_style_prompt: str = Field(default="Cinematic 35mm film aesthetic")


class ProjectPatchRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    patches: Optional[List[Dict[str, Any]]] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Any
    title: str
    description: Optional[str]
    status: ProjectStatus
    format: str
    version: int
    manifest: Optional[Dict[str, Any]]
    created_at: Any
    updated_at: Any


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Create a new CineForge project with a blank initial manifest structure."""
    user = await ensure_default_user_exists(db)

    project_id = str(uuid.uuid4())
    format_val = req.format if isinstance(req.format, str) else req.format.value
    default_manifest = {
        "projectId": project_id,
        "version": 1,
        "title": req.title,
        "format": format_val,
        "contextArtifactIds": [],
        "globalStyle": {
            "aspectRatio": req.aspect_ratio,
            "resolution": "1080p",
            "visualStylePrompt": req.visual_style_prompt,
            "colorGradingPreset": "cinematic_teal_orange",
        },
        "consistencies": {
            "characters": [],
            "objects": [],
        },
        "scenes": [],
        "outroEndFrame": {
            "prompt": "Closing cinematic logo and fade to black",
            "status": "idle",
            "variants": [],
        },
        "assembly": {
            "transitionType": "cut",
            "transitionDurationSec": 0.5,
            "burnCaptions": True,
            "subtitleStyle": "subtitles_classic",
            "thumbnail": {
                "prompt": f"Dramatic movie poster thumbnail for {req.title}",
                "status": "idle",
                "variants": [],
            },
            "status": "idle",
            "progressPercent": 0,
        },
    }

    project = Project(
        id=project_id,
        user_id=user.id,
        title=req.title,
        description=req.description,
        status=ProjectStatus.DRAFT,
        format=format_val,
        version=1,
        manifest=default_manifest,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[Project]:
    """List all projects ordered by creation date descending."""
    stmt = select(Project).order_by(desc(Project.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Retrieve complete project details and Master JSON manifest."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: str,
    req: ProjectPatchRequest,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Apply metadata updates or RFC 6902 JSON Patch operations to the project manifest."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    if req.title is not None:
        project.title = req.title
    if req.description is not None:
        project.description = req.description
    if req.status is not None:
        project.status = req.status

    if req.patches:
        manifest = project.manifest or {}
        updated_manifest = apply_json_patches(manifest, req.patches)
        project.manifest = updated_manifest
        project.version += 1

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project and cascade deletion to related jobs and artifacts."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    await db.delete(project)
    await db.commit()
