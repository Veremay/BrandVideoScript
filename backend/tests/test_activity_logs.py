"""Tests for activity log listing helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.activity_logs import (
    build_activity_event,
    persist_http_activity_log,
    serialize_activity_event,
    should_persist_http_path,
)


def test_serialize_activity_event_strips_mongo_id():
    document = {
        "_id": "mongo_object_id",
        "event_id": "evt_123",
        "project_id": "project_1",
        "action": "script.save",
        "before": {"script": {"rows": []}},
        "after": {"script": {"rows": [{"row_id": "r1"}]}},
    }
    event = serialize_activity_event(document)
    assert "_id" not in event
    assert event["event_id"] == "evt_123"
    assert event["after"]["script"]["rows"][0]["row_id"] == "r1"


def test_build_activity_event_marks_http_type():
    event = build_activity_event(
        method="POST",
        path="/api/projects/project_1/script",
        status_code=200,
        duration_ms=12.34,
        request_id="abc123",
        user_id="creator001",
        project_id="project_1",
    )
    assert event["event_type"] == "http"
    assert event["source"] == "api"
    assert event["action"] == "POST /api/projects/project_1/script"
    assert event["method"] == "POST"
    assert event["path"] == "/api/projects/project_1/script"
    assert event["status_code"] == 200
    assert event["duration_ms"] == 12.34
    assert event["request_id"] == "abc123"
    assert event["user_id"] == "creator001"
    assert event["project_id"] == "project_1"
    assert "event_id" in event
    assert "ts" in event


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/projects/project_1/script", True),
        ("/api/health", False),
        ("/docs", False),
        ("/openapi.json", False),
        ("/redoc", False),
    ],
)
def test_should_persist_http_path(path: str, expected: bool):
    assert should_persist_http_path(path) is expected


@pytest.mark.asyncio
async def test_persist_http_activity_log_inserts_when_enabled():
    db = MagicMock()
    db.activity_logs.insert_one = AsyncMock()
    with patch("app.repositories.activity_logs.activity_log_enabled", return_value=True):
        await persist_http_activity_log(
            db,
            method="GET",
            path="/api/projects/project_1",
            status_code=200,
            duration_ms=5.0,
            request_id="rid1",
            user_id="creator001",
            project_id="project_1",
        )
    db.activity_logs.insert_one.assert_awaited_once()
    inserted = db.activity_logs.insert_one.await_args.args[0]
    assert inserted["event_type"] == "http"
    assert inserted["source"] == "api"
    assert inserted["project_id"] == "project_1"


@pytest.mark.asyncio
async def test_persist_http_activity_log_skips_when_disabled():
    db = MagicMock()
    db.activity_logs.insert_one = AsyncMock()
    with patch("app.repositories.activity_logs.activity_log_enabled", return_value=False):
        await persist_http_activity_log(
            db,
            method="GET",
            path="/api/projects/project_1",
            status_code=200,
            duration_ms=5.0,
            request_id="rid1",
            user_id="creator001",
            project_id="project_1",
        )
    db.activity_logs.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_http_activity_log_skips_noise_paths():
    db = MagicMock()
    db.activity_logs.insert_one = AsyncMock()
    with patch("app.repositories.activity_logs.activity_log_enabled", return_value=True):
        await persist_http_activity_log(
            db,
            method="GET",
            path="/api/health",
            status_code=200,
            duration_ms=1.0,
            request_id="rid1",
        )
    db.activity_logs.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_http_activity_log_skips_ui_batch_path():
    db = MagicMock()
    db.activity_logs.insert_one = AsyncMock()
    with patch("app.repositories.activity_logs.activity_log_enabled", return_value=True):
        await persist_http_activity_log(
            db,
            method="POST",
            path="/api/projects/project_1/activity-logs/batch",
            status_code=200,
            duration_ms=2.0,
            request_id="rid2",
        )
    db.activity_logs.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_insert_ui_activity_logs_batch_inserts_when_enabled():
    from app.repositories.activity_logs import insert_ui_activity_logs_batch

    db = MagicMock()
    db.activity_logs.insert_many = AsyncMock()
    with patch("app.repositories.activity_logs.ui_activity_log_enabled", return_value=True):
        inserted = await insert_ui_activity_logs_batch(
            db,
            project_id="project_1",
            user_id="creator001",
            events=[
                {
                    "action": "ui.click",
                    "client_ts": "2026-07-22T09:00:00.000Z",
                    "session_id": "sess_1",
                    "meta": {"data_track": "nav.back", "target": "Back"},
                }
            ],
        )
    assert inserted == 1
    db.activity_logs.insert_many.assert_awaited_once()
    docs = db.activity_logs.insert_many.await_args.args[0]
    assert docs[0]["event_type"] == "ui"
    assert docs[0]["action"] == "ui.click"
    assert docs[0]["source"] == "frontend"
    assert docs[0]["meta"]["data_track"] == "nav.back"
    assert docs[0]["client_ts"] == "2026-07-22T09:00:00.000Z"


@pytest.mark.asyncio
async def test_insert_ui_activity_logs_batch_skips_when_disabled():
    from app.repositories.activity_logs import insert_ui_activity_logs_batch

    db = MagicMock()
    db.activity_logs.insert_many = AsyncMock()
    with patch("app.repositories.activity_logs.ui_activity_log_enabled", return_value=False):
        inserted = await insert_ui_activity_logs_batch(
            db,
            project_id="project_1",
            user_id="creator001",
            events=[{"action": "ui.click", "meta": {"data_track": "nav.back"}}],
        )
    assert inserted == 0
    db.activity_logs.insert_many.assert_not_awaited()


def test_build_ui_activity_event_shape():
    from app.repositories.activity_logs import build_ui_activity_event

    event = build_ui_activity_event(
        project_id="project_1",
        user_id="creator001",
        action="ui.click",
        client_ts="2026-07-22T09:00:00.000Z",
        session_id="sess_1",
        meta={"data_track": "script.argue.toggle"},
    )
    assert event["event_type"] == "ui"
    assert event["source"] == "frontend"
    assert "event_id" in event
    assert "ts" in event
    assert event["meta"]["data_track"] == "script.argue.toggle"
