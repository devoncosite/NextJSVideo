"""Multimodal LLM Context Summarizer (Gemini Flash Pass) (TASK-3.5)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from server.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ContextSummary(BaseModel):
    """Structured multimodal context summary extracted from ingested source materials."""

    core_narrative: str = Field(description="Summary of facts, narrative premise, or main thesis.")
    visual_style: str = Field(description="Lighting, color palette, camera conventions, and cinematography.")
    key_entities: List[str] = Field(
        default_factory=list,
        description="List of notable characters, historical figures, vehicles, locations, or props.",
    )
    pacing: str = Field(description="Cadence, emotional arc, rhythm, and acoustic/musical atmosphere.")
    themes: List[str] = Field(default_factory=list, description="Core thematic keywords or concepts.")


SUMMARIZER_SYSTEM_INSTRUCTION = """
You are the Multimodal Context Analyst for CineForge AI Studio.
Your role is to analyze ingested reference materials (documents, web articles, video transcripts, or audio notes)
and extract actionable creative constraints and production bibles for downstream AI video generation.

Extract:
1. core_narrative: Concise synthesis of topic, plot, or factual substance.
2. visual_style: Aesthetic qualities (lighting, lenses, color grading, tone, environment).
3. key_entities: High-priority subjects, characters, objects, and locations mentioned.
4. pacing: Rhythm, tension, tone, and musical cues.
5. themes: 3 to 7 thematic tags.

Output MUST strictly conform to the JSON schema without any conversational markdown wrapper.
"""


class ContextSummarizer:
    """Summarizes multimodal context into structured JSON using Gemini Flash with deterministic fallback."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def summarize_context(
        self,
        extracted_markdown: str,
        title: Optional[str] = None,
        image_bytes_list: Optional[List[bytes]] = None,
    ) -> ContextSummary:
        """Execute single-pass multimodal context summarization."""
        api_key = self.settings.GEMINI_API_KEY

        if api_key and api_key.strip():
            try:
                return await self._call_gemini_flash(extracted_markdown, title, image_bytes_list)
            except Exception as exc:
                logger.warning("Gemini Flash API call failed (%s); falling back to heuristic summarizer.", exc)

        return self._heuristic_fallback_summary(extracted_markdown, title)

    async def _call_gemini_flash(
        self,
        extracted_markdown: str,
        title: Optional[str],
        image_bytes_list: Optional[List[bytes]],
    ) -> ContextSummary:
        """Call Gemini Flash with structured schema output."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.settings.GEMINI_API_KEY)
            prompt = f"Title: {title or 'Untitled Source'}\n\nDocument Content:\n{extracted_markdown[:15000]}"

            contents: List[Any] = [prompt]
            if image_bytes_list:
                for img_bytes in image_bytes_list[:3]:  # Max 3 keyframe references
                    contents.append(
                        types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                    )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARIZER_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ContextSummary,
                    temperature=0.2,
                ),
            )

            if response.text:
                return ContextSummary.model_validate_json(response.text)
        except Exception as exc:
            # Fall back to google.generativeai if google-genai fails
            logger.info("google-genai client exception (%s), attempting legacy google.generativeai.", exc)
            import google.generativeai as gai
            gai.configure(api_key=self.settings.GEMINI_API_KEY)
            model = gai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=SUMMARIZER_SYSTEM_INSTRUCTION,
            )
            prompt = f"Return JSON only:\nTitle: {title or 'Untitled'}\n\n{extracted_markdown[:15000]}"
            resp = model.generate_content(prompt)
            clean_json = re.sub(r"```json|```", "", resp.text).strip()
            return ContextSummary.model_validate_json(clean_json)

        raise RuntimeError("Failed to generate response from Gemini Flash")

    def _heuristic_fallback_summary(
        self,
        markdown: str,
        title: Optional[str] = None,
    ) -> ContextSummary:
        """Deterministic heuristic analysis when Gemini API key is absent or unreachable."""
        clean = re.sub(r"[#*_>`]", " ", markdown)
        words = clean.split()
        first_few_sentences = [s.strip() for s in re.split(r"[.!?]\s+", clean) if len(s.strip()) > 15]

        core_narrative = (
            " ".join(first_few_sentences[:3])
            if first_few_sentences
            else f"Extracted overview for {title or 'context artifact'}."
        )

        # Detect capital entities
        capital_words = re.findall(r"\b[A-Z][a-z]{3,}\b", clean)
        freq: Dict[str, int] = {}
        stop_words = {"This", "That", "There", "When", "With", "From", "Into", "Their", "About", "These", "Then", "Page"}
        for w in capital_words:
            if w not in stop_words:
                freq[w] = freq.get(w, 0) + 1

        top_entities = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)[:6]
        if not top_entities:
            top_entities = ["Protagonist", "Primary Subject", "Environment"]

        # Detect visual style cues
        visual_keywords = []
        lower_md = markdown.lower()
        if any(k in lower_md for k in ("dark", "night", "shadow", "coastal", "dusk")):
            visual_keywords.append("Moody chiaroscuro lighting, deep maritime shadows")
        if any(k in lower_md for k in ("bright", "sun", "day", "warm")):
            visual_keywords.append("High-key warm daylight, naturalistic illumination")
        if any(k in lower_md for k in ("film", "35mm", "grain", "cinematic")):
            visual_keywords.append("35mm anamorphic texture, shallow depth of field")
        if not visual_keywords:
            visual_keywords.append("Cinematic 35mm composition with neutral studio grading")

        return ContextSummary(
            core_narrative=core_narrative,
            visual_style="; ".join(visual_keywords),
            key_entities=top_entities,
            pacing="Measured cadence with building narrative tension.",
            themes=[w.lower() for w in top_entities[:4]],
        )
