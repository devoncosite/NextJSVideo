"""JSON Patch (RFC 6902) Delta Engine & Broadcast Formatter (TASK-4.4)."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Union


def normalize_json_pointer(path: str) -> str:
    """Normalize path to RFC 6902 JSON pointer format starting with '/'."""
    if not path.startswith("/"):
        # Handle dot-path: scenes.0.keyframe.status -> /scenes/0/keyframe/status
        segments = path.strip(".").split(".")
        return "/" + "/".join(segments)
    return path


def create_replace_patch(path: str, value: Any) -> Dict[str, Any]:
    """Create an RFC 6902 'replace' patch operation."""
    return {
        "op": "replace",
        "path": normalize_json_pointer(path),
        "value": value,
    }


def create_status_progress_patch(
    base_path: str,
    status: str,
    progress: int,
    error: Optional[str] = None,
    asset_url: Optional[str] = None,
    variants: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Create a batch of RFC 6902 patches for standard asset node state updates."""
    norm_base = normalize_json_pointer(base_path).rstrip("/")
    patches: List[Dict[str, Any]] = [
        {"op": "replace", "path": f"{norm_base}/status", "value": status},
        {"op": "replace", "path": f"{norm_base}/progressPercent", "value": progress},
    ]

    if error is not None:
        patches.append({"op": "replace", "path": f"{norm_base}/error", "value": error})
    elif status in ("queued", "generating", "completed"):
        patches.append({"op": "replace", "path": f"{norm_base}/error", "value": None})

    if asset_url is not None:
        patches.append({"op": "replace", "path": f"{norm_base}/selectedAssetUrl", "value": asset_url})

    if variants is not None:
        patches.append({"op": "replace", "path": f"{norm_base}/variants", "value": variants})

    return patches


def _parse_tokens(path: str) -> List[Union[str, int]]:
    """Parse JSON pointer path into dictionary keys and integer array indices."""
    tokens = path.strip("/").split("/")
    result: List[Union[str, int]] = []
    for t in tokens:
        # RFC 6901 decoding (~1 -> /, ~0 -> ~)
        decoded = t.replace("~1", "/").replace("~0", "~")
        if decoded.isdigit():
            result.append(int(decoded))
        else:
            result.append(decoded)
    return result


def apply_json_patches(
    document: Dict[str, Any],
    patches: List[Dict[str, Any]],
    in_place: bool = False,
) -> Dict[str, Any]:
    """Apply an array of RFC 6902 JSON patch operations to a nested dictionary/list structure."""
    target = document if in_place else copy.deepcopy(document)

    for patch in patches:
        op = patch.get("op")
        raw_path = patch.get("path", "")
        value = patch.get("value")

        if not raw_path or raw_path == "/":
            if op == "replace" and isinstance(value, dict):
                target = copy.deepcopy(value) if not in_place else target
                continue

        tokens = _parse_tokens(raw_path)
        if not tokens:
            continue

        # Traverse to the parent container of the targeted leaf
        curr: Any = target
        for token in tokens[:-1]:
            if isinstance(curr, list):
                if isinstance(token, int) and 0 <= token < len(curr):
                    curr = curr[token]
                else:
                    raise KeyError(f"Array index {token} out of bounds in path {raw_path}")
            elif isinstance(curr, dict):
                if token not in curr:
                    curr[token] = {}
                curr = curr[token]
            else:
                raise TypeError(f"Cannot traverse through non-container type at {token} in {raw_path}")

        last_token = tokens[-1]

        if op in ("replace", "add"):
            if isinstance(curr, list):
                if isinstance(last_token, int):
                    if 0 <= last_token < len(curr):
                        curr[last_token] = value
                    elif last_token == len(curr):
                        curr.append(value)
                    else:
                        raise IndexError(f"List index {last_token} out of range in path {raw_path}")
                elif str(last_token) == "-":
                    curr.append(value)
                else:
                    raise TypeError(f"Expected int index for list, got {last_token}")
            elif isinstance(curr, dict):
                curr[str(last_token)] = value
        elif op == "remove":
            if isinstance(curr, list) and isinstance(last_token, int) and 0 <= last_token < len(curr):
                curr.pop(last_token)
            elif isinstance(curr, dict) and str(last_token) in curr:
                del curr[str(last_token)]

    return target
