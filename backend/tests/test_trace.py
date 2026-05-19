import unittest

from app.services.trace import TraceRecorder


class TraceRecorderTest(unittest.TestCase):
    def test_brief_uploaded_and_llm_events(self):
        trace = TraceRecorder(source="test")
        trace.brief_uploaded(filename="a.md", text_length=100, summary="hello world")
        trace.llm_request(
            task_type="brand_generate_insights",
            model="Qwen/Qwen3-32B",
            messages=[{"role": "user", "content": "x" * 500}],
            mock=False,
        )
        trace.llm_response(
            task_type="brand_generate_insights",
            model="Qwen/Qwen3-32B",
            mock=False,
            content='{"insights":[]}',
        )

        self.assertEqual(len(trace.events), 3)
        self.assertEqual(trace.events[0]["kind"], "brief_uploaded")
        self.assertEqual(trace.events[1]["kind"], "llm_request")
        self.assertEqual(trace.events[1]["data"]["messages"][0]["chars"], 500)
        self.assertEqual(trace.events[2]["kind"], "llm_response")

        br = trace.merge_brand_research({"status": "running"})
        self.assertEqual(br["trace_run_id"], trace.run_id)
        self.assertEqual(len(br["traces"]), 3)

    def test_tool_call_and_result(self):
        trace = TraceRecorder(source="pipeline")
        trace.tool_call("tavily_search", {"query": "brand tone"})
        trace.tool_result("tavily_search", {"result_count": 2})

        self.assertEqual(trace.events[0]["kind"], "tool_call")
        self.assertEqual(trace.events[1]["kind"], "tool_result")
        self.assertEqual(trace.events[1]["data"]["output"]["result_count"], 2)


if __name__ == "__main__":
    unittest.main()
