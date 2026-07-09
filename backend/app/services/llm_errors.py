from __future__ import annotations


class LLMInvocationError(Exception):
    """Raised when a configured LLM call fails and mock fallback must not be used."""

    def __init__(
        self,
        *,
        task_type: str,
        cause: Exception | None = None,
        message: str | None = None,
    ) -> None:
        self.task_type = task_type
        self.cause = cause
        default = "AI 服务暂时不可用，请检查网络后重新生成。"
        super().__init__(message or default)
