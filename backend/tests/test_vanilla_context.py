import unittest
from unittest.mock import patch

from app.services.coordinator_stream import build_vanilla_system_content


class BuildVanillaSystemContentTests(unittest.TestCase):
    def test_includes_system_prompt_and_full_script(self) -> None:
        project = {
            "current_script": {
                "columns": [
                    {"column_id": "c1", "key": "scene", "label": "画面", "order": 0},
                    {"column_id": "c2", "key": "voiceover", "label": "口播", "order": 1},
                ],
                "rows": [
                    {
                        "row_id": "r1",
                        "order": 0,
                        "cells": [
                            {"column_id": "c1", "value": "开场特写"},
                            {"column_id": "c2", "value": "大家好"},
                        ],
                    }
                ],
            }
        }
        with patch(
            "app.services.coordinator_stream.load_prompt",
            return_value="SYSTEM_PROMPT_MARKER",
        ):
            content = build_vanilla_system_content(project)

        self.assertTrue(content.startswith("SYSTEM_PROMPT_MARKER"))
        self.assertIn("row_id=r1", content)
        self.assertIn("开场特写", content)
        self.assertIn("大家好", content)
        self.assertTrue("当前完整脚本" in content or "Full current script" in content)


if __name__ == "__main__":
    unittest.main()
