import unittest

from app.services.llm_client import extract_stream_delta


class LLMStreamingTest(unittest.TestCase):
    def test_extract_stream_delta_reads_openai_compatible_content(self):
        chunk = {"choices": [{"delta": {"content": "hello"}}]}

        self.assertEqual(extract_stream_delta(chunk), "hello")

    def test_extract_stream_delta_ignores_empty_delta(self):
        self.assertEqual(extract_stream_delta({"choices": [{"delta": {}}]}), "")


if __name__ == "__main__":
    unittest.main()
