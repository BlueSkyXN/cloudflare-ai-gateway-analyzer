from __future__ import annotations

import unittest

from cf_aigw_analyzer.usage import parse_usage_from_response


class UsageParserTest(unittest.TestCase):
    def test_openai_usage(self) -> None:
        usage = parse_usage_from_response(
            {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 7,
                    "total_tokens": 17,
                    "prompt_tokens_details": {"cached_tokens": 4},
                    "completion_tokens_details": {"reasoning_tokens": 2},
                }
            }
        )

        self.assertEqual(usage.input_tokens, 10)
        self.assertEqual(usage.output_tokens, 7)
        self.assertEqual(usage.total_tokens, 17)
        self.assertEqual(usage.cached_tokens, 4)
        self.assertEqual(usage.reasoning_tokens, 2)
        self.assertTrue(usage.has_numeric_data)

    def test_anthropic_usage(self) -> None:
        usage = parse_usage_from_response(
            {
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 30,
                    "cache_creation_input_tokens": 5,
                }
            }
        )

        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 20)
        self.assertEqual(usage.total_tokens, 120)
        self.assertEqual(usage.cached_tokens, 30)
        self.assertEqual(usage.cache_write_tokens, 5)

    def test_gemini_usage_metadata(self) -> None:
        usage = parse_usage_from_response(
            {
                "usageMetadata": {
                    "promptTokenCount": 8,
                    "candidatesTokenCount": 12,
                    "totalTokenCount": 20,
                    "cachedContentTokenCount": 3,
                    "thoughtsTokenCount": 6,
                }
            }
        )

        self.assertEqual(usage.input_tokens, 8)
        self.assertEqual(usage.output_tokens, 12)
        self.assertEqual(usage.total_tokens, 20)
        self.assertEqual(usage.cached_tokens, 3)
        self.assertEqual(usage.reasoning_tokens, 6)

    def test_sse_usage(self) -> None:
        usage = parse_usage_from_response(
            'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
            'data: {"usage":{"prompt_tokens":2,"completion_tokens":3}}\n\n'
            "data: [DONE]\n"
        )

        self.assertEqual(usage.input_tokens, 2)
        self.assertEqual(usage.output_tokens, 3)
        self.assertEqual(usage.total_tokens, 5)

    def test_cloudflare_result_can_contain_json_string(self) -> None:
        usage = parse_usage_from_response(
            {
                "success": True,
                "result": '{"usage":{"input_tokens":15,"output_tokens":5,"total_tokens":20}}',
            }
        )

        self.assertEqual(usage.input_tokens, 15)
        self.assertEqual(usage.output_tokens, 5)
        self.assertEqual(usage.total_tokens, 20)


if __name__ == "__main__":
    unittest.main()
