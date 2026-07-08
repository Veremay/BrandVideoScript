"""
将 data/brand_wiki/ 中的品牌手册蒸馏为结构化摘要，供 Brand Agent 使用。

用法：
    uv run python scripts/distill_brand_wiki.py                  # 处理所有未蒸馏手册
    uv run python scripts/distill_brand_wiki.py --force           # 重新蒸馏所有手册
    uv run python scripts/distill_brand_wiki.py --file 2022观夏品牌手册.md
"""
from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WIKI_DIR = Path(__file__).resolve().parents[1] / "data" / "brand_wiki"
WIKI_OUTPUT_DIR = WIKI_DIR

_YEAR_PREFIX = re.compile(r"^\d+")
_STRIP_SUFFIXES = [
    "品牌手册",
    "护肤品牌手册",
    "护肤品牌",
    "手册",
    "品牌",
    "BrandManual",
    "Manual",
]

_TOPIC_PAGES = [
    (
        "brand-positioning",
        "Brand Positioning",
        ["position", "positioning", "定位", "价值", "受众", "人群", "core", "品牌"],
    ),
    (
        "tone-style",
        "Tone And Style",
        ["tone", "style", "调性", "风格", "视觉", "语言", "气质", "氛围"],
    ),
    (
        "collaboration-preferences",
        "Collaboration Preferences",
        ["collaboration", "creator", "content", "scene", "合作", "达人", "内容", "场景", "叙事"],
    ),
    (
        "prohibited-expressions",
        "Prohibited Expressions",
        ["forbidden", "avoid", "risk", "禁止", "避免", "不得", "不能", "红线", "风险", "hard-sell"],
    ),
    (
        "differentiation",
        "Differentiation",
        ["different", "differentiation", "差异", "独特", "区别", "竞品"],
    ),
    (
        "source-digests",
        "Source Digests",
        ["source", "manual", "来源", "手册", "原文", "brief"],
    ),
]


def _extract_brand_name(stem: str) -> str:
    name = _YEAR_PREFIX.sub("", stem).strip()
    for suffix in sorted(_STRIP_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name or stem.strip()


def _topic_excerpt(text: str, keywords: list[str], *, fallback_chars: int = 900) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(keyword in lower for keyword in lowered_keywords):
            selected.extend(lines[max(0, index - 1) : min(len(lines), index + 3)])

    deduped: list[str] = []
    for line in selected:
        if line not in deduped:
            deduped.append(line)

    if deduped:
        return "\n".join(f"- {line}" for line in deduped)[:1600]

    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:fallback_chars] if clean else "（手册未说明）"


