from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import List


def extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n".join(pages)


def extract_epub(path: Path) -> str:
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(str(path))
    texts: List[str] = []
    for item in book.get_items():
        if item.get_type() == 9:  # DOCUMENT
            soup = BeautifulSoup(item.get_body_content(), "html.parser")
            texts.append(soup.get_text(" "))
    return "\n".join(texts)


def extract_html(path: Path) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    return soup.get_text(separator=" ", strip=True)


def extract_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_rst(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_csv(path: Path, delimiter: str = ",") -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return " ".join(cell for row in reader for cell in row)


def extract_tsv(path: Path) -> str:
    return extract_csv(path, delimiter="\t")


def extract_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    return json.dumps(data, ensure_ascii=False)


def extract_jsonl(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            lines.append(json.dumps(json.loads(line), ensure_ascii=False))
    return "\n".join(lines)


def extract_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as e:
        raise ImportError("python-docx is required for .docx support: pip install python-docx") from e

    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def extract_xml(path: Path) -> str:
    """Extract plain text from XML files, with USLM-aware handling.

    USLM = United States Legislative Markup (http://xml.house.gov/schemas/uslm/1.0),
    the official format used by govinfo.gov for bills, amendments, and congressional records.

    For USLM documents, this extractor preserves document structure by pulling:
      - Bill/document title from <dc:title>, <official-title>, or <shortTitle>
      - Sponsor/cosponsor metadata from <sponsor> and <cosponsor> elements
      - Section headings from <heading> elements
      - Body text from <text>, <paragraph>, <section>, <subsection>, <enum> elements
      - Preamble/recitals from <preamble> and <recital> elements

    For non-USLM XML, falls back to stripping all tags and returning plain text.
    Uses only stdlib (xml.etree.ElementTree) — no additional dependencies.
    """
    import xml.etree.ElementTree as ET

    USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
    DC_NS = "http://purl.org/dc/elements/1.1/"

    # Tags whose text content we want to extract (local name only)
    USLM_TEXT_TAGS = {
        "official-title", "shortTitle", "sponsor", "cosponsor",
        "heading", "text", "paragraph", "section", "subsection",
        "enum", "preamble", "recital", "chapeau", "continuation",
        "quoted-block", "after-quoted-block",
    }
    # Tags that act as structural separators (emit a blank line before/after)
    USLM_BLOCK_TAGS = {
        "section", "subsection", "paragraph", "preamble", "recital",
    }

    def _local(tag: str) -> str:
        """Strip namespace from a Clark-notation tag."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _collect_text(elem: ET.Element) -> str:
        """Recursively collect all text within an element."""
        parts = []
        if elem.text and elem.text.strip():
            parts.append(elem.text.strip())
        for child in elem:
            child_text = _collect_text(child)
            if child_text:
                parts.append(child_text)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())
        return " ".join(parts)

    def _is_uslm(root: ET.Element) -> bool:
        tag = root.tag
        ns = ""
        if "}" in tag:
            ns = tag.split("}", 1)[0].lstrip("{")
        return ns == USLM_NS or "uslm" in ns.lower()

    def _extract_uslm(root: ET.Element) -> str:
        """Walk the USLM tree and extract structured text."""
        lines: List[str] = []

        # Pull dc:title first if present
        dc_title_tag = f"{{{DC_NS}}}title"
        dc_title = root.find(f".//{dc_title_tag}")
        if dc_title is not None and dc_title.text and dc_title.text.strip():
            lines.append(dc_title.text.strip())
            lines.append("")

        def walk(elem: ET.Element, depth: int = 0) -> None:
            local = _local(elem.tag)

            if local in USLM_BLOCK_TAGS:
                if lines and lines[-1] != "":
                    lines.append("")

            if local in USLM_TEXT_TAGS:
                # For structural containers, collect direct text then recurse into children
                if local in USLM_BLOCK_TAGS:
                    direct_text = (elem.text or "").strip()
                    if direct_text:
                        lines.append(direct_text)
                    for child in elem:
                        walk(child, depth + 1)
                    if lines and lines[-1] != "":
                        lines.append("")
                    return
                else:
                    text = _collect_text(elem)
                    if text:
                        lines.append(text)
                    return

            # Not a specifically targeted tag — recurse into children
            for child in elem:
                walk(child, depth + 1)

        walk(root)

        # Remove consecutive blank lines
        result_lines: List[str] = []
        for line in lines:
            if line == "" and result_lines and result_lines[-1] == "":
                continue
            result_lines.append(line)

        return "\n".join(result_lines).strip()

    def _extract_generic(root: ET.Element) -> str:
        """Fallback: collect all text nodes, strip tags."""
        parts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                parts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                parts.append(elem.tail.strip())
        return " ".join(parts)

    try:
        tree = ET.parse(str(path))
    except ET.ParseError:
        # Not valid XML — return raw text content
        return path.read_text(encoding="utf-8", errors="ignore")

    root = tree.getroot()

    if _is_uslm(root):
        return _extract_uslm(root)
    else:
        return _extract_generic(root)
