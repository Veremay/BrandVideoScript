"""Tests for activity log listing helpers."""

from app.repositories.activity_logs import serialize_activity_event


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
