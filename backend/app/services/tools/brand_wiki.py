from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BRAND_WIKI_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "brand_wiki"
BRAND_WIKI_ROOT_DIR = BRAND_WIKI_DIR

_STRIP_SUFFIXES = [
    "品牌手册",
    "护肤品牌手册",
    "护肤品牌",
    "手册",
    "品牌",
    "BrandManual",
    "Manual",
]
_YEAR_PREFIX = re.compile(r"^\d+")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", re.IGNORECASE)
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _extract_brand_name(stem: str) -> str:
    """Extract the core brand name from a manual filename or brand folder."""
    name = _YEAR_PREFIX.sub("", stem).strip()
    for suffix in sorted(_STRIP_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name or stem.strip()


def _find_wiki_file(brief_text: str, brief_filename: str | None) -> Path | None:
    """Return the best-matching raw wiki file for the given brief, or None."""
    if not BRAND_WIKI_DIR.exists():
        return None

    wiki_files = [
        path
        for path in sorted(BRAND_WIKI_DIR.glob("*.md"))
        if ".distilled" not in path.stem
    ]
    if not wiki_files:
        return None

    search_corpus = f"{brief_filename or ''} {brief_text}".lower()

    for wiki_file in wiki_files:
        brand_name = _extract_brand_name(wiki_file.stem)
        if brand_name and brand_name.lower() in search_corpus:
            return wiki_file
        if wiki_file.stem.lower() in search_corpus:
            return wiki_file

    return None


def _brand_dirs() -> list[Path]:
    if not BRAND_WIKI_ROOT_DIR.exists():
        return []
    return [
        path
        for path in sorted(BRAND_WIKI_ROOT_DIR.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]


def _find_brand_dir(brand_identifier: str | None, brief_text: str | None = None) -> Path | None:
    search_corpus = f"{brand_identifier or ''} {brief_text or ''}".lower()
    for brand_dir in _brand_dirs():
        brand_name = _extract_brand_name(brand_dir.name)
        candidates = {brand_dir.name.lower(), brand_name.lower()}
        if any(candidate and candidate in search_corpus for candidate in candidates):
            return brand_dir

    raw = _find_wiki_file(brief_text or "", brand_identifier)
    if raw is not None:
        raw_brand = _extract_brand_name(raw.stem).lower()
        for brand_dir in _brand_dirs():
            if _extract_brand_name(brand_dir.name).lower() == raw_brand:
                return brand_dir

    return None


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def _page_score(query_tokens: list[str], page_path: Path, content: str) -> int:
    haystacks = [
        page_path.stem.lower().replace("-", " "),
        content[:500].lower(),
        content.lower(),
    ]
    score = 0
    for token in query_tokens:
        if token in haystacks[0]:
            score += 8
        if token in haystacks[1]:
            score += 4
        if token in haystacks[2]:
            score += 1
    return score


def _snippet(content: str, query_tokens: list[str], limit: int = 220) -> str:
    clean = re.sub(r"\s+", " ", content).strip()
    if len(clean) <= limit:
        return clean
    lower = clean.lower()
    hit_positions = [lower.find(token) for token in query_tokens if lower.find(token) >= 0]
    start = max(0, min(hit_positions) - 60) if hit_positions else 0
    return clean[start : start + limit].strip()


def _safe_wiki_page(path: str) -> Path | None:
    parts = Path(path).parts
    if len(parts) < 2:
        return None
    brand_name = parts[0]
    page_parts = list(parts[1:])
    if any(part in {"", ".", ".."} or part.startswith(".") for part in page_parts):
        return None
    if not page_parts[-1].endswith(".md"):
        page_parts[-1] = f"{page_parts[-1]}.md"
    candidate = BRAND_WIKI_ROOT_DIR / brand_name
    for part in page_parts:
        candidate = candidate / part
    try:
        candidate.relative_to(BRAND_WIKI_ROOT_DIR)
    except ValueError:
        return None
    return candidate if candidate.exists() and candidate.is_file() else None


async def brand_wiki_search(
    query: str,
    brand_identifier: str | None = None,
    *,
    brief_text: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search brand Wiki pages by brand and query."""
    brand_dir = _find_brand_dir(brand_identifier, brief_text)
    if brand_dir is None:
        return {
            "brand_name": brand_identifier,
            "found": False,
            "results": [],
            "query": query,
        }

    query_tokens = _tokens(query)
    scored: list[tuple[int, Path, str]] = []
    for page in sorted(brand_dir.rglob("*.md")):
        if page.name == "error_book.yaml":
            continue
        content = page.read_text(encoding="utf-8")
        score = _page_score(query_tokens, page, content)
        if page.name == "_index.md":
            score += 1
        if score > 0:
            scored.append((score, page, content))

    scored.sort(key=lambda item: (-item[0], item[1].name))
    results = [
        {
            "brand_name": brand_dir.name,
            "page_id": page.relative_to(brand_dir).with_suffix("").as_posix(),
            "title": _page_title(content, page),
            "path": f"{brand_dir.name}/{page.relative_to(brand_dir).as_posix()}",
            "score": score,
            "snippet": _snippet(content, query_tokens),
        }
        for score, page, content in scored[:limit]
    ]

    return {
        "brand_name": brand_dir.name,
        "found": bool(results),
        "results": results,
        "query": query,
    }


def _page_title(content: str, page: Path) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return page.stem.replace("-", " ").title()


async def brand_wiki_read(paths: list[str]) -> dict[str, Any]:
    """Read brand Wiki pages by `Brand/page.md` path."""
    pages: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_path in paths:
        page = _safe_wiki_page(raw_path)
        if page is None:
            missing.append(raw_path)
            continue
        content = page.read_text(encoding="utf-8")
        brand_name = page.parent.name
        brand_dir = page
        while brand_dir.parent != BRAND_WIKI_ROOT_DIR:
            brand_dir = brand_dir.parent
        brand_name = brand_dir.name
        relative = page.relative_to(brand_dir).as_posix()
        pages.append(
            {
                "brand_name": brand_name,
                "page_id": page.relative_to(brand_dir).with_suffix("").as_posix(),
                "path": f"{brand_name}/{relative}",
                "title": _page_title(content, page),
                "wikilinks": _WIKILINK_RE.findall(content),
                "content": content,
            }
        )
    return {"pages": pages, "missing": missing}


async def brand_wiki_context_for_task(
    *,
    brand_identifier: str | None,
    brief_text: str | None,
    task: str,
    max_pages: int = 4,
) -> dict[str, Any]:
    """Build compact task-specific Wiki context through search and read calls."""
    task_queries = {
        "extract_requirements": [
            brief_text or "",
            "brand positioning tone style collaboration preferences prohibited expressions constraints",
            "forbidden avoid risk hard sell compliance",
        ],
        "issue_response": [
            brief_text or "",
            "brand position argument evidence constraints tone",
        ],
    }
    queries = [q for q in task_queries.get(task, [brief_text or "", task]) if q.strip()]

    selected_paths: list[str] = []
    search_lines: list[str] = ["## Brand Wiki Search"]
    for query in queries:
        result = await brand_wiki_search(
            query,
            brand_identifier=brand_identifier,
            brief_text=brief_text,
            limit=max_pages,
        )
        for item in result.get("results", []):
            path = str(item["path"])
            search_lines.append(f"- {path}: {item['snippet']}")
            if path not in selected_paths:
                selected_paths.append(path)
            if len(selected_paths) >= max_pages:
                break
        if len(selected_paths) >= max_pages:
            break

    if selected_paths:
        read = await brand_wiki_read(selected_paths)
        page_blocks = ["## Brand Wiki Pages"]
        for page in read["pages"]:
            page_blocks.append(f"### {page['path']}\n{page['content']}")
        return {
            "brand_name": read["pages"][0]["brand_name"] if read["pages"] else brand_identifier,
            "found": bool(read["pages"]),
            "source": "brand_wiki",
            "context": "\n".join(search_lines + [""] + page_blocks),
            "paths": selected_paths,
        }

    fallback = await brand_wiki_lookup(brand_identifier, brief_text=brief_text)
    if fallback.get("found"):
        return {
            "brand_name": fallback.get("brand_name"),
            "found": True,
            "source": fallback.get("source"),
            "context": (
                "## Brand Wiki Fallback\n"
                f"source={fallback.get('source')}\n\n{fallback.get('full_text')}"
            ),
            "paths": [],
        }

    return {
        "brand_name": brand_identifier,
        "found": False,
        "source": None,
        "context": "## Brand Wiki\n（未找到对应品牌知识库）",
        "paths": [],
    }


async def brand_wiki_lookup(
    brand_identifier: str | None = None,
    *,
    brief_text: str | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Return the full text of the matching distilled/raw brand wiki file.

    `mock` is kept for backward compatibility. File reads are deterministic and
    do not require network access.
    """
    del mock
    wiki_file = _find_wiki_file(brief_text or "", brand_identifier)

    if wiki_file is not None:
        brand_name = _extract_brand_name(wiki_file.stem)
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
