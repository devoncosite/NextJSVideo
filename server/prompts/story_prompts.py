"""ContentMachine & AI-Content-Studio Prompt Engineering Engine (TASK-5.2).

Houses the 300+ line production prompt rules, character 360° turnaround specifications,
cinematographic camera directives, and structured output instructions.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# --- Cinematography & Camera Movement Lexicon ---
CAMERA_MOVEMENTS = [
    "Slow cinematic dolly push-in",
    "Subtle creeping tracking shot",
    "Low-angle upward tilt revealing horizon",
    "Smooth lateral camera truck with parallax foreground",
    "Sweeping high-altitude aerial drone orbit",
    "Handheld organic shoulder-mount tracking shot",
    "Static tripod master shot with atmospheric depth",
    "Rapid whip-pan transition into close focus",
]

LIGHTING_CONVENTIONS = [
    "35mm anamorphic film, moody coastal chiaroscuro lighting, diffuse maritime mist",
    "Golden hour warm sidelight, high dynamic range, soft lens flares",
    "Moody neon cyberpunk rain-slicked pavement reflections, high contrast shadows",
    "Diffused overcast Scandinavian natural light, muted earth tones",
    "Dramatic high-contrast rim lighting, deep volumetric shadows, Kodak 2383 stock",
]


# --- Master System Instructions for the Planner ---
PLANNER_SYSTEM_INSTRUCTION = """
You are the Lead Director and Screenplay Architect for CineForge AI Studio.
Your mission is to transform a creative brief and multimodal reference materials into a rigorously structured Master JSON Manifest.

You must obey the following IRONCLAD PRODUCTION RULES:
1. MASTER MANIFEST CONSISTENCY:
   - Output MUST be valid JSON adhering strictly to the MasterManifest schema.
   - Do NOT emit Markdown formatting (no ```json or explanatory prose).
   - All character and object references MUST use stable IDs (e.g. 'char_01', 'obj_01').

2. CHARACTER 360° SPECIFICATIONS:
   - Every character 'prompt360' must be a character turnaround model sheet:
     'Full-body character turnaround sheet, front view, 90-degree profile view, three-quarter view, back view, neutral grey studio background, diffuse soft lighting, hyper-consistent facial features and wardrobe'.
   - Avoid generic descriptions; specify age, hair texture, fabric weave, distinctive marks, and emotional posture.

3. SCENE TIMING & FRAME CONTINUITY:
   - Scenes must form a continuous chronological sequence: Scene N's timestamp.endSec MUST equal Scene N+1's timestamp.startSec.
   - Scene duration must be between 3 and 10 seconds.
   - Frame chaining: Scene N's keyframe.prompt must logically flow from the previous camera position.
   - The final scene must transition cleanly into 'outroEndFrame'.

4. CAMERA DIRECTIVES:
   - Every scene must define camera.angle, camera.movement, and camera.lens (e.g., '35mm shallow depth of field, f/1.8').
   - Use dynamic cinematographic vocabulary: dolly push-in, low-angle tracking, pedestal down.

5. AUDIO & DIALOGUE TIMING:
   - Voiceover and dialogue must NOT overlap in timestamps within a scene.
   - Voiceover startOffsetSec to endOffsetSec must fit completely within scene boundaries (endOffsetSec <= scene.endSec - scene.startSec).
   - Dialogue speakerId must match an existing character ID in consistencies.characters.
"""


def build_planner_user_prompt(
    user_prompt: str,
    format_type: str = "cinematic_drama",
    aspect_ratio: str = "16:9",
    context_markdown: Optional[str] = None,
    num_scenes: int = 4,
) -> str:
    """Construct prompt for structured planning pass with contextual reference injection."""
    context_section = ""
    if context_markdown and context_markdown.strip():
        context_section = f"""
---
PRE-INGESTED REFERENCE MATERIAL & PRODUCTION BIBLE:
{context_markdown[:10000]}
---
Incorporate the visual style, characters, locations, and facts from the reference material above into the Master JSON.
"""

    return f"""
Project Request:
Format: {format_type}
Target Aspect Ratio: {aspect_ratio}
Target Scene Count: {num_scenes}
Concept / Script Brief:
"{user_prompt}"

{context_section}

Generate a comprehensive Master JSON manifest with:
1. globalStyle (aspectRatio, resolution 1080p, visualStylePrompt, colorGradingPreset, musicGenrePrompt).
2. consistencies (1-3 distinct characters with full 360 turnaround prompts; 1-2 key objects/props).
3. scenes (array of {num_scenes} chronological scenes with exact startSec/endSec, camera movements, keyframe prompts with refIds, audio voiceovers/dialogue, and video motion prompts).
4. outroEndFrame (final closing visual anchor).
5. assembly (transitions, burnCaptions true, subtitleStyle).

Return the JSON object only.
"""


def build_character_turnaround_prompt(
    character_name: str,
    role: str,
    visual_description: str,
    wardrobe: str,
    style_preset: str = "35mm anamorphic film",
) -> str:
    """Format prompt for 360° character turnaround sheet."""
    return (
        f"Character turnaround model sheet of {character_name}, {role}. "
        f"{visual_description}. Wearing {wardrobe}. "
        f"Four distinct camera angles side-by-side on one seamless frame: front-facing view, side profile view, three-quarter dynamic angle, and rear back view. "
        f"Neutral solid studio grey background, even diffuse softbox lighting, centered composition, high fidelity anatomy, no background clutter. "
        f"Aesthetic: {style_preset}."
    )


def build_object_turnaround_prompt(
    object_name: str,
    category: str,
    visual_description: str,
    style_preset: str = "35mm anamorphic film",
) -> str:
    """Format prompt for object/prop multi-angle reference sheet."""
    return (
        f"Commercial product turnaround reference sheet of {object_name} ({category}). "
        f"{visual_description}. "
        f"Multi-angle product showcase displaying front angle, top-down 45-degree angle, side view, and intricate close-up mechanical detail. "
        f"Clean neutral gradient studio background, soft cinematic studio fill lighting, tack-sharp focus. "
        f"Aesthetic: {style_preset}."
    )


def build_keyframe_prompt(
    scene_description: str,
    character_refs: List[Dict[str, str]],
    object_refs: List[Dict[str, str]],
    camera_directive: str,
    global_style: str,
) -> str:
    """Synthesize reference-injected keyframe prompt with character and object conditioning tags."""
    char_notes = ""
    if character_refs:
        char_desc = ", ".join(f"{c['name']} [{c['id']}]" for c in character_refs)
        char_notes = f"Featuring characters: {char_desc}. "

    obj_notes = ""
    if object_refs:
        obj_desc = ", ".join(f"{o['name']} [{o['id']}]" for o in object_refs)
        obj_notes = f"Including items: {obj_desc}. "

    return (
        f"{scene_description}. {char_notes}{obj_notes}"
        f"Cinematography: {camera_directive}. "
        f"Visual Tone: {global_style}. 1080p high definition cinematic keyframe."
    )
