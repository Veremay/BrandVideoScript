from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BRAND_WIKI_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "brand_wiki"

# Common noise tokens to strip when extracting brand name from filename.
_STRIP_SUFFIXES = ["品牌手册", "手册", "护肤品牌", "品牌", "护肤"]
_YEAR_PREFIX = re.compile(r"^\d+")


def _extract_brand_name(stem: str) -> str:
    """Extract the core brand name from a wiki filename stem.

    '2022观夏品牌手册' → '观夏'
    '2021谷雨护肤品牌手册' → '谷雨'
    """
    name = _YEAR_PREFIX.sub("", stem).strip()
    for suffix in _STRIP_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def _find_wiki_file(brief_text: str, brief_filename: str | None) -> Path | None:
    """Return the best-matching wiki file for the given brief, or None."""
    if not BRAND_WIKI_DIR.exists():
        return None

    wiki_files = list(BRAND_WIKI_DIR.glob("*.md"))
    if not wiki_files:
        return None

    search_corpus = f"{brief_filename or ''} {brief_text}".lower()

    for wiki_file in wiki_files:
        brand_name = _extract_brand_name(wiki_file.stem)
        # Primary match: extracted brand name appears anywhere in brief
        if brand_name and brand_name in search_corpus:
            return wiki_file
        # Fallback: full filename stem contains the search corpus (rare edge case)
        if wiki_file.stem.lower() in search_corpus:
            return wiki_file

    return None


async def brand_wiki_lookup(
    brand_identifier: str | None = None,
    *,
    brief_text: str | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Return the full text of the matching brand wiki file.

    Searches `backend/data/brand_wiki/` for a Markdown file whose extracted
    brand name appears in *brief_text* or *brand_identifier* (brief filename).
    Falls back gracefully when no match is found.

    The `mock` parameter is kept for backward compatibility but ignored—
    file reads need no network and are always performed.
    """
    wiki_file = _find_wiki_file(brief_text or "", brand_identifier)

    if wiki_file is not None:
        brand_name = _extract_brand_name(wiki_file.stem)

        # Prefer the distilled version (compact, structured for LLM consumption).
        # Fall back to raw file if distillation hasn't been run yet.
        distilled = wiki_file.with_suffix(".distilled.md")
        if distilled.exists():
            text = distilled.read_text(encoding="utf-8")
            source = distilled.name
        else:
            import warnings
            warnings.warn(
                f"Brand wiki '{wiki_file.name}' has no distilled version. "
                "Run: uv run python scripts/distill_brand_wiki.py",
                stacklevel=2,
            )
            text = wiki_file.read_text(encoding="utf-8")
            source = wiki_file.name

        return {
            "brand_name": brand_name,
            "source": source,
            "full_text": text,
            "found": True,
            "distilled": distilled.exists(),
        }

    return {
        "brand_name": brand_identifier,
        "source": None,
        "full_text": "",
        "found": False,
        "distilled": False,
    }
