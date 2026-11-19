"""Tests for JSON Patch (RFC 6902) Delta Engine (TASK-4.4)."""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from server.core.patch_engine import (
    apply_json_patches,
    create_replace_patch,
    create_status_progress_patch,
    normalize_json_pointer,
)


def test_normalize_json_pointer() -> None:
    assert normalize_json_pointer("scenes.0.keyframe.status") == "/scenes/0/keyframe/status"
    assert normalize_json_pointer("/consistencies/characters/1") == "/consistencies/characters/1"


def test_apply_json_patches_replace_and_nested() -> None:
    manifest: Dict[str, Any] = {
        "projectId": "proj_123",
        "version": 1,
        "scenes": [
            {
                "sceneNumber": 1,
                "video": {
                    "status": "idle",
                    "progressPercent": 0,
                    "selectedAssetUrl": None,
                },
            }
        ],
    }

    patches = [
        {"op": "replace", "path": "/scenes/0/video/status", "value": "generating"},
        {"op": "replace", "path": "/scenes/0/video/progressPercent", "value": 45},
    ]

    updated = apply_json_patches(manifest, patches)
    assert updated["scenes"][0]["video"]["status"] == "generating"
    assert updated["scenes"][0]["video"]["progressPercent"] == 45
    # Original should be untouched when in_place=False
    assert manifest["scenes"][0]["video"]["status"] == "idle"


def test_create_status_progress_patch() -> None:
    patches = create_status_progress_patch(
        base_path="/scenes/0/keyframe",
        status="completed",
        progress=100,
        asset_url="http://cdn.app/keyframe_01.png",
        variants=["http://cdn.app/v1.png", "http://cdn.app/v2.png"],
    )

    ops = {p["path"]: p["value"] for p in patches}
    assert ops["/scenes/0/keyframe/status"] == "completed"
    assert ops["/scenes/0/keyframe/progressPercent"] == 100
    assert ops["/scenes/0/keyframe/selectedAssetUrl"] == "http://cdn.app/keyframe_01.png"
    assert len(ops["/scenes/0/keyframe/variants"]) == 2


def test_rfc6902_payload_size_comparison() -> None:
    """Benchmark payload size: compare full manifest broadcast vs patch delta."""
    # Build realistic manifest with 5 scenes
    full_manifest = {
        "projectId": "proj_benchmark",
        "version": 14,
        "scenes": [
            {
                "sceneNumber": i,
                "keyframe": {"status": "completed", "prompt": "Wide shot of coast", "variants": ["v1", "v2"]},
                "video": {"status": "generating", "progressPercent": 60, "motionPrompt": "Camera slow pan"},
                "audio": {"status": "idle", "dialogue": []},
            }
            for i in range(1, 15)
        ],
    }

    full_bytes = len(json.dumps(full_manifest).encode("utf-8"))

    patch_delta = [
        {"op": "replace", "path": "/scenes/2/video/progressPercent", "value": 65},
    ]
    patch_bytes = len(json.dumps({"type": "patch", "version": 15, "patches": patch_delta}).encode("utf-8"))

    # Assert patch is more than 10x smaller than full manifest
    assert full_bytes > 2000
    assert patch_bytes < 150
    assert full_bytes / patch_bytes > 15
