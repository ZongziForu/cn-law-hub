"""File I/O helpers for structured data."""

import csv
import json
from datetime import datetime
from pathlib import Path


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}__{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def render_markdown_report(title: str, sections: list) -> str:
    lines = [f"# {title}", ""]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.extend([f"生成时间：{generated_at}", ""])
    for heading, payload in sections:
        lines.append(f"## {heading}")
        if isinstance(payload, str):
            lines.extend([payload, ""])
            continue
        if isinstance(payload, dict):
            for key, value in payload.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
            continue
        if isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                for row in payload:
                    name = row.get("name", "")
                    count = row.get("count", "")
                    extra = row.get("extra", "")
                    text = f"- {name}: {count}"
                    if extra:
                        text += f" ({extra})"
                    lines.append(text)
            else:
                for row in payload:
                    lines.append(f"- {row}")
            lines.append("")
            continue
    return "\n".join(lines).rstrip() + "\n"
