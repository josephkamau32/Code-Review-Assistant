"""
Tests for the redaction layer (PRIV-02).

All secrets used here are deliberately fake / synthetic.
No real production credentials are used anywhere in this file.
"""

import textwrap
from unittest.mock import patch

from src.utils.redaction import (
    _PATTERNS,
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

    def test_provider_specific_key_inside_assignment_no_double_count(self):
        """Confirm a provider-specific key inside an assignment (e.g. AWS_ACCESS_KEY = 'AKIA...')
        records exactly 1 redaction in the report, avoiding double-counting by the
        subsequent generic_secret_assignment pattern.
        """
        text = 'AWS_ACCESS_KEY = "AKIA0000000000000000"'
        redacted, report = redact_text(text)

        assert "AKIA0000000000000000" not in redacted
        assert REDACTED_SECRET in redacted
        assert report.total_redactions == 1
        assert report.redactions_by_label == {"aws_access_key": 1}

    def test_patterns_ordering_provider_before_generic(self):
        """Confirm all provider-specific patterns appear before generic_secret_assignment in _PATTERNS.

        This ordering invariant ensures that provider-specific patterns replace known tokens first,
        allowing generic_secret_assignment's placeholder guard to prevent double-counting.
        """
        labels = [label for label, _ in _PATTERNS]
        generic_idx = labels.index("generic_secret_assignment")
        provider_labels = [
            "aws_access_key",
            "google_api_key",
            "google_api_key_alt",
            "github_token",
            "openai_style_key",
            "slack_token",
        ]
        for pl in provider_labels:
            assert pl in labels
            assert (
                labels.index(pl) < generic_idx
            ), f"Provider pattern '{pl}' must appear before 'generic_secret_assignment' in _PATTERNS"


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

    def test_unclosed_quote_does_not_span_newlines_or_alter_line_count(self):
        """Confirm generic secret assignment with a missing closing quote on line 1
        does NOT match across newlines to a quote on a subsequent line, preserving
        line count (LLM-04 invariant).
        """
        diff = (
            "@@ -1,5 +1,5 @@\n"
            '+API_KEY = "unclosed_secret_without_quote\n'
            " def foo():\n"
            '-    return "quoted_string_on_line_3"\n'
            '+    return "done"\n'
        )
        before_line_count = len(diff.splitlines())
        redacted, report = redact_text(diff)
        after_line_count = len(redacted.splitlines())

        # Line count must be preserved exactly
        assert after_line_count == before_line_count
        # The unclosed quote on line 2 must not consume text across newlines up to line 4
        assert "unclosed_secret_without_quote" in redacted
        assert "quoted_string_on_line_3" in redacted
        assert "done" in redacted
        # No cross-line match occurred
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
        ), "Raw secret was sent to LLM service - redaction failed!"
        assert REDACTED_SECRET in sent_code_change.diff

        # Also verify the embedding service got redacted text
        embed_call_args = mock_embedding.embed_code_change.call_args
        sent_diff_text = embed_call_args[0][0]
        assert (
            fake_secret not in sent_diff_text
        ), "Raw secret was sent to embedding service - redaction failed!"

    @patch("src.rag.pipeline.VectorStoreManager")
    @patch("src.rag.pipeline.EmbeddingService")
    @patch("src.rag.pipeline.LLMService")
    def test_file_path_redacted_in_embedding_and_llm(
        self, MockLLMService, MockEmbeddingService, MockVectorStore
    ):
        from datetime import datetime

        from src.models.schemas import CodeChange, CodeLanguage, PullRequest
        from src.rag.pipeline import RAGPipeline

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

        diff = "@@ -1,2 +1,3 @@\n import os\n+x = 1\n print(x)\n"
        secret_path = "src/AKIA0000000000000000/helper.py"
        pr = PullRequest(
            pr_number=43,
            title="Test PR",
            author="tester",
            repository="test/repo",
            branch="main",
            changes=[
                CodeChange(
                    file_path=secret_path,
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

        # 1. Embedding context must contain redacted file path, not raw secret
        embed_call_kwargs = mock_embedding.embed_code_change.call_args
        context_sent = embed_call_kwargs.kwargs.get("context") or embed_call_kwargs[
            1
        ].get("context")
        assert "AKIA0000000000000000" not in context_sent
        assert REDACTED_SECRET in context_sent

        # 2. LLM service must receive redacted CodeChange.file_path
        call_kwargs = mock_llm.generate_review.call_args
        sent_code_change = call_kwargs.kwargs.get("code_change") or call_kwargs[1].get(
            "code_change"
        )
        if sent_code_change is None:
            sent_code_change = call_kwargs[0][0]
        assert "AKIA0000000000000000" not in sent_code_change.file_path
        assert REDACTED_SECRET in sent_code_change.file_path


class TestHistoricalReviewIngestionRedaction:
    """Test that historical review ingestion redacts secrets and PII before embedding and storage."""

    @patch("src.rag.pipeline.VectorStoreManager")
    @patch("src.rag.pipeline.EmbeddingService")
    @patch("src.rag.pipeline.LLMService")
    def test_pipeline_ingest_historical_reviews_redacts_content(
        self, MockLLMService, MockEmbeddingService, MockVectorStore
    ):
        from datetime import datetime

        from src.models.schemas import CodeLanguage, HistoricalReview
        from src.rag.pipeline import RAGPipeline

        mock_embedding = MockEmbeddingService.return_value
        mock_embedding.embed_batch.return_value = [[0.1] * 768]
        mock_vs = MockVectorStore.return_value

        pipeline = RAGPipeline()
        review = HistoricalReview(
            pr_number=101,
            repository="test/repo",
            file_path="src/config.py",
            code_snippet='API_KEY = "AKIA0000000000000000"',
            review_comment="Please contact developer@example.com about this secret",
            reviewer="reviewer1",
            comment_type="security",
            language=CodeLanguage.PYTHON,
            created_at=datetime.now(),
            was_resolved=True,
        )

        pipeline.ingest_historical_reviews([review])

        # Verify embed_batch received redacted document
        assert mock_embedding.embed_batch.called
        embedded_docs = mock_embedding.embed_batch.call_args[0][0]
        assert len(embedded_docs) == 1
        assert "AKIA0000000000000000" not in embedded_docs[0]
        assert "developer@example.com" not in embedded_docs[0]
        assert REDACTED_SECRET in embedded_docs[0]
        assert REDACTED_EMAIL in embedded_docs[0]

        # Verify vector_store.add_reviews_batch received reviews with redacted snippets/comments
        assert mock_vs.add_reviews_batch.called
        stored_reviews = mock_vs.add_reviews_batch.call_args[0][0]
        assert len(stored_reviews) == 1
        assert "AKIA0000000000000000" not in stored_reviews[0].code_snippet
        assert REDACTED_SECRET in stored_reviews[0].code_snippet
        assert "developer@example.com" not in stored_reviews[0].review_comment
        assert REDACTED_EMAIL in stored_reviews[0].review_comment

    def test_vector_store_add_review_redacts_documents(self):
        from datetime import datetime
        from unittest.mock import MagicMock

        from src.models.schemas import CodeLanguage, HistoricalReview
        from src.rag.vector_store import VectorStoreManager

        vs = VectorStoreManager.__new__(VectorStoreManager)
        vs.collection = MagicMock()

        review = HistoricalReview(
            pr_number=102,
            repository="test/repo",
            file_path="src/auth.py",
            code_snippet='token = "ghp_000000000000000000000000000000000000"',
            review_comment="Hardcoded token found, ping security@example.com",
            reviewer="reviewer2",
            comment_type="security",
            language=CodeLanguage.PYTHON,
            created_at=datetime.now(),
            was_resolved=True,
        )

        vs.add_review(review, [0.1] * 768)

        # Confirm collection.add received document with secrets redacted
        call_kwargs = vs.collection.add.call_args
        documents = call_kwargs.kwargs.get("documents") or call_kwargs[1].get(
            "documents"
        )
        assert len(documents) == 1
        assert "ghp_00000000" not in documents[0]
        assert "security@example.com" not in documents[0]
        assert REDACTED_SECRET in documents[0]
        assert REDACTED_EMAIL in documents[0]


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
