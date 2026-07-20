"""Incremental extractor for negotiation JSON string fields while LLM tokens stream in.

Tracks object keys ``issue_node_id``, ``brand_feedback``, and ``reply`` so the UI can
animate each dispute reply as soon as its string value starts arriving.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


TRACKED_KEYS = frozenset({"reply", "issue_node_id", "brand_feedback"})


@dataclass(frozen=True)
class ReplyStreamEvent:
    kind: str  # "reply_token" | "dispute_ready" | "dispute_meta"
    dispute_index: int
    content: str = ""
    issue_node_id: str = ""
    brand_feedback: str = ""
    reply: str = ""


class IncrementalReplyExtractor:
    """Lightweight JSON scanner focused on tracked string fields (not a full JSON parser)."""

    def __init__(self) -> None:
        self._in_string = False
        self._escape = False
        self._reading_key = False
        self._key_chars: list[str] = []
        self._pending_key: str | None = None
        self._awaiting_colon = False
        self._awaiting_value = False
        self._in_value = False
        self._value_chars: list[str] = []
        self._value_key: str | None = None
        self._current_issue_node_id = ""
        self._current_brand_feedback = ""
        self._dispute_index = 0
        self._reply_emitted_len = 0

    def feed(self, chunk: str) -> Iterator[ReplyStreamEvent]:
        token_parts: list[str] = []
        token_index = self._dispute_index

        def flush_tokens() -> Iterator[ReplyStreamEvent]:
            nonlocal token_parts, token_index
            if not token_parts:
                return
            yield ReplyStreamEvent(
                kind="reply_token",
                dispute_index=token_index,
                content="".join(token_parts),
            )
            token_parts = []

        for ch in chunk:
            for event in self._feed_char(ch):
                if event.kind == "reply_token":
                    if token_parts and event.dispute_index != token_index:
                        yield from flush_tokens()
                    token_index = event.dispute_index
                    token_parts.append(event.content)
                else:
                    yield from flush_tokens()
                    yield event
        yield from flush_tokens()

    def _feed_char(self, ch: str) -> Iterator[ReplyStreamEvent]:
        if self._in_value:
            yield from self._feed_value_char(ch)
            return

        if self._in_string:
            if self._escape:
                if self._reading_key:
                    self._key_chars.append(self._unescape(ch))
                self._escape = False
                return
            if ch == "\\":
                self._escape = True
                return
            if ch == '"':
                self._in_string = False
                if self._reading_key:
                    key = "".join(self._key_chars)
                    self._reading_key = False
                    self._key_chars = []
                    if key in TRACKED_KEYS:
                        self._pending_key = key
                        self._awaiting_colon = True
                return
            if self._reading_key:
                self._key_chars.append(ch)
            return

        if self._awaiting_colon:
            if ch.isspace():
                return
            if ch == ":":
                self._awaiting_colon = False
                self._awaiting_value = True
                return
            # unexpected — reset
            self._awaiting_colon = False
            self._pending_key = None
            return

        if self._awaiting_value:
            if ch.isspace():
                return
            if ch == '"':
                self._awaiting_value = False
                self._in_value = True
                self._in_string = True
                self._value_key = self._pending_key
                self._pending_key = None
                self._value_chars = []
                self._reply_emitted_len = 0
                return
            # non-string value for a tracked key — skip
            self._awaiting_value = False
            self._pending_key = None
            return

        if ch == '"':
            self._in_string = True
            self._reading_key = True
            self._key_chars = []
            return

    def _feed_value_char(self, ch: str) -> Iterator[ReplyStreamEvent]:
        if self._escape:
            decoded = self._unescape(ch)
            self._value_chars.append(decoded)
            self._escape = False
            if self._value_key == "reply":
                yield ReplyStreamEvent(
                    kind="reply_token",
                    dispute_index=self._dispute_index,
                    content=decoded,
                )
                self._reply_emitted_len = len(self._value_chars)
            return

        if ch == "\\":
            self._escape = True
            return

        if ch == '"':
            value = "".join(self._value_chars)
            key = self._value_key
            self._in_value = False
            self._in_string = False
            self._value_key = None
            self._value_chars = []

            if key == "issue_node_id":
                self._current_issue_node_id = value
                yield ReplyStreamEvent(
                    kind="dispute_meta",
                    dispute_index=self._dispute_index,
                    issue_node_id=value,
                    brand_feedback=self._current_brand_feedback,
                )
            elif key == "brand_feedback":
                self._current_brand_feedback = value
                yield ReplyStreamEvent(
                    kind="dispute_meta",
                    dispute_index=self._dispute_index,
                    issue_node_id=self._current_issue_node_id,
                    brand_feedback=value,
                )
            elif key == "reply":
                # flush any remaining (should already be emitted char-by-char)
                yield ReplyStreamEvent(
                    kind="dispute_ready",
                    dispute_index=self._dispute_index,
                    issue_node_id=self._current_issue_node_id,
                    brand_feedback=self._current_brand_feedback,
                    reply=value,
                )
                self._dispute_index += 1
                self._current_issue_node_id = ""
                self._current_brand_feedback = ""
            return

        self._value_chars.append(ch)
        if self._value_key == "reply":
            yield ReplyStreamEvent(
                kind="reply_token",
                dispute_index=self._dispute_index,
                content=ch,
            )
            self._reply_emitted_len = len(self._value_chars)

    @staticmethod
    def _unescape(ch: str) -> str:
        mapping = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
        return mapping.get(ch, ch)
