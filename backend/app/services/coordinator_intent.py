"""Detect Coordinator user intent from natural language (MVP heuristics)."""

from __future__ import annotations

import re

# Requests for IBIS nodes/issues — not modification schemes.
_NODE_GENERATION_PATTERNS = (
    re.compile(r"生成.{0,12}(节点|node)", re.IGNORECASE),
    re.compile(r"(新增|添加|创建).{0,8}(节点|node)", re.IGNORECASE),
    re.compile(r"(update|create).{0,12}(graph\s+)?node", re.IGNORECASE),
)

_GENERATE_SCHEME_PATTERNS = (
    re.compile(r"生成.{0,16}(新|多方向|修改|修订)?方案", re.IGNORECASE),
    re.compile(r"(给|帮|请).{0,8}(我|咱|我们).{0,12}(生成|出|写|提供|给).{0,16}方案", re.IGNORECASE),
    re.compile(r"(重新|再).{0,6}生成.{0,12}方案", re.IGNORECASE),
    re.compile(r"新的?.{0,8}修改方案", re.IGNORECASE),
    re.compile(r"revision\s*proposals?", re.IGNORECASE),
    re.compile(
        r"(generate|create|draft).{0,24}(revision|modification).{0,12}(scheme|proposal)s?",
        re.IGNORECASE,
    ),
    re.compile(r"generate\s+(new\s+)?(revision\s+)?proposals?", re.IGNORECASE),
)


def wants_generate_modification_schemes(message: str, *, task_type: str | None = None) -> bool:
    if task_type == "generate_modification_schemes":
        return True
    text = (message or "").strip()
    if not text:
        return False
    if any(pattern.search(text) for pattern in _NODE_GENERATION_PATTERNS) and "方案" not in text:
        return False
    return any(pattern.search(text) for pattern in _GENERATE_SCHEME_PATTERNS)
