"""Document Parser Integration (TASK-3.2).

Supports PDF, DOCX, PPTX, HTML, Markdown, and plain text formats.
Extracts clean Markdown, preserves GFM table structures, and normalizes headings.
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path
from typing import Optional, Union

from server.models.context_artifact import ContextSourceType


def html_to_markdown(html_content: str) -> str:
    """Parse HTML into clean GitHub Flavored Markdown."""
    try:
        from bs4 import BeautifulSoup, NavigableString, Tag
    except ImportError:
        # Basic regex-based fallback if bs4 is missing
        clean = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        return "\n\n".join(line.strip() for line in clean.splitlines() if line.strip())

    soup = BeautifulSoup(html_content, "lxml" if "lxml" in BeautifulSoup.__dict__ else "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Process tables into Markdown tables
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        md_table_rows = []
        for row_idx, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            cell_texts = [re.sub(r"\s+", " ", cell.get_text(strip=True)).replace("|", "\\|") for cell in cells]
            if not cell_texts:
                continue
            md_table_rows.append("| " + " | ".join(cell_texts) + " |")
            if row_idx == 0:
                md_table_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
        
        if md_table_rows:
            table_markdown = "\n" + "\n".join(md_table_rows) + "\n"
            table.replace_with(NavigableString(table_markdown))

    # Process headings
    for h_level in range(1, 7):
        for h in soup.find_all(f"h{h_level}"):
            h_text = h.get_text(strip=True)
            if h_text:
                h.replace_with(NavigableString(f"\n\n{'#' * h_level} {h_text}\n\n"))

    # Process list items
    for li in soup.find_all("li"):
        li_text = li.get_text(strip=True)
        if li_text:
            li.replace_with(NavigableString(f"\n- {li_text}"))

    # Process paragraphs
    for p in soup.find_all("p"):
        p_text = p.get_text(strip=True)
        if p_text:
            p.replace_with(NavigableString(f"\n\n{p_text}\n\n"))

    # Process blockquotes
    for bq in soup.find_all("blockquote"):
        bq_text = bq.get_text(strip=True)
        if bq_text:
            bq.replace_with(NavigableString(f"\n\n> {bq_text}\n\n"))

    # Process code
    for code in soup.find_all("pre"):
        code_text = code.get_text()
        if code_text:
            code.replace_with(NavigableString(f"\n\n```\n{code_text.strip()}\n```\n\n"))

    raw_text = soup.get_text()
    # Normalize multiple newlines and spaces
    clean_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    return clean_text.strip()


class DocumentParser:
    """Multimodal document parsing engine with Docling/MarkItDown and native fallbacks."""

    def __init__(self, use_markitdown: bool = True) -> None:
        self.use_markitdown = use_markitdown
        self._markitdown_instance = None
        if self.use_markitdown:
            try:
                from markitdown import MarkItDown
                self._markitdown_instance = MarkItDown()
            except ImportError:
                self._markitdown_instance = None

    def parse_bytes(
        self,
        data: bytes,
        filename: str,
        source_type: Optional[Union[ContextSourceType, str]] = None,
    ) -> str:
        """Parse raw document bytes into Markdown."""
        ext = Path(filename).suffix.lstrip(".").lower()
        resolved_type = str(source_type.value if isinstance(source_type, ContextSourceType) else (source_type or ext)).lower()

        with tempfile.NamedTemporaryFile(prefix="doc_parse_", suffix=f".{ext}", delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            return self.parse_file(tmp.name, source_type=resolved_type)

    def parse_file(
        self,
        file_path: Union[str, Path],
        source_type: Optional[Union[ContextSourceType, str]] = None,
    ) -> str:
        """Parse document file on disk into Markdown."""
        path = Path(file_path)
        ext = path.suffix.lstrip(".").lower()
        st = str(source_type.value if isinstance(source_type, ContextSourceType) else (source_type or ext)).lower()

        # Try MarkItDown first if available
        if self._markitdown_instance is not None and st in ("pdf", "docx", "pptx", "html"):
            try:
                result = self._markitdown_instance.convert(str(path))
                if result and result.text_content and result.text_content.strip():
                    return result.text_content.strip()
            except Exception:
                pass  # Fall through to specific parsers

        if st == "html":
            return self._parse_html_file(path)
        elif st == "pdf":
            return self._parse_pdf_file(path)
        elif st in ("docx", "doc"):
            return self._parse_docx_file(path)
        elif st in ("pptx", "ppt"):
            return self._parse_pptx_file(path)
        else:
            return self._parse_text_file(path)

    def _parse_html_file(self, path: Path) -> str:
        content = path.read_text(encoding="utf-8", errors="replace")
        return html_to_markdown(content)

    def _parse_pdf_file(self, path: Path) -> str:
        """Extract text from PDF pages with header division."""
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_md = []
            for i, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                clean = page_text.strip()
                if clean:
                    pages_md.append(f"## Page {i}\n\n{clean}")
            if pages_md:
                return "\n\n".join(pages_md)
        except Exception:
            pass

        # Binary text scan fallback if pypdf fails
        raw = path.read_bytes()
        strings = re.findall(b"[\x20-\x7e]{4,}", raw)
        extracted = "\n".join(s.decode("latin1", errors="ignore") for s in strings[:1000])
        return extracted or "# Extracted Document Content\n\nNo readable text extracted."

    def _parse_docx_file(self, path: Path) -> str:
        """Extract paragraphs and tables from DOCX using python-docx."""
        try:
            import docx
            doc = docx.Document(str(path))
            sections = []

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue
                style_name = paragraph.style.name.lower() if paragraph.style else ""
                if "heading 1" in style_name:
                    sections.append(f"# {text}")
                elif "heading 2" in style_name:
                    sections.append(f"## {text}")
                elif "heading 3" in style_name:
                    sections.append(f"### {text}")
                else:
                    sections.append(text)

            for table in doc.tables:
                rows_md = []
                for row_idx, row in enumerate(table.rows):
                    cells = [c.text.strip().replace("\n", " ").replace("|", "\\|") for c in row.cells]
                    rows_md.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        rows_md.append("| " + " | ".join(["---"] * len(cells)) + " |")
                if rows_md:
                    sections.append("\n" + "\n".join(rows_md) + "\n")

            return "\n\n".join(sections)
        except Exception:
            return self._parse_text_file(path)

    def _parse_pptx_file(self, path: Path) -> str:
        """Extract text from presentation slides."""
        try:
            from pptx import Presentation
            prs = Presentation(str(path))
            slides_md = []
            for i, slide in enumerate(prs.slides, 1):
                slide_lines = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_lines.append(shape.text.strip())
                if slide_lines:
                    slides_md.append(f"## Slide {i}\n\n" + "\n\n".join(slide_lines))
            if slides_md:
                return "\n\n".join(slides_md)
        except Exception:
            pass
        return self._parse_text_file(path)

    def _parse_text_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace").strip()
