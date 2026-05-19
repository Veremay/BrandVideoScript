import unittest

from app.services.agent_context import (
    build_agent_chat_messages,
    build_prompt_variables,
    format_brand_entity,
    format_brand_insights,
    summarize_script,
)


class AgentContextTest(unittest.TestCase):
    def test_summarize_script_includes_rows_and_columns(self):
        script = {
            "columns": [
                {"column_id": "col_duration", "label": "Duration"},
                {"column_id": "col_scene", "label": "Scene"},
            ],
            "rows": [
                {
                    "row_id": "row_1",
                    "cells": [
                        {"column_id": "col_duration", "value": "0-5"},
                        {"column_id": "col_scene", "value": "Opening shot"},
                    ],
                }
            ],
        }

        summary = summarize_script(script)

        self.assertIn("row_1", summary)
        self.assertIn("Duration: 0-5", summary)
        self.assertIn("Scene: Opening shot", summary)

    def test_build_agent_chat_messages_adds_system_history_and_user_message(self):
        project = {
            "brief": {"summary": "Launch brief"},
            "current_script": {"columns": [], "rows": []},
            "brand_insights": [],
            "audience_analysis": {},
            "personas": [],
            "active_persona_id": None,
        }

        messages = build_agent_chat_messages(
            agent_type="brand",
            system_prompt="System prompt",
            project=project,
            recent_messages=[{"role": "assistant", "content": "Earlier answer"}],
            user_message="New question",
            quotes=[{"text": "Selected quote"}],
        )

        self.assertEqual(messages[0], {"role": "system", "content": "System prompt"})
        self.assertEqual(messages[1], {"role": "assistant", "content": "Earlier answer"})
        self.assertEqual(messages[2]["role"], "user")
        self.assertIn("Selected quote", messages[2]["content"])
        self.assertIn("New question", messages[2]["content"])

    def test_format_brand_entity_uses_research_payload(self):
        project = {
            "brand_research": {
                "entity": {"brand_name": "观夏", "category": "香氛", "product": "陶瓷香挂"},
                "matched_wiki": True,
            }
        }
        text = format_brand_entity(project)
        self.assertIn("观夏", text)
        self.assertIn("香氛", text)
        self.assertIn("陶瓷香挂", text)
        self.assertIn("内部手册：已匹配", text)

    def test_format_brand_entity_returns_placeholder_when_missing(self):
        self.assertIn("尚未识别", format_brand_entity({}))

    def test_format_brand_insights_groups_and_marks_user_vs_agent(self):
        project = {
            "brand_insights": [
                {
                    "category": "explicit_requirement",
                    "title": "必提卖点",
                    "content": "突出陶瓷工艺",
                    "reason": "Brief 明确要求",
                    "confidence": "high",
                    "status": "confirmed",
                    "created_by": "user",
                    "evidence": [{"source_type": "brief", "quote": "突出工艺"}],
                },
                {
                    "category": "implicit_requirement",
                    "title": "调性留白",
                    "content": "保持东方留白感",
                    "reason": "品牌手册",
                    "confidence": "medium",
                    "status": "new",
                    "created_by": "agent",
                    "evidence": [{"source_type": "brand_wiki", "quote": "留白感"}],
                },
            ]
        }
        text = format_brand_insights(project)
        self.assertIn("显式需求（1 条）", text)
        self.assertIn("隐式需求（1 条）", text)
        self.assertIn("必提卖点", text)
        self.assertIn("调性留白", text)
        self.assertIn("用户", text)
        self.assertIn("Agent", text)
        self.assertIn("[brief]", text)
        self.assertIn("[brand_wiki]", text)

    def test_build_prompt_variables_exposes_brand_entity_and_insights(self):
        project = {
            "brief": {"summary": "x"},
            "current_script": {"columns": [], "rows": []},
            "brand_insights": [
                {
                    "category": "explicit_requirement",
                    "title": "T",
                    "content": "C",
                    "reason": "R",
                    "confidence": "high",
                    "status": "new",
                    "created_by": "agent",
                    "evidence": [{"source_type": "brief", "quote": "q"}],
                }
            ],
            "brand_research": {"entity": {"brand_name": "观夏"}, "research_summary": "S"},
            "personas": [],
            "active_persona_id": None,
        }
        variables = build_prompt_variables(project, recent_messages=[], quotes=[])
        self.assertIn("观夏", variables["brand_entity"])
        self.assertIn("T", variables["brand_insights"])
        self.assertNotIn("[{", variables["brand_insights"])  # not a raw str(list)


if __name__ == "__main__":
    unittest.main()
