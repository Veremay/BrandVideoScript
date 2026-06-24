"""Pipeline / agent / LLM step logging to console."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger("brandvideo.pipeline")

_STEP_MAX = 6000
_LLM_MAX = 50000


def setup_pipeline_logging() -> None:
    if logger.handlers:
        return
    level_name = os.getenv("PIPELINE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def _serialize(value: Any, *, max_len: int) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    else:
        text = str(value)
    if len(text) > max_len:
        return f"{text[:max_len]}\n... [truncated, total {len(text)} chars]"
    return text


def log_step(step: str, *, phase: str, **fields: Any) -> None:
    """Log a pipeline or agent step with labeled inputs/outputs."""
    lines = [f"{'=' * 60}", f"[{phase}] {step}"]
    for key, value in fields.items():
        if value is None or value == "" or value == {} or value == []:
            continue
        lines.append(f"--- {key} ---")
        lines.append(_serialize(value, max_len=_STEP_MAX))
    lines.append("=" * 60)
    logger.info("\n".join(lines))


def log_llm_request(
    *,
    task_type: str,
    model: str,
    messages: list[dict[str, str]],
    stream: bool = False,
    response_format: dict[str, Any] | None = None,
) -> None:
    lines = [
        f"{'~' * 60}",
        f"[LLM REQUEST] task={task_type} model={model} stream={stream}",
    ]
    if response_format:
        lines.append(f"response_format: {json.dumps(response_format, ensure_ascii=False)}")
    for index, message in enumerate(messages):
        role = message.get("role", "?")
        content = message.get("content", "")
        lines.append(f"--- message[{index}] role={role} ({len(content)} chars) ---")
        lines.append(_serialize(content, max_len=_LLM_MAX))
    lines.append("~" * 60)
    logger.info("\n".join(lines))


def log_llm_response(
    *,
    task_type: str,
    model: str,
    content: str,
    parsed_json: dict[str, Any] | None = None,
    extra: str | None = None,
) -> None:
    lines = [
        f"{'~' * 60}",
        f"[LLM RESPONSE] task={task_type} model={model}",
    ]
    if extra:
        lines.append(extra)
    lines.append(f"--- raw content ({len(content)} chars) ---")
    lines.append(_serialize(content, max_len=_LLM_MAX))
    if parsed_json is not None:
        lines.append("--- parsed JSON ---")
        lines.append(_serialize(parsed_json, max_len=_LLM_MAX))
    lines.append("~" * 60)
    logger.info("\n".join(lines))


def log_llm_mock(task_type: str, *, reason: str) -> None:
    logger.warning(f"[LLM MOCK] task={task_type} reason={reason}")


# ---------------------------------------------------------------------------
# Real-time stream echo
# Set LLM_STREAM_ECHO=0 to suppress token-by-token output (e.g. in CI).
# ---------------------------------------------------------------------------

_STREAM_ECHO = os.getenv("LLM_STREAM_ECHO", "1") != "0"


def log_llm_stream_start(task_type: str, model: str) -> None:
    if not _STREAM_ECHO:
        return
    sys.stdout.write(f"\n{'~' * 60}\n[LLM STREAM] task={task_type} model={model}\n")
    sys.stdout.flush()


def log_llm_stream_token(token: str) -> None:
    if not _STREAM_ECHO:
        return
    sys.stdout.write(token)
    sys.stdout.flush()


def log_llm_stream_end() -> None:
    if not _STREAM_ECHO:
        return
    sys.stdout.write(f"\n{'~' * 60}\n")
    sys.stdout.flush()
