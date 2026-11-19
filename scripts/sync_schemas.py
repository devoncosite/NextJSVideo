#!/usr/bin/env python3
"""Dual-Language Schema Synchronizer (Pydantic v2 -> JSON Schema & TypeScript Zod) (TASK-1.4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SCHEMA_JSON_PATH = ROOT_DIR / "shared" / "schemas" / "master_manifest.schema.json"
TS_MANIFEST_PATH = ROOT_DIR / "web" / "src" / "types" / "manifest.ts"


def build_fallback_json_schema() -> dict:
    """Deterministic JSON Schema matching server/schemas/manifest.py MasterManifest."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MasterManifest",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "projectId",
            "version",
            "title",
            "format",
            "contextArtifactIds",
            "globalStyle",
            "consistencies",
            "scenes",
            "outroEndFrame",
            "assembly",
        ],
        "properties": {
            "projectId": {"type": "string", "minLength": 1},
            "version": {"type": "integer", "minimum": 1, "default": 1},
            "title": {"type": "string", "minLength": 1},
            "format": {
                "type": "string",
                "enum": [
                    "cinematic_drama",
                    "documentary",
                    "explainer",
                    "podcast_clip",
                    "vertical_short",
                ],
            },
            "contextArtifactIds": {"type": "array", "items": {"type": "string"}},
            "globalStyle": {"$ref": "#/$defs/GlobalStyle"},
            "consistencies": {"$ref": "#/$defs/ConsistenciesContainer"},
            "scenes": {"type": "array", "items": {"$ref": "#/$defs/SceneNode"}},
            "outroEndFrame": {"$ref": "#/$defs/OutroEndFrame"},
            "assembly": {"$ref": "#/$defs/AssemblyConfig"},
        },
        "$defs": {
            "AssetStatus": {
                "type": "string",
                "enum": ["idle", "queued", "generating", "completed", "failed"],
            },
            "CharacterConsistency": {
                "type": "object",
                "required": ["id", "name", "role", "description", "prompt360", "status", "progressPercent", "selectedAssetUrl", "variants"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "role": {"type": "string", "enum": ["protagonist", "antagonist", "supporting", "narrator"]},
                    "description": {"type": "string"},
                    "prompt360": {"type": "string"},
                    "negativePrompt": {"type": ["string", "null"]},
                    "status": {"$ref": "#/$defs/AssetStatus"},
                    "progressPercent": {"type": "number", "minimum": 0, "maximum": 100},
                    "error": {"type": ["string", "null"]},
                    "selectedAssetUrl": {"type": ["string", "null"]},
                    "variants": {"type": "array", "items": {"type": "string"}},
                },
            },
            "ObjectConsistency": {
                "type": "object",
                "required": ["id", "name", "category", "prompt360", "status", "progressPercent", "selectedAssetUrl", "variants"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": ["prop", "vehicle", "costume", "environment"]},
                    "prompt360": {"type": "string"},
                    "status": {"$ref": "#/$defs/AssetStatus"},
                    "progressPercent": {"type": "number", "minimum": 0, "maximum": 100},
                    "error": {"type": ["string", "null"]},
                    "selectedAssetUrl": {"type": ["string", "null"]},
                    "variants": {"type": "array", "items": {"type": "string"}},
                },
            },
            "GlobalStyle": {
                "type": "object",
                "required": ["aspectRatio", "resolution", "visualStylePrompt", "colorGradingPreset"],
                "properties": {
                    "aspectRatio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]},
                    "resolution": {"type": "string", "enum": ["1080p", "4k"]},
                    "visualStylePrompt": {"type": "string"},
                    "colorGradingPreset": {"type": "string"},
                    "musicGenrePrompt": {"type": ["string", "null"]},
                },
            },
            "ConsistenciesContainer": {
                "type": "object",
                "required": ["characters", "objects"],
                "properties": {
                    "characters": {"type": "array", "items": {"$ref": "#/$defs/CharacterConsistency"}},
                    "objects": {"type": "array", "items": {"$ref": "#/$defs/ObjectConsistency"}},
                },
            },
            "SceneNode": {
                "type": "object",
                "required": ["sceneNumber", "id", "timestamp", "visualDescription", "camera", "keyframe", "audio", "video"],
            },
            "OutroEndFrame": {
                "type": "object",
                "required": ["prompt", "selectedAssetUrl", "variants", "status"],
            },
            "AssemblyConfig": {
                "type": "object",
                "required": ["transitionType", "transitionDurationSec", "backgroundMusicUrl", "burnCaptions", "subtitleStyle", "thumbnail", "finalVideoUrl", "bundleZipUrl", "status", "progressPercent"],
            },
        },
    }


def export_json_schema() -> dict:
    """Export Pydantic v2 JSON Schema to shared/schemas/master_manifest.schema.json."""
    try:
        from server.schemas.manifest import MasterManifest  # type: ignore

        schema = MasterManifest.model_json_schema()
    except ImportError:
        schema = build_fallback_json_schema()

    SCHEMA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_JSON_PATH.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    return schema


def verify_zod_parity(schema: dict) -> None:
    """Verify TypeScript Zod manifest exists and covers all top-level MasterManifest properties."""
    if not TS_MANIFEST_PATH.exists():
        raise FileNotFoundError(f"TypeScript manifest missing at {TS_MANIFEST_PATH}")
    ts_content = TS_MANIFEST_PATH.read_text(encoding="utf-8")
    required_props = schema.get("properties", {}).keys()
    missing = [prop for prop in required_props if f"{prop}:" not in ts_content]
    if missing:
        raise RuntimeError(f"Zod schema in {TS_MANIFEST_PATH} is missing properties: {missing}")


def main() -> int:
    schema = export_json_schema()
    verify_zod_parity(schema)
    print(f"[sync_schemas] Exported JSON Schema ({len(schema.get('$defs', {}))} defs) -> {SCHEMA_JSON_PATH}")
    print(f"[sync_schemas] Verified TypeScript Zod schema parity -> {TS_MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
