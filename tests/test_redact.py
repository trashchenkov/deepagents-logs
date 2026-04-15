import unittest

from deepagents_logs.core.redact import REDACTED, redact_url, sanitize


class RedactTests(unittest.TestCase):
    def test_sanitize_recurses_sensitive_keys(self):
        payload = {
            "Authorization": "secret",
            "nested": {"api_key": "123", "ok": "x"},
            "list": [{"password": "p"}],
        }
        sanitized = sanitize(payload)
        self.assertEqual(sanitized["Authorization"], REDACTED)
        self.assertEqual(sanitized["nested"]["api_key"], REDACTED)
        self.assertEqual(sanitized["nested"]["ok"], "x")
        self.assertEqual(sanitized["list"][0]["password"], REDACTED)

    def test_redact_url_query_values(self):
        url = "https://example.com/path?token=abc&ok=1"
        self.assertEqual(
            redact_url(url),
            "https://example.com/path?token=%5BREDACTED%5D&ok=1",
        )

    def test_usage_token_counts_are_not_redacted(self):
        payload = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
            },
            "access_token": "secret",
        }
        sanitized = sanitize(payload)
        self.assertEqual(sanitized["usage"]["prompt_tokens"], 10)
        self.assertEqual(sanitized["usage"]["completion_tokens"], 2)
        self.assertEqual(sanitized["usage"]["total_tokens"], 12)
        self.assertEqual(sanitized["access_token"], REDACTED)


if __name__ == "__main__":
    unittest.main()
