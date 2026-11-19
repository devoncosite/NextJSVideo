"""Tests for Web URL Scraper & SSRF Protection (TASK-3.3)."""

from __future__ import annotations

import pytest

from server.core.ingestion.web_crawler import (
    SSRFValidationError,
    WebCrawler,
    validate_url_safe_for_ssrf,
)


def test_ssrf_validation_blocks_private_and_loopback_ips() -> None:
    blocked_urls = [
        "http://127.0.0.1:8008/api/v1/health",
        "http://127.0.0.1:5432",
        "http://localhost:3000/studio",
        "http://10.0.0.5/admin",
        "http://192.168.1.100:9000",
        "http://172.16.0.1/secrets",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.com/file.txt",
    ]

    for url in blocked_urls:
        with pytest.raises(SSRFValidationError):
            validate_url_safe_for_ssrf(url)


def test_web_crawler_extracts_article_data() -> None:
    crawler = WebCrawler()
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:title" content="Deep Ocean Telemetry Unlocked">
        <meta name="author" content="Dr. Sarah Jenkins">
        <meta property="article:published_time" content="2026-10-15">
        <meta property="og:image" content="https://cdn.example.com/beacon.jpg">
    </head>
    <body>
        <main>
            <h1>Deep Ocean Telemetry Unlocked</h1>
            <p>Scientists uncovered a synchronous pulse emitting from the Pacific seabed.</p>
        </main>
    </body>
    </html>
    """
    result = crawler._extract_article_data("https://science.example.com/telemetry", sample_html)
    assert result.title == "Deep Ocean Telemetry Unlocked"
    assert result.author == "Dr. Sarah Jenkins"
    assert result.published_date == "2026-10-15"
    assert "https://cdn.example.com/beacon.jpg" in result.media_urls
    assert "Scientists uncovered a synchronous pulse" in result.markdown_content
