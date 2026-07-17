from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def estimate_tokens(text: str) -> int:
    """Rough token estimate for mixed CJK / Latin text (no tokenizer dependency).

    Heuristic: CJK characters ≈ 1 token each; remaining non-CJK text ≈ 4 chars / token.
    """
    if not text:
        return 0
    cjk_chars = len(_CJK_RE.findall(text))
    non_cjk_chars = len(text) - cjk_chars
    return cjk_chars + max(1, (non_cjk_chars + 3) // 4) if non_cjk_chars else cjk_chars


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(str(m.get("content") or "")) for m in messages)
