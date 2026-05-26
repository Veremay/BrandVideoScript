import unittest

from app.services.coordinator_intent import wants_generate_modification_schemes


class CoordinatorIntentTests(unittest.TestCase):
    def test_detects_chinese_generate_request(self) -> None:
        self.assertTrue(wants_generate_modification_schemes("请帮我生成多方向修改方案"))
        self.assertTrue(wants_generate_modification_schemes("重新生成新方案"))

    def test_detects_english_request(self) -> None:
        self.assertTrue(wants_generate_modification_schemes("generate revision proposals for open issues"))

    def test_ignores_general_analysis(self) -> None:
        self.assertFalse(wants_generate_modification_schemes("分析一下这段脚本"))
        self.assertFalse(wants_generate_modification_schemes("这个品牌 issue 是什么意思？"))

    def test_ignores_node_generation_without_scheme(self) -> None:
        self.assertFalse(wants_generate_modification_schemes("请生成新节点"))
        self.assertTrue(wants_generate_modification_schemes("请生成新节点相关的修改方案"))

    def test_explicit_task_type(self) -> None:
        self.assertTrue(
            wants_generate_modification_schemes("hello", task_type="generate_modification_schemes")
        )


if __name__ == "__main__":
    unittest.main()
