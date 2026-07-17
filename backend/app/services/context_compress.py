from __future__ import annotations

from app.core.config import get_settings
from app.services.llm_client import LLMClient
from app.services.pipeline_log import log_step
from app.services.prompt_loader import load_prompt
from app.services.token_estimate import estimate_messages_tokens

HISTORY_TOKEN_LIMIT = 32_000
KEEP_RECENT_MESSAGES = 12  # ~6 turns


def _format_transcript(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _hard_truncate(messages: list[dict[str, str]], keep_recent: int) -> list[dict[str, str]]:
    if len(messages) <= keep_recent:
        return list(messages)
    return list(messages[-keep_recent:])


def _summary_prefix() -> str:
    return "[Conversation summary]" if get_settings().prompt_language == "en" else "[对话摘要]"


def _compress_user_prompt(transcript: str) -> str:
    if get_settings().prompt_language == "en":
        return (
            "Compress the earlier conversation below into a concise summary. "
            "Keep goals, constraints, agreements, and open questions. "
            "Output summary text only.\n\n"
            f"{transcript}"
        )
    return (
        "请将以下更早的对话压缩为一段简洁摘要，保留目标、约束、已达成共识与未决问题。"
        "只输出摘要正文，不要标题或解释。\n\n"
        f"{transcript}"
    )


async def maybe_compress_history(
    messages: list[dict[str, str]],
    *,
    llm: LLMClient | None = None,
    token_limit: int = HISTORY_TOKEN_LIMIT,
    keep_recent: int = KEEP_RECENT_MESSAGES,
) -> list[dict[str, str]]:
    """If chat history exceeds token_limit, summarize older turns via a compress agent.

    System prompt and script are never passed here — caller keeps those separate.
    Compression is ephemeral (does not mutate Mongo). On failure, hard-truncate to recent.
    """
    if not messages:
        return []

    total = estimate_messages_tokens(messages)
    if total <= token_limit:
        return list(messages)

    keep_n = min(keep_recent, len(messages))
    recent = list(messages[-keep_n:])
    older = list(messages[:-keep_n]) if len(messages) > keep_n else []
    if not older:
        return recent

    client = llm or LLMClient()
    log_step(
        "vanilla.context_compress",
        phase="IN",
        history_tokens=total,
        token_limit=token_limit,
        older_messages=len(older),
        recent_messages=len(recent),
    )

    try:
        if not client.settings.siliconflow_api_key:
            raise RuntimeError("missing API key for context compress")

        system = load_prompt("context_compress_agent.md")
        transcript = _format_transcript(older)
        response = await client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _compress_user_prompt(transcript)},
            ],
            task_type="vanilla_context_compress",
            stream=False,
            mock=False,
        )
        summary = client._extract_message_content(response).strip()
        if not summary:
            raise ValueError("empty compress summary")

        summary_msg: dict[str, str] = {
            "role": "user",
            "content": f"{_summary_prefix()}\n{summary}",
        }
        result = [summary_msg, *recent]
        log_step(
            "vanilla.context_compress",
            phase="OUT",
            source="llm",
            summary_tokens=estimate_messages_tokens([summary_msg]),
            result_messages=len(result),
        )
        return result
    except Exception as exc:
        truncated = _hard_truncate(messages, keep_n)
        log_step(
            "vanilla.context_compress",
            phase="OUT",
            source="fallback_truncate",
            error=f"{type(exc).__name__}: {exc}",
            result_messages=len(truncated),
        )
        return truncated
