import json
import unittest

from app.services.sse import encode_sse


class SSETest(unittest.TestCase):
    def test_encode_sse_writes_event_and_json_data(self):
        frame = encode_sse("token", {"content": "hello"})

        self.assertEqual(frame, 'event: token\ndata: {"content":"hello"}\n\n')

    def test_encode_sse_escapes_newlines_inside_json(self):
        frame = encode_sse("error", {"message": "line 1\nline 2"})
        payload = frame.split("data: ", 1)[1].strip()

        self.assertEqual(json.loads(payload), {"message": "line 1\nline 2"})


if __name__ == "__main__":
    unittest.main()
