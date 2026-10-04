"""
Tests for the redaction layer (PRIV-02).

All secrets used here are deliberately fake / synthetic.
No real production credentials are used anywhere in this file.
"""

import textwrap
from unittest.mock import patch

from src.utils.redaction import (
    REDACTED_EMAIL,
    REDACTED_SECRET,
    redact_text,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

FAKE_DIFF_WITH_SECRETS = textwrap.dedent(
    """\
    @@ -1,12 +1,14 @@
     import os
    +
    +AWS_ACCESS_KEY = "AKIA0000000000000000"
    +GOOGLE_API_KEY = "AIza00000000000000000000000000000000000"
    +GITHUB_TOKEN = "ghp_000000000000000000000000000000000000"
    +OPENAI_KEY = "sk-000000000000000000000000"
    +SLACK_TOKEN = "xoxb-0000000000000000000000"
    +MY_SECRET = "super_secret_value_here"
    +MY_PASSWORD = "hunter2_not_a_real_password"
    +contact = "developer@example.com"
    +normal_code = some_function()
     print("hello world")
"""
)


class TestRedactionPatterns:
    """Test each individual pattern type is caught."""

    def test_aws_access_key(self):
        text = 'AWS_KEY = "AKIA0000000000000000"'
        redacted, report = redact_text(text)
        assert "AKIA0000000000000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_google_api_key(self):
        text = 'key = "AIza00000000000000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "AIza0000000000000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_google_api_key_alt(self):
        text = 'key = "AQ00Ab000000000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "AQ00Ab" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_github_classic_token(self):
        text = 'token = "ghp_000000000000000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "ghp_00000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_github_oauth_token(self):
        text = 'GITHUB_OAUTH = "gho_000000000000000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "gho_00000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_github_fine_grained_token(self):
        text = 'GH_TOKEN = "github_pat_00000000000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "github_pat_000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_openai_style_key(self):
        text = 'OPENAI_API_KEY = "sk-000000000000000000000000"'
        redacted, report = redact_text(text)
        assert "sk-00000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_slack_bot_token(self):
        text = 'SLACK_TOKEN = "xoxb-0000000000000000000000"'
        redacted, report = redact_text(text)
        assert "xoxb-000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_slack_user_token(self):
        text = 'SLACK = "xoxp-0000000000000000000000"'
        redacted, report = redact_text(text)
        assert "xoxp-000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_generic_secret_assignment(self):
        text = 'MY_SECRET = "super_secret_value_here"'
        redacted, report = redact_text(text)
        assert "super_secret_value_here" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_generic_password_assignment(self):
        text = "password = 'hunter2_not_a_real_password'"
        redacted, report = redact_text(text)
        assert "hunter2_not_a_real_password" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions >= 1

    def test_generic_token_assignment_case_insensitive(self):
        text = 'Api_Token = "some_token_value_12345"'
        redacted, report = redact_text(text)
        assert "some_token_value_12345" not in redacted
        assert REDACTED_SECRET in redacted

    def test_email_address(self):
        text = "author: developer@example.com"
        redacted, report = redact_text(text)
        assert "developer@example.com" not in redacted
        assert REDACTED_EMAIL in redacted
        assert report.total_redactions >= 1


class TestRedactionPreservesStructure:
    """Redaction must not alter line count or line boundaries."""

    def test_line_count_preserved(self):
        original_lines = FAKE_DIFF_WITH_SECRETS.splitlines()
        redacted, _report = redact_text(FAKE_DIFF_WITH_SECRETS)
        redacted_lines = redacted.splitlines()
        assert len(original_lines) == len(
            redacted_lines
        ), f"Line count mismatch: {len(original_lines)} vs {len(redacted_lines)}"

    def test_newline_count_preserved(self):
        original_newlines = FAKE_DIFF_WITH_SECRETS.count("\n")
        redacted, _report = redact_text(FAKE_DIFF_WITH_SECRETS)
        redacted_newlines = redacted.count("\n")
        assert original_newlines == redacted_newlines

    def test_non_secret_code_untouched(self):
        redacted, _report = redact_text(FAKE_DIFF_WITH_SECRETS)
        # These lines contain no secrets and should be byte-identical
        assert "import os" in redacted
        assert "normal_code = some_function()" in redacted
        assert 'print("hello world")' in redacted
        assert "@@ -1,12 +1,14 @@" in redacted

    def test_clean_code_passes_through_unchanged(self):
        clean = textwrap.dedent(
            """\
            def add(a, b):
                return a + b

            class Foo:
                pass
        """
        )
        redacted, report = redact_text(clean)
        assert redacted == clean
        assert report.total_redactions == 0


class TestRedactionReport:
    """The report must list pattern labels and counts without the secret values."""

    def test_report_counts(self):
        _redacted, report = redact_text(FAKE_DIFF_WITH_SECRETS)
        assert report.total_redactions > 0
        assert isinstance(report.redactions_by_label, dict)
        # At least AWS, Google, GitHub, OpenAI-style, Slack, generic, email
        assert len(report.redactions_by_label) >= 4

    def test_report_does_not_contain_secret_values(self):
        """The report object must never store the actual secret."""
        _redacted, report = redact_text(FAKE_DIFF_WITH_SECRETS)
        report_str = str(report)
        assert "AKIA0000000000000000" not in report_str
        assert "developer@example.com" not in report_str


class TestLineValidationUnaffected:
    """Prove that extract_valid_lines returns identical results before/after redaction."""

    def test_valid_lines_identical_before_and_after_redaction(self):
        from src.rag.pipeline import extract_valid_lines

        diff_with_secret = (
            "@@ -1,2 +1,4 @@\n"
            " import os\n"
            '+API_KEY = "sk-000000000000000000000000"\n'
            "+normal_line = True\n"
            ' print("done")\n'
        )
        file_path = "config.py"

        valid_before = extract_valid_lines(diff_with_secret, file_path)

        redacted, _report = redact_text(diff_with_secret)
        valid_after = extract_valid_lines(redacted, file_path)

        assert (
            valid_before == valid_after
        ), f"Valid lines differ after redaction: {valid_before} vs {valid_after}"
        # Sanity: there should actually be valid lines
        assert len(valid_before) > 0


class TestLLMServiceReceivesRedactedText:
    """Prove the LLM boundary mock receives redacted text, not raw secrets."""

    @patch("src.rag.pipeline.VectorStoreManager")
    @patch("src.rag.pipeline.EmbeddingService")
    @patch("src.rag.pipeline.LLMService")
    def test_llm_gets_redacted_diff(
        self, MockLLMService, MockEmbeddingService, MockVectorStore
    ):
        from datetime import datetime

        from src.models.schemas import CodeChange, CodeLanguage, PullRequest
        from src.rag.pipeline import RAGPipeline

        # Setup mocks
        mock_embedding = MockEmbeddingService.return_value
        mock_embedding.embed_code_change.return_value = [0.1] * 768

        mock_vs = MockVectorStore.return_value
        mock_vs.search_similar_reviews.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        mock_llm = MockLLMService.return_value
        mock_llm.generate_review.return_value = {
            "suggestions": [],
            "summary": "Looks good.",
        }
        mock_llm.generate_summary.return_value = "No issues."

        # Build a PR with a diff containing a fake secret
        fake_secret = "sk-000000000000000000000000"
        diff = (
            "@@ -1,2 +1,3 @@\n"
            " import os\n"
            f'+API_KEY = "{fake_secret}"\n'
            ' print("hello")\n'
        )

        pr = PullRequest(
            pr_number=42,
            title="Test PR",
            author="tester",
            repository="test/repo",
            branch="main",
            changes=[
                CodeChange(
                    file_path="config.py",
                    diff=diff,
                    language=CodeLanguage.PYTHON,
                    added_lines=1,
                    removed_lines=0,
                )
            ],
            created_at=datetime.now(),
        )

        pipeline = RAGPipeline()
        pipeline.review_pull_request(pr)

        # Verify that the LLM service was called with a redacted CodeChange
        assert mock_llm.generate_review.called
        call_kwargs = mock_llm.generate_review.call_args
        sent_code_change = call_kwargs.kwargs.get("code_change") or call_kwargs[1].get(
            "code_change"
        )
        if sent_code_change is None:
            # positional arg
            sent_code_change = call_kwargs[0][0]

        assert (
            fake_secret not in sent_code_change.diff
        ), "Raw secret was sent to LLM service — redaction failed!"
        assert REDACTED_SECRET in sent_code_change.diff

        # Also verify the embedding service got redacted text
        embed_call_args = mock_embedding.embed_code_change.call_args
        sent_diff_text = embed_call_args[0][0]
        assert (
            fake_secret not in sent_diff_text
        ), "Raw secret was sent to embedding service — redaction failed!"


class TestCase02BenchmarkRedaction:
    """Standalone test verifying how case_02 (hardcoded JWT secret) is transformed by redaction."""

    def test_case_02_hardcoded_jwt_secret_redaction(self):
        import json
        from pathlib import Path

        case_path = Path("eval/cases/case_02_hardcoded_jwt_secret.json")
        with open(case_path, "r", encoding="utf-8") as f:
            case_data = json.load(f)

        original_diff = case_data["diff"]
        redacted_diff, report = redact_text(original_diff)

        # Print for visibility when running pytest with -s
        print("\n" + "=" * 60)
        print("CASE_02 ORIGINAL DIFF:")
        print(original_diff)
        print("CASE_02 REDACTED DIFF:")
        print(redacted_diff)
        print("CASE_02 REDACTION REPORT:")
        print(report)
        print("=" * 60 + "\n")

        # Verify the secret was scrubbed
        assert "production-jwt-super-secret-key-12345" not in redacted_diff
        # Verify the variable assignment structure remains intact
        assert f'SECRET_KEY = "{REDACTED_SECRET}"' in redacted_diff
        assert '-SECRET_KEY = os.getenv("JWT_SECRET_KEY")' in redacted_diff
        assert "+SECRET_KEY =" in redacted_diff
        # Verify line counts match
        assert original_diff.count("\n") == redacted_diff.count("\n")
        # Verify report label
        assert report.total_redactions == 1
        assert "generic_secret_assignment" in report.redactions_by_label
