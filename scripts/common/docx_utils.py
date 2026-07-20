"""DOCX parsing and Chinese law article extraction utilities."""

import re
import subprocess
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET


def extract_paragraphs_from_docx(content: bytes) -> list:
    """Extract text paragraphs. Supports .docx (ZIP) and .doc (OLE) formats."""
    if content[:4] == b"PK\x03\x04":  # ZIP = DOCX
        with zipfile.ZipFile(BytesIO(content), "r") as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        return [
            "".join(t.text for t in p.iter(f"{W}t") if t.text)
            for p in tree.iter(f"{W}p")
            if any(t.text for t in p.iter(f"{W}t"))
        ]

    # Old .doc format - try antiword or catdoc
    for tool in ["antiword", "catdoc"]:
        try:
            result = subprocess.run(
                [tool, "-"], input=content, capture_output=True, timeout=30
            )
            if result.returncode == 0:
                text = result.stdout.decode("utf-8", errors="replace")
                if text.strip():
                    return [line for line in text.split("\n") if line.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    raise RuntimeError(
        "File is in old .doc format (not .docx) and no conversion tool found. "
        "Install antiword or catdoc: apt-get install antiword catdoc"
    )


def is_article_line(line: str) -> bool:
    return bool(re.match(r"^第[一二三四五六七八九十百千万零\d]+条", line.strip()))


def extract_article_number(line: str) -> str:
    m = re.match(r"(第[一二三四五六七八九十百千万零\d]+条)", line.strip())
    return m.group(1) if m else line[:20]


def split_into_articles(paragraphs: list) -> list:
    articles = []
    current_num = "题注/前言"
    current_lines = []
    for line in paragraphs:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if is_article_line(line_stripped):
            if current_lines:
                articles.append((current_num, "\n".join(current_lines)))
            current_num = extract_article_number(line_stripped)
            current_lines = [line_stripped]
        else:
            current_lines.append(line_stripped)
    if current_lines:
        articles.append((current_num, "\n".join(current_lines)))
    return articles


def match_article_query(query: str, article_number: str) -> bool:
    from .chinese_numerals import int_to_chinese

    query = query.strip()
    if query in article_number:
        return True
    m = re.match(r"^第(\d+)条$", query)
    if m:
        n = int(m.group(1))
        return (
            f"第{int_to_chinese(n)}条" == article_number or f"第{n}条" == article_number
        )
    if re.match(r"^\d+$", query):
        n = int(query)
        return f"第{int_to_chinese(n)}条" == article_number
    if re.match(r"^[一二三四五六七八九十百千万零]+$", query):
        return f"第{query}条" == article_number
    return False
