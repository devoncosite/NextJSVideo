"""Web URL Scraper via Crawl4AI & Async HTTP with SSRF Protection (TASK-3.3)."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from server.core.ingestion.doc_parser import html_to_markdown


class SSRFValidationError(Exception):
    """Raised when a URL targets a private IP, loopback, cloud metadata service, or local network."""
    pass


@dataclass
class ScrapedArticleResult:
    """Structured extraction of web article content."""

    url: str
    title: str
    author: Optional[str]
    published_date: Optional[str]
    markdown_content: str
    media_urls: List[str]


# RFC 1918, RFC 3927, RFC 4291, RFC 6890 private/reserved IP networks
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6
]


def validate_url_safe_for_ssrf(url: str) -> None:
    """Validate that the target URL does not resolve to loopback, private, or metadata IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFValidationError(f"Invalid URL scheme '{parsed.scheme}': only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL contains no valid host name.")

    lowered_host = hostname.lower()
    if lowered_host in ("localhost", "local", "metadata.google.internal") or lowered_host.endswith(".local"):
        raise SSRFValidationError(f"Target host '{hostname}' is not permitted.")

    # Resolve hostname to IP addresses
    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise SSRFValidationError(f"Failed to resolve DNS for host '{hostname}': {exc}")

    for addr_info in addr_infos:
        sockaddr = addr_info[4]
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)

        # Check against blocked networks
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SSRFValidationError(f"Access to private/loopback/reserved IP address {ip_str} is blocked.")

        for net in BLOCKED_NETWORKS:
            if ip in net:
                raise SSRFValidationError(f"IP address {ip_str} belongs to protected network {net}.")


class WebCrawler:
    """Async web crawler with SSRF protection, clean article extraction, and markdown conversion."""

    def __init__(
        self,
        timeout: float = 15.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.timeout = timeout
        self._client = http_client

    async def crawl_url(self, url: str) -> ScrapedArticleResult:
        """Fetch URL with SSRF validation and extract structured content."""
        validate_url_safe_for_ssrf(url)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 CineForge/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async def _fetch(client: httpx.AsyncClient) -> httpx.Response:
            resp = await client.get(url, headers=headers, follow_redirects=True, timeout=self.timeout)
            # Validate final redirect destination
            validate_url_safe_for_ssrf(str(resp.url))
            resp.raise_for_status()
            return resp

        if self._client is not None:
            response = await _fetch(self._client)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await _fetch(client)

        html_text = response.text
        return self._extract_article_data(url, html_text)

    def _extract_article_data(self, url: str, html_text: str) -> ScrapedArticleResult:
        """Extract title, author, date, media links, and markdown from HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Title extraction
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = str(og_title["content"]).strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.h1:
            title = soup.h1.get_text(strip=True)
        if not title:
            title = "Untitled Web Article"

        # 2. Author extraction
        author: Optional[str] = None
        author_meta = soup.find("meta", attrs={"name": re.compile(r"author", re.I)}) or soup.find(
            "meta", property=re.compile(r"article:author", re.I)
        )
        if author_meta and author_meta.get("content"):
            author = str(author_meta["content"]).strip()

        # 3. Published date
        published_date: Optional[str] = None
        date_meta = (
            soup.find("meta", property="article:published_time")
            or soup.find("meta", attrs={"name": re.compile(r"date|pubdate", re.I)})
            or soup.find("time")
        )
        if date_meta:
            if date_meta.name == "time" and date_meta.get("datetime"):
                published_date = str(date_meta["datetime"]).strip()
            elif date_meta.get("content"):
                published_date = str(date_meta["content"]).strip()

        # 4. Extract primary media elements
        media_urls: List[str] = []
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            media_urls.append(str(og_image["content"]).strip())

        for img in soup.find_all("img"):
            src = img.get("src")
            if src and src.startswith("http") and src not in media_urls:
                media_urls.append(src)
            if len(media_urls) >= 10:
                break

        # 5. Extract core content
        # Focus on article or main if present
        content_container = soup.find("article") or soup.find("main") or soup.body or soup
        markdown_body = html_to_markdown(str(content_container))

        header_lines = [f"# {title}\n"]
        if author:
            header_lines.append(f"**Author**: {author}")
        if published_date:
            header_lines.append(f"**Date**: {published_date}")
        header_lines.append(f"**Source URL**: {url}\n\n---\n")

        full_markdown = "\n".join(header_lines) + "\n" + markdown_body

        return ScrapedArticleResult(
            url=url,
            title=title,
            author=author,
            published_date=published_date,
            markdown_content=full_markdown.strip(),
            media_urls=media_urls,
        )
