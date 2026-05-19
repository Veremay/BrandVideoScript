import json
import re
from pathlib import Path
from typing import Any


def _slugify_filename_stem(filename: str | None) -> str:
    if not filename:
        return "unknown-brand"
    stem = Path(filename).stem.lower().strip()
    stem = re.sub(r"[^\w\u4e00-\u9fff]+", "-", stem, flags=re.UNICODE)
    stem = stem.strip("-") or "unknown-brand"
    return stem[:80]


def find_brand_slug_from_wiki(wiki_root: Path, filename: str | None, brief_text: str) -> tuple[str, bool]:
    """Return (slug, matched_via_meta_aliases)."""
    brands = wiki_root / "brands"
    if not brands.is_dir():
        return _slugify_filename_stem(filename), False

    head = brief_text[:1200].lower()
    for child in sorted(brands.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        names: list[str] = []
        if meta.get("display_name"):
            names.append(str(meta["display_name"]).lower())
        for a in meta.get("aliases") or []:
            names.append(str(a).lower())
        for n in names:
            if n and n in head:
                return child.name, True

    return _slugify_filename_stem(filename), False


def extract_wiki_snippets(
    wiki_root: Path,
    brand_slug: str,
    brief_text: str,
    *,
    max_chunks: int = 8,
    chunk_chars: int = 450,
) -> list[dict[str, Any]]:
    handbook = wiki_root / "brands" / brand_slug / "handbook.md"
    if not handbook.is_file():
        return []

    text = handbook.read_text(encoding="utf-8", errors="replace")
    sections = re.split(r"(?m)^##\s+(.+)$", text)
    chunks: list[tuple[str, str]] = []
    preamble = sections[0].strip() if sections else ""
    if preamble:
        chunks.append(("(文档开头)", preamble[:2000]))
    i = 1
    while i + 1 < len(sections):
        title = sections[i].strip()
        body = sections[i + 1].strip()
        chunks.append((f"## {title}", body))
        i += 2

    brief_words = {w for w in re.split(r"\W+", brief_text.lower()) if len(w) > 2}
    scored: list[tuple[int, str, str]] = []
    for heading, body in chunks:
        blob = f"{heading}\n{body}".lower()
        score = sum(1 for w in brief_words if w in blob)
        scored.append((score, heading, body))

    scored.sort(key=lambda x: x[0], reverse=True)
    snippets: list[dict[str, Any]] = []
    rel_path = str(handbook.relative_to(wiki_root))
    for score, heading, body in scored[:max_chunks]:
        snippet = body[:chunk_chars].strip()
        if not snippet:
            continue
        snippets.append(
            {
                "path": rel_path,
                "heading": heading,
                "snippet": snippet,
                "score": score,
            }
        )
    return snippets