def compile_manual_to_wiki(
    wiki_file: Path,
    *,
    output_root: Path | None = None,
    force: bool = True,
) -> dict[str, object]:
    """Compile one raw brand manual into linked Markdown Wiki pages."""
    if ".distilled" in wiki_file.stem:
        raise ValueError("compile_manual_to_wiki expects a raw manual, not a distilled file")
    if not wiki_file.exists():
        raise FileNotFoundError(wiki_file)

    output_root = output_root or WIKI_OUTPUT_DIR
    brand_name = _extract_brand_name(wiki_file.stem)
    brand_dir = output_root / brand_name
    brand_dir.mkdir(parents=True, exist_ok=True)

    source_text = wiki_file.read_text(encoding="utf-8")
    page_ids = [page_id for page_id, _, _ in _TOPIC_PAGES]

    index_lines = [
        f"# {brand_name} Brand Wiki",
        "",
        f"- source: {wiki_file.name}",
        "- format: brand wiki",
        "",
        "## Pages",
        *[f"- [[{page_id}]]" for page_id in page_ids],
        "",
        "## Traversal Notes",
        "- Start from positioning, then inspect tone/style, collaboration preferences, and prohibited expressions before giving brand advice.",
    ]
    (brand_dir / "_index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    written = ["_index.md"]
    for page_id, title, keywords in _TOPIC_PAGES:
        excerpt = _topic_excerpt(source_text, keywords)
        sibling_links = " ".join(f"[[{other}]]" for other in page_ids if other != page_id)
        page_lines = [
            f"# {title}",
            "",
            f"brand: {brand_name}",
            f"source_refs: {wiki_file.name}",
            f"aliases: {', '.join(keywords[:6])}",
            "",
            "## Knowledge",
            excerpt,
            "",
            "## Related",
            sibling_links,
            "",
        ]
        path = brand_dir / f"{page_id}.md"
        if force or not path.exists():
            path.write_text("\n".join(page_lines), encoding="utf-8")
        written.append(path.name)

    error_book = brand_dir / "error_book.yaml"
    if force or not error_book.exists():
        error_book.write_text(
            "version: 1\n"
            "entries: []\n"
            "notes:\n"
            "  - deterministic compiler created initial linked Wiki pages\n",
            encoding="utf-8",
        )

    return {
        "brand_name": brand_name,
        "brand_dir": str(brand_dir),
        "pages": written,
    }


_SECTION_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_GENERATED_WIKI_STEMS = {
    "_index",
    "_agent-guide",
    "brand-positioning",
    "tone-style",
    "collaboration-preferences",
    "prohibited-expressions",
    "differentiation",
    "source-digests",
}
_AGENT_NAV_TOPICS: dict[str, list[str]] = {
    "voice_and_personality": [
        "voice",
        "writing",
        "narrative",
        "personality",
        "principles",
        "inclusive",
        "quirky",
        "fun",
        "tone",
        "品牌",
        "理念",
        "东方",
        "生活方式",
        "调性",
        "美学",
    ],
    "messaging_and_copy": [
        "sample messaging",
        "messaging",
        "tagline",
        "cta",
        "description",
        "press",
        "copy",
        "介绍",
        "表达",
        "文案",
        "故事",
    ],
    "audiences_and_motivation": [
        "audience",
        "consumers",
        "learners",
        "everyone",
        "motivation",
        "inclusive",
        "用户",
        "消费者",
        "人群",
        "场景",
        "生活",
    ],
    "culture_and_operating_principles": [
        "principle",
        "long view",
        "raise the bar",
        "ship it",
        "show don't tell",
        "green machine",
        "合作",
        "购买",
        "线下",
        "工艺",
        "原料",
        "调香",
        "产品",
        "系列",
    ],
}


def _slugify(text: str, *, fallback: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower(), flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-_")
    return slug or fallback


def _source_group_id(source_file: Path) -> str:
    stem = source_file.stem.lower()
    if "handbook" in stem:
        return "handbook"
    if "guideline" in stem:
        return "guidelines"
    if "manual" in stem or "手册" in source_file.stem:
        return "manual"
    return _slugify(source_file.stem, fallback="source")


def _is_source_markdown(path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    if ".distilled" in path.stem:
        return False
    return path.stem not in _GENERATED_WIKI_STEMS


def _split_markdown_sections(text: str, *, fallback_title: str) -> list[dict[str, str]]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [{"title": fallback_title, "content": text.strip()}]

    sections: list[dict[str, str]] = []
    preface = text[: matches[0].start()].strip()
    if preface:
        sections.append({"title": "Overview", "content": preface})

    for index, match in enumerate(matches):
        title = match.group(2).strip().strip("#").strip()
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append({"title": title, "content": text[match.end() : next_start].strip()})
    return sections


def _write_section_pages(
    *,
    brand_dir: Path,
    brand_name: str,
    source_file: Path,
    group_id: str,
    source_text: str,
) -> list[dict[str, str]]:
    group_dir = brand_dir / group_id
    group_dir.mkdir(parents=True, exist_ok=True)

    sections = _split_markdown_sections(source_text, fallback_title=source_file.stem)
    used_slugs: set[str] = set()
    pages: list[dict[str, str]] = []
    for index, section in enumerate(sections, start=1):
        slug = _slugify(section["title"], fallback=f"section-{index}")
        original_slug = slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{original_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        relative_path = f"{group_id}/{slug}.md"
        page_lines = [
            f"# {section['title']}",
            "",
            f"brand: {brand_name}",
            f"source_refs: {source_file.name}",
            f"source_section: {section['title']}",
            "",
            "## Source Content",
            section["content"] or "（本章节无正文）",
            "",
        ]
        output_path = brand_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(page_lines), encoding="utf-8")
        pages.append(
            {
                "title": section["title"],
                "path": relative_path,
                "source": source_file.name,
                "group": group_id,
            }
        )
    return pages


def _split_markdown_sections(text: str, *, fallback_title: str) -> list[dict[str, object]]:
    matches = list(_SECTION_HEADING_RE.finditer(text))
    if not matches:
        return [{"title": fallback_title, "content": text.strip(), "level": 1, "has_children": False}]

    sections: list[dict[str, object]] = []
    preface = text[: matches[0].start()].strip()
    if preface:
        sections.append({"title": "Overview", "content": preface, "level": 1, "has_children": False})

    for index, match in enumerate(matches):
        title = match.group(2).strip().strip("#").strip()
        level = len(match.group(1))
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        has_children = False
        for later in matches[index + 1 :]:
            later_level = len(later.group(1))
            if later_level <= level:
                break
            has_children = True
            break
        sections.append(
            {
                "title": title,
                "content": text[match.end() : next_start].strip(),
                "level": level,
                "has_children": has_children,
            }
        )
    return sections


def _infer_page_tags(title: str, content: str) -> list[str]:
    haystack = f"{title}\n{content}".lower()
    return [
        topic
        for topic, keywords in _AGENT_NAV_TOPICS.items()
        if any(keyword in haystack for keyword in keywords)
    ]


def _write_section_pages(
    *,
    brand_dir: Path,
    brand_name: str,
    source_file: Path,
    group_id: str,
    source_text: str,
) -> list[dict[str, str]]:
    group_dir = brand_dir / group_id
    group_dir.mkdir(parents=True, exist_ok=True)

    sections = _split_markdown_sections(source_text, fallback_title=source_file.stem)
    used_paths: set[str] = set()
    pages: list[dict[str, str]] = []
    current_h2_prefix: str | None = None

    for index, section in enumerate(sections, start=1):
        title = str(section["title"])
        content = str(section["content"])
        level = int(section["level"])
        has_children = bool(section["has_children"])
        slug = _slugify(title, fallback=f"section-{index}")

        if level == 3 and current_h2_prefix:
            base_relative = f"{current_h2_prefix}/{slug}.md"
        elif level == 2 and has_children:
            base_relative = f"{group_id}/{slug}/index.md"
            current_h2_prefix = f"{group_id}/{slug}"
        else:
            base_relative = f"{group_id}/{slug}.md"
            if level == 2:
                current_h2_prefix = f"{group_id}/{slug}"

        relative_path = base_relative
        suffix = 2
        while relative_path in used_paths:
            stem = base_relative.removesuffix(".md")
            if stem.endswith("/index"):
                stem = stem.removesuffix("/index")
                relative_path = f"{stem}-{suffix}/index.md"
                if level == 2:
                    current_h2_prefix = f"{stem}-{suffix}"
            else:
                relative_path = f"{stem}-{suffix}.md"
            suffix += 1
        used_paths.add(relative_path)

        tags = _infer_page_tags(title, content)
        page_lines = [
            f"# {title}",
            "",
            f"brand: {brand_name}",
            f"source_refs: {source_file.name}",
            f"source_section: {title}",
            f"inferred_tags: {', '.join(tags) if tags else 'none'}",
            "",
            "## Source Content",
            content or "（本章节无正文）",
            "",
        ]
        output_path = brand_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(page_lines), encoding="utf-8")
        pages.append(
            {
                "title": title,
                "path": relative_path,
                "source": source_file.name,
                "group": group_id,
                "content": content,
                "tags": ",".join(tags),
            }
        )
    return pages


def _write_agent_guide(brand_dir: Path, pages: list[dict[str, str]]) -> None:
    lines = [
        "# Agent Guide",
        "",
        "This file is an inferred navigation layer. Use it to choose original section pages, not as a source of brand facts.",
        "",
        "## Inferred Topic Navigation",
    ]
    for topic in _AGENT_NAV_TOPICS:
        matches = [page for page in pages if topic in page.get("tags", "").split(",")][:10]
        if not matches:
            continue
        lines.extend(["", f"### {topic}"])
        for page in matches:
            lines.append(f"- [[{page['path'].removesuffix('.md')}]] - {page['title']}")
    (brand_dir / "_agent-guide.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_brand_index(
    *,
    brand_dir: Path,
    brand_name: str,
    source_files: list[Path],
    pages: list[dict[str, str]],
) -> None:
    lines = [
        f"# {brand_name} Brand Wiki",
        "",
        "- format: section-faithful brand wiki",
        "- compilation: source Markdown headings are preserved as Wiki pages",
        "",
        "## Sources",
        *[f"- {source.name}" for source in source_files],
        "",
        "## Pages",
        "",
        "- [[_agent-guide]] - inferred navigation for agents",
    ]
    current_group = ""
    for page in pages:
        if page["group"] != current_group:
            current_group = page["group"]
            lines.extend(["", f"### {current_group}"])
        lines.append(f"- [[{page['path'].removesuffix('.md')}]] - {page['title']}")

    lines.extend(
        [
            "",
            "## Traversal Notes",
            "- Search and read the original section pages that match the current question.",
            "- Do not infer missing brand rules from section titles alone.",
        ]
    )
    (brand_dir / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_agent_guide(brand_dir, pages)


def _write_error_book(brand_dir: Path) -> None:
    (brand_dir / "error_book.yaml").write_text(
        "version: 1\n"
        "entries: []\n"
        "notes:\n"
        "  - section-faithful compiler created linked Wiki pages from source headings\n",
        encoding="utf-8",
    )


def compile_manual_to_wiki(
    wiki_file: Path,
    *,
    output_root: Path | None = None,
    force: bool = True,
) -> dict[str, object]:
    """Compile one raw brand manual into source-section Wiki pages."""
    if ".distilled" in wiki_file.stem:
        raise ValueError("compile_manual_to_wiki expects a raw manual, not a distilled file")
    if not wiki_file.exists():
        raise FileNotFoundError(wiki_file)

    output_root = output_root or WIKI_OUTPUT_DIR
    brand_name = _extract_brand_name(wiki_file.stem)
    brand_dir = output_root / brand_name
    source_text = wiki_file.read_text(encoding="utf-8")
    if force and brand_dir.exists():
        shutil.rmtree(brand_dir)
    brand_dir.mkdir(parents=True, exist_ok=True)
    if wiki_file.parent.resolve() == brand_dir.resolve():
        (brand_dir / wiki_file.name).write_text(source_text, encoding="utf-8")

    pages = _write_section_pages(
        brand_dir=brand_dir,
        brand_name=brand_name,
        source_file=wiki_file,
        group_id=_source_group_id(wiki_file),
        source_text=source_text,
    )
    _write_brand_index(brand_dir=brand_dir, brand_name=brand_name, source_files=[wiki_file], pages=pages)
    _write_error_book(brand_dir)

    return {
        "brand_name": brand_name,
        "brand_dir": str(brand_dir),
        "pages": ["_index.md", *[page["path"] for page in pages]],
    }


def compile_brand_directory_to_wiki(
    source_dir: Path,
    *,
    output_root: Path | None = None,
    force: bool = True,
) -> dict[str, object]:
    """Compile all Markdown files in a brand directory into one section Wiki."""
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(source_dir)

    source_files = [path for path in sorted(source_dir.glob("*.md")) if _is_source_markdown(path)]
    if not source_files:
        raise ValueError(f"No markdown source files found in {source_dir}")
    source_records = [
        {
            "path": path,
            "text": path.read_text(encoding="utf-8"),
        }
        for path in source_files
    ]

    output_root = output_root or WIKI_OUTPUT_DIR
    brand_name = _extract_brand_name(source_dir.name)
    brand_dir = output_root / brand_name
    if force and brand_dir.exists():
        shutil.rmtree(brand_dir)
    brand_dir.mkdir(parents=True, exist_ok=True)
    if source_dir.resolve() == brand_dir.resolve():
        for record in source_records:
            (brand_dir / record["path"].name).write_text(str(record["text"]), encoding="utf-8")

    pages: list[dict[str, str]] = []
    for record in source_records:
        source_file = record["path"]
        pages.extend(
            _write_section_pages(
                brand_dir=brand_dir,
                brand_name=brand_name,
                source_file=source_file,
                group_id=_source_group_id(source_file),
                source_text=str(record["text"]),
            )
        )
    _write_brand_index(brand_dir=brand_dir, brand_name=brand_name, source_files=source_files, pages=pages)
    _write_error_book(brand_dir)

    return {
        "brand_name": brand_name,
        "brand_dir": str(brand_dir),
        "pages": ["_index.md", *[page["path"] for page in pages]],
    }

DISTILL_SYSTEM_PROMPT = """\
你是一位品牌内容策略专家，专注于帮助视频内容创作者理解品牌要求。

你的任务是阅读品牌方提供的品牌手册，提炼出对视频内容创作**最关键的品牌信息**，\
输出一份结构化、简洁的品牌摘要，供 AI 助手在后续判断合作内容需求时使用。

输出格式严格遵循以下 Markdown 结构，每个部分用 ## 标题分隔：

## 品牌定位
（2-3句：品牌是什么、面向谁、核心价值主张）

## 调性与风格
（用短语列举，例如：克制留白、东方意境、生活化场景、避免夸张……）

## 内容合作偏好
（列举该品牌希望内容如何呈现：偏好什么叙事方式、场景、情绪……）

## 明确禁止事项
（列举内容红线：不得出现什么、不得使用什么风格……）

## 品牌差异化
（1-2句：该品牌与同类产品的本质差异，用于帮助创作者理解品牌底气）

要求：
- 总字数控制在 700 字以内
- 保留品牌手册中出现的关键词和标志性表达
- 不要添加手册中没有的信息
- 若某部分手册中无明确内容，写"（手册未说明）"
"""

DISTILL_USER_TEMPLATE = """\
以下是品牌手册原文，请按格式提炼：

{full_text}
"""


async def distill_one(wiki_file: Path, *, force: bool = False) -> None:
    distilled_path = wiki_file.with_suffix(".distilled.md")

    if distilled_path.exists() and not force:
        print(f"  [skip] {wiki_file.name} — 已有蒸馏版本")
        return

    print(f"  [distill] {wiki_file.name} …")
    full_text = wiki_file.read_text(encoding="utf-8")

    from app.services.llm_client import LLMClient  # noqa: PLC0415

    client = LLMClient()
    if not client.settings.siliconflow_api_key:
        print("  [error] 未配置 SILICONFLOW_API_KEY，无法蒸馏")
        return

    import httpx  # noqa: PLC0415
    from app.services.model_router import select_model  # noqa: PLC0415

    model = select_model("brand_analyze_brief", "high")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
            {"role": "user", "content": DISTILL_USER_TEMPLATE.format(full_text=full_text)},
        ],
        "temperature": 0.3,
        "top_p": 0.8,
        "max_tokens": 1200,
    }

    async with httpx.AsyncClient(
        base_url=client.settings.siliconflow_base_url,
        timeout=180,
    ) as http:
        response = await http.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {client.settings.siliconflow_api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        print(f"  [error] LLM 未返回内容：{data}")
        return

    content: str = choices[0].get("message", {}).get("content", "").strip()
    if not content:
        print("  [error] LLM 返回内容为空")
        return

    # Prepend a header so the file is self-describing
    brand_name = wiki_file.stem
    header = f"<!-- 蒸馏自：{wiki_file.name}，请勿手动编辑，使用 distill_brand_wiki.py --force 重新生成 -->\n\n"
    distilled_path.write_text(header + content, encoding="utf-8")
    print(f"  [ok]     → {distilled_path.name}  ({len(content)} 字)")


async def main() -> None:
    parser = argparse.ArgumentParser(description="蒸馏品牌手册为结构化摘要")
    parser.add_argument("--force", action="store_true", help="强制重新蒸馏所有手册")
    parser.add_argument("--file", metavar="FILENAME", help="只处理指定文件名")
    parser.add_argument("--compile-wiki", action="store_true", help="also compile manuals into linked Brand Wiki pages")
    parser.add_argument("--compile-only", action="store_true", help="skip LLM distillation and only compile linked Brand Wiki pages")
    args = parser.parse_args()

    if not WIKI_DIR.exists():
        print(f"[error] 目录不存在：{WIKI_DIR}")
        sys.exit(1)

    if args.file:
        targets = [WIKI_DIR / args.file]
        missing = [f for f in targets if not f.exists()]
        if missing:
            print(f"[error] 文件不存在：{missing[0]}")
            sys.exit(1)
    else:
        # Exclude already-distilled files and non-manual files
        targets = [
            f for f in sorted(WIKI_DIR.glob("*.md"))
            if ".distilled" not in f.stem
        ]

    if not targets:
        print("[info] 没有需要处理的文件")
        return

    print(f"\n处理 {len(targets)} 个手册文件：\n")
    for wiki_file in targets:
        if args.compile_only:
            if wiki_file.is_dir():
                result = compile_brand_directory_to_wiki(wiki_file, force=args.force)
            else:
                result = compile_manual_to_wiki(wiki_file, force=args.force)
            print(f"  [compile] {wiki_file.name} -> {result['brand_dir']}")
            continue

        await distill_one(wiki_file, force=args.force)
        if args.compile_wiki:
            result = compile_manual_to_wiki(wiki_file, force=args.force)
            print(f"  [compile] {wiki_file.name} -> {result['brand_dir']}")

    print("\n完成\n")


if __name__ == "__main__":
    asyncio.run(main())
