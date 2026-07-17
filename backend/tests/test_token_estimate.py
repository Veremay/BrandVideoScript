import unittest

from app.services.token_estimate import estimate_messages_tokens, estimate_tokens


class TokenEstimateTests(unittest.TestCase):
    def test_empty_is_zero(self) -> None:
        self.assertEqual(estimate_tokens(""), 0)

    def test_ascii_roughly_four_chars_per_token(self) -> None:
        text = "abcd" * 25  # 100 chars
        self.assertEqual(estimate_tokens(text), 25)

    def test_cjk_counts_near_one_per_char(self) -> None:
        text = "你好世界" * 10  # 40 chars
        self.assertGreaterEqual(estimate_tokens(text), 40)
        self.assertLessEqual(estimate_tokens(text), 60)

    def test_messages_sum_contents(self) -> None:
        messages = [
            {"role": "user", "content": "abcd" * 10},
            {"role": "assistant", "content": "efgh" * 10},
        ]
        self.assertEqual(estimate_messages_tokens(messages), 20)


if __name__ == "__main__":
    unittest.main()
