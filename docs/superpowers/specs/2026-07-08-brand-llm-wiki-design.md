# Brand LLM-WiKi Design

## Goal

Turn brand manuals into an agent-readable Wiki so Brand Agent can search, read, and traverse brand knowledge instead of receiving one full distilled document.

## Architecture

Brand Wiki data lives under `backend/data/brand_wiki/<brand>/`. A compile script creates one folder per brand with `_index.md`, `_agent-guide.md`, section pages, and `error_book.yaml`. Runtime code exposes `brand_wiki_search`, `brand_wiki_read`, and `brand_wiki_context_for_task`; Brand Agent uses this curated context during requirement extraction.

## Wiki Shape

Each brand folder contains:

- `_index.md`: brand overview and wikilinks to topic pages.
- `brand-positioning.md`: positioning, audience, and core value.
- `tone-style.md`: tone, creative texture, visual style, and language style.
- `collaboration-preferences.md`: preferred narrative, scenes, creator behavior, and content structure.
- `prohibited-expressions.md`: hard constraints, risky claims, and unacceptable styles.
- `differentiation.md`: brand distinctions and strategic contrast.
- `source-digests.md`: source summary and provenance notes.
- `error_book.yaml`: structural validation notes for future correction.

## Runtime Behavior

`brand_wiki_search(query, brand_identifier, brief_text)` selects a brand, scans the brand page index, and returns ranked candidate pages with snippets. `brand_wiki_read(paths)` reads specific pages and includes wikilinks for traversal. `brand_wiki_context_for_task` performs a small query set for Brand Agent, deduplicates pages, and returns a compact Markdown context block.

## Fallbacks

If brand Wiki pages do not exist, runtime falls back to the current distilled/raw manual behavior. This keeps existing projects usable before compilation has been run.

## Testing

Tests cover brand matching, page search, page read behavior, task context assembly, and fallback to distilled manuals.
