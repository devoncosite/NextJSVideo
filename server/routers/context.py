"""FastAPI Context Ingestion Router (TASK-3.1, TASK-3.2, TASK-3.3, TASK-3.4, TASK-3.5)."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.core.database import get_db_session
from server.core.ingestion.doc_parser import DocumentParser
from server.core.ingestion.hasher import StreamingHasher, compute_sha256_bytes
from server.core.ingestion.media_ingester import MediaIngester
from server.core.ingestion.summarizer import ContextSummarizer
from server.core.ingestion.web_crawler import SSRFValidationError, WebCrawler
from server.core.storage import StorageService
from server.models.context_artifact import ContextArtifact, ContextSourceType
from server.models.project import Project, ProjectStatus
from server.models.user import User

router = APIRouter(prefix="/api/v1", tags=["context"])

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_storage_service() -> StorageService:
    """FastAPI dependency providing configured StorageService instance."""
    return StorageService()


async def ensure_default_user_exists(db: AsyncSession) -> User:
    """Ensure a default user exists in database for headless/auth-skipped operations."""
    stmt = select(User).where(User.id == DEFAULT_USER_ID)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            id=DEFAULT_USER_ID,
            email="creator@cineforge.ai",
            hashed_password="guest_session_unauthenticated",
            name="CineForge Director",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_or_create_project(project_id: str, db: AsyncSession) -> Project:
    """Retrieve existing project or initialize a default project instance."""
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        user = await ensure_default_user_exists(db)
        empty_manifest = {
            "projectId": project_id,
            "version": 1,
            "title": f"Project {project_id}",
            "format": "cinematic_drama",
            "contextArtifactIds": [],
            "globalStyle": {
                "aspectRatio": "16:9",
                "resolution": "1080p",
                "visualStylePrompt": "Cinematic 35mm film",
            },
            "consistencies": {"characters": [], "objects": []},
            "scenes": [],
            "assembly": {"status": "idle", "burnCaptions": True},
        }
        project = Project(
            id=project_id,
            user_id=user.id,
            title=f"Project {project_id}",
            format="cinematic_drama",
            version=1,
            manifest=empty_manifest,
            status=ProjectStatus.DRAFT,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

    return project


class IngestUrlRequest(BaseModel):
    url: str


class ContextArtifactResponse(BaseModel):
    id: str
    project_id: str
    content_hash: str
    source_type: str
    original_filename: str
    storage_path: str
    extracted_markdown: Optional[str]
    summary_json: Optional[Dict[str, Any]]
    cached: bool = False


@router.post("/projects/{project_id}/context/upload", response_model=ContextArtifactResponse)
async def upload_context_document(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage_service),
) -> ContextArtifactResponse:
    """Upload document, calculate streaming SHA-256, deduplicate, parse markdown, and summarize."""
    project = await get_or_create_project(project_id, db)

    # 1. Stream file chunks and calculate SHA-256 on the fly
    hasher = StreamingHasher()
    file_bytes_list: List[bytes] = []

    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        file_bytes_list.append(chunk)

    all_bytes = b"".join(file_bytes_list)
    sha256_hex = hasher.hexdigest
    filename = file.filename or "uploaded_document"
    ext = Path(filename).suffix.lstrip(".").lower() or "bin"

    # 2. Check for existing content_hash (deduplication)
    stmt = select(ContextArtifact).where(ContextArtifact.content_hash == sha256_hex)
    existing_result = await db.execute(stmt)
    existing_artifact = existing_result.scalars().first()

    if existing_artifact is not None:
        # Link artifact to project manifest if not already present
        manifest = dict(project.manifest)
        artifact_ids: List[str] = manifest.get("contextArtifactIds", [])
        if existing_artifact.id not in artifact_ids:
            artifact_ids.append(existing_artifact.id)
            manifest["contextArtifactIds"] = artifact_ids
            project.manifest = manifest
            await db.commit()

        return ContextArtifactResponse(
            id=existing_artifact.id,
            project_id=project_id,
            content_hash=existing_artifact.content_hash,
            source_type=str(existing_artifact.source_type.value),
            original_filename=existing_artifact.original_filename,
            storage_path=existing_artifact.storage_path,
            extracted_markdown=existing_artifact.extracted_markdown,
            summary_json=existing_artifact.summary_json,
            cached=True,
        )

    # 3. Determine source type
    source_type = ContextSourceType.PDF
    if ext in ("docx", "doc"):
        source_type = ContextSourceType.DOCX
    elif ext in ("pptx", "ppt"):
        source_type = ContextSourceType.PPTX
    elif ext in ("html", "htm"):
        source_type = ContextSourceType.HTML
    elif ext in ("mp4", "mov", "webm"):
        source_type = ContextSourceType.VIDEO
    elif ext in ("mp3", "wav", "m4a"):
        source_type = ContextSourceType.AUDIO

    # 4. Save raw file to S3
    persist_res = await storage.upload_bytes(
        data=all_bytes,
        project_id=project_id,
        subfolder="raw_context",
        extension=ext,
        sha256_hex=sha256_hex,
    )

    # 5. Extract Markdown text
    extracted_md = ""
    if source_type in (ContextSourceType.VIDEO, ContextSourceType.AUDIO):
        ingester = MediaIngester()
        # For audio/video upload, perform quick transcript extraction
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=True) as tmp_media:
            tmp_media.write(all_bytes)
            tmp_media.flush()
            segments = ingester.transcribe_audio(Path(tmp_media.name))
            extracted_md = ingester.build_markdown_summary(
                title=filename,
                duration_sec=segments[-1].end if segments else 0.0,
                keyframes=[],
                segments=segments,
            )
    else:
        parser = DocumentParser()
        extracted_md = parser.parse_bytes(all_bytes, filename=filename, source_type=source_type)

    # 6. Generate Multimodal Summary
    summarizer = ContextSummarizer()
    summary = await summarizer.summarize_context(extracted_md, title=filename)
    summary_dict = summary.model_dump()

    # 7. Persist ContextArtifact and link to manifest
    artifact = ContextArtifact(
        project_id=project_id,
        content_hash=sha256_hex,
        source_type=source_type,
        original_filename=filename,
        storage_path=persist_res.s3_key,
        extracted_markdown=extracted_md,
        summary_json=summary_dict,
    )
    db.add(artifact)
    await db.flush()

    manifest = dict(project.manifest)
    artifact_ids = manifest.get("contextArtifactIds", [])
    if artifact.id not in artifact_ids:
        artifact_ids.append(artifact.id)
        manifest["contextArtifactIds"] = artifact_ids
        project.manifest = manifest

    await db.commit()
    await db.refresh(artifact)

    return ContextArtifactResponse(
        id=artifact.id,
        project_id=project_id,
        content_hash=artifact.content_hash,
        source_type=str(artifact.source_type.value),
        original_filename=artifact.original_filename,
        storage_path=artifact.storage_path,
        extracted_markdown=artifact.extracted_markdown,
        summary_json=artifact.summary_json,
        cached=False,
    )


@router.post("/projects/{project_id}/context/url", response_model=ContextArtifactResponse)
async def ingest_context_url(
    project_id: str,
    payload: IngestUrlRequest,
    db: AsyncSession = Depends(get_db_session),
    storage: StorageService = Depends(get_storage_service),
) -> ContextArtifactResponse:
    """Crawl a web article or ingest a video URL with SSRF protection."""
    project = await get_or_create_project(project_id, db)
    url_str = payload.url.strip()

    # Detect if URL is a YouTube / direct video link
    is_video_url = any(k in url_str.lower() for k in ("youtube.com", "youtu.be", "vimeo.com")) or url_str.lower().endswith(
        (".mp4", ".mov", ".webm", ".m4a", ".mp3")
    )

    if is_video_url:
        ingester = MediaIngester()
        with tempfile.TemporaryDirectory(prefix="cineforge_ingest_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            try:
                media_file, title, duration = ingester.download_with_ytdlp(url_str, tmp_path)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to ingest media URL: {exc}",
                )

            keyframes = ingester.extract_scene_keyframes(media_file, tmp_path / "keyframes")
            audio_path = tmp_path / "extracted_audio.wav"
            ingester.extract_audio(media_file, audio_path)
            segments = ingester.transcribe_audio(audio_path)
            extracted_md = ingester.build_markdown_summary(title, duration, keyframes, segments)
            sha256_hex = compute_sha256_bytes(url_str.encode("utf-8"))

            persist_res = await storage.upload_file(
                file_path=media_file,
                project_id=project_id,
                subfolder="raw_context",
                sha256_hex=sha256_hex,
            )

            summarizer = ContextSummarizer()
            summary = await summarizer.summarize_context(extracted_md, title=title)
            summary_dict = summary.model_dump()

            artifact = ContextArtifact(
                project_id=project_id,
                content_hash=sha256_hex,
                source_type=ContextSourceType.VIDEO,
                original_filename=f"{title}.mp4",
                storage_path=persist_res.s3_key,
                extracted_markdown=extracted_md,
                summary_json=summary_dict,
            )
    else:
        crawler = WebCrawler()
        try:
            scraped = await crawler.crawl_url(url_str)
        except SSRFValidationError as ssrf_err:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"SSRF validation blocked request: {ssrf_err}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to crawl web URL: {exc}",
            )

        extracted_md = scraped.markdown_content
        sha256_hex = compute_sha256_bytes(url_str.encode("utf-8"))

        persist_res = await storage.upload_bytes(
            data=extracted_md.encode("utf-8"),
            project_id=project_id,
            subfolder="raw_context",
            extension="md",
            sha256_hex=sha256_hex,
        )

        summarizer = ContextSummarizer()
        summary = await summarizer.summarize_context(extracted_md, title=scraped.title)
        summary_dict = summary.model_dump()

        artifact = ContextArtifact(
            project_id=project_id,
            content_hash=sha256_hex,
            source_type=ContextSourceType.URL,
            original_filename=f"{scraped.title}.html",
            storage_path=persist_res.s3_key,
            extracted_markdown=extracted_md,
            summary_json=summary_dict,
        )

    db.add(artifact)
    await db.flush()

    manifest = dict(project.manifest)
    artifact_ids = manifest.get("contextArtifactIds", [])
    if artifact.id not in artifact_ids:
        artifact_ids.append(artifact.id)
        manifest["contextArtifactIds"] = artifact_ids
        project.manifest = manifest

    await db.commit()
    await db.refresh(artifact)

    return ContextArtifactResponse(
        id=artifact.id,
        project_id=project_id,
        content_hash=artifact.content_hash,
        source_type=str(artifact.source_type.value),
        original_filename=artifact.original_filename,
        storage_path=artifact.storage_path,
        extracted_markdown=artifact.extracted_markdown,
        summary_json=artifact.summary_json,
        cached=False,
    )


@router.get("/projects/{project_id}/context", response_model=List[ContextArtifactResponse])
async def list_project_context_artifacts(
    project_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> List[ContextArtifactResponse]:
    """Retrieve all context artifacts attached to the specified project."""
    stmt = (
        select(ContextArtifact)
        .where(ContextArtifact.project_id == project_id)
        .order_by(ContextArtifact.created_at.desc())
    )
    result = await db.execute(stmt)
    artifacts = result.scalars().all()

    return [
        ContextArtifactResponse(
            id=a.id,
            project_id=a.project_id,
            content_hash=a.content_hash,
            source_type=str(a.source_type.value),
            original_filename=a.original_filename,
            storage_path=a.storage_path,
            extracted_markdown=a.extracted_markdown,
            summary_json=a.summary_json,
            cached=False,
        )
        for a in artifacts
    ]


@router.get("/context/{artifact_id}", response_model=ContextArtifactResponse)
async def get_context_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ContextArtifactResponse:
    """Retrieve a single context artifact by its unique ID."""
    stmt = select(ContextArtifact).where(ContextArtifact.id == artifact_id)
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context artifact not found")

    return ContextArtifactResponse(
        id=artifact.id,
        project_id=artifact.project_id,
        content_hash=artifact.content_hash,
        source_type=str(artifact.source_type.value),
        original_filename=artifact.original_filename,
        storage_path=artifact.storage_path,
        extracted_markdown=artifact.extracted_markdown,
        summary_json=artifact.summary_json,
        cached=False,
    )


@router.delete("/projects/{project_id}/context/{artifact_id}")
async def delete_project_context_artifact(
    project_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Remove a context artifact and unlink it from the project's Master Manifest."""
    project = await get_or_create_project(project_id, db)
    stmt = select(ContextArtifact).where(
        ContextArtifact.id == artifact_id,
        ContextArtifact.project_id == project_id,
    )
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found in project")

    await db.delete(artifact)

    manifest = dict(project.manifest)
    artifact_ids: List[str] = manifest.get("contextArtifactIds", [])
    if artifact_id in artifact_ids:
        artifact_ids.remove(artifact_id)
        manifest["contextArtifactIds"] = artifact_ids
        project.manifest = manifest

    await db.commit()
    return {"status": "deleted", "artifactId": artifact_id}
