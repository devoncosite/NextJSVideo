"""Tests for Document Parser Integration (TASK-3.2)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from server.core.ingestion.doc_parser import DocumentParser, html_to_markdown
from server.models.context_artifact import ContextSourceType


def test_html_to_markdown_removes_scripts_and_extracts_structure() -> None:
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title><style>.hidden { display: none; }</style></head>
    <body>
        <nav><a href="/home">Home</a></nav>
        <header><h1>Header Navigation</h1></header>
        <script>console.log("malicious tracking");</script>
        <article>
            <h1>Elena's Discovery</h1>
            <p>She observed the mechanical drone drifting across the shore.</p>
            <blockquote>The signal was unlike anything recorded.</blockquote>
            <ul>
                <li>High frequency pulses</li>
                <li>Modulated carrier wave</li>
            </ul>
            <table>
                <tr><th>Component</th><th>Frequency</th></tr>
                <tr><td>Beacon</td><td>1420 MHz</td></tr>
                <tr><td>Drone</td><td>2.4 GHz</td></tr>
            </table>
        </article>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    md = html_to_markdown(html)
    assert "malicious tracking" not in md
    assert "Elena's Discovery" in md
    assert "mechanical drone drifting" in md
    assert "> The signal was unlike anything recorded." in md
    assert "- High frequency pulses" in md
    assert "| Component | Frequency |" in md
    assert "| Beacon | 1420 MHz |" in md


def test_document_parser_text_and_markdown() -> None:
    parser = DocumentParser()
    sample_text = "# Production Bible\n\nElena Vance travels to the coastal beacon."
    result = parser.parse_bytes(sample_text.encode("utf-8"), filename="bible.md", source_type="text")
    assert "Production Bible" in result
    assert "Elena Vance" in result


def test_document_parser_html_bytes() -> None:
    parser = DocumentParser()
    html_data = "<h1>Coastal Beacon Research</h1><p>Telemetry recorded in 1080p.</p>"
    result = parser.parse_bytes(html_data.encode("utf-8"), filename="article.html", source_type=ContextSourceType.HTML)
    assert "# Coastal Beacon Research" in result
    assert "Telemetry recorded in 1080p." in result
