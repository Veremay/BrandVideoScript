"""Tests for application logging helpers."""

from app.services.app_log import summarize_request_body


def test_summarize_request_body_script():
    body = {
        "user_id": "user_1",
        "script": {"rows": [{"row_id": "r1"}], "columns": [{"column_id": "c1"}, {"column_id": "c2"}]},
        "text": "x" * 500,
    }
    summary = summarize_request_body(body)
    assert summary["user_id"] == "user_1"
    assert summary["script"] == {"row_count": 1, "column_count": 2}
    assert len(summary["text"]) < 500


def test_summarize_request_body_skips_empty():
    assert summarize_request_body({"user_id": "u", "message": ""}) == {"user_id": "u"}
