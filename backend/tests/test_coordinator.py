import unittest

from app.repositories.coordinator_messages import build_coordinator_message
from app.services.sse import encode_sse


class CoordinatorMessagesTest(unittest.TestCase):
    def test_build_coordinator_message_has_metadata(self) -> None:
        message = build_coordinator_message(
            project_id="project_1",
            user_id="user_1",
            role="user",
            content="What about this line?",
            task_type="quote_analysis",
            requested_perspectives=["brand", "audience"],
            quotes=[{"text": "hello", "row_id": "row_1"}],
            related_node_ids=["node_1"],
        )
        self.assertTrue(message["message_id"].startswith("msg_"))
        self.assertEqual(message["requested_perspectives"], ["brand", "audience"])
        self.assertEqual(message["quotes"][0]["row_id"], "row_1")


class SseEncodingTest(unittest.TestCase):
    def test_encode_sse_frame(self) -> None:
        frame = encode_sse("token", {"content": "hi"})
        self.assertIn("event: token", frame)
        self.assertIn('"content": "hi"', frame)


if __name__ == "__main__":
    unittest.main()
