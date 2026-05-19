import unittest

from app.repositories.agent_messages import build_agent_message, serialize_agent_message, sort_recent_messages


class AgentMessagesTest(unittest.TestCase):
    def test_build_agent_message_sets_metadata(self):
        message = build_agent_message(
            project_id="project_1",
            user_id="user_1",
            agent_type="brand",
            role="user",
            content="Is this too ad-like?",
            quotes=[{"text": "Buy now", "row_id": "row_1", "column_id": "col_scene"}],
        )

        self.assertTrue(message["_id"].startswith("msg_"))
        self.assertEqual(message["project_id"], "project_1")
        self.assertEqual(message["agent_type"], "brand")
        self.assertEqual(message["role"], "user")
        self.assertEqual(message["content"], "Is this too ad-like?")
        self.assertEqual(message["quotes"][0]["text"], "Buy now")
        self.assertIsNotNone(message["created_at"])

    def test_serialize_agent_message_uses_string_id(self):
        message = build_agent_message(
            project_id="project_1",
            user_id="user_1",
            agent_type="audience",
            role="assistant",
            content="It feels natural.",
            quotes=[],
        )

        serialized = serialize_agent_message(message)

        self.assertEqual(serialized["_id"], message["_id"])

    def test_sort_recent_messages_returns_chronological_order(self):
        messages = [
            {"_id": "msg_2", "created_at": "2026-05-19T10:00:02"},
            {"_id": "msg_1", "created_at": "2026-05-19T10:00:01"},
        ]

        ordered = sort_recent_messages(messages)

        self.assertEqual([message["_id"] for message in ordered], ["msg_1", "msg_2"])


if __name__ == "__main__":
    unittest.main()
