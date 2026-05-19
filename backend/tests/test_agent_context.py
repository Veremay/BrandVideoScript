import unittest

from app.services.agent_context import build_agent_chat_messages, summarize_script


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


if __name__ == "__main__":
    unittest.main()
