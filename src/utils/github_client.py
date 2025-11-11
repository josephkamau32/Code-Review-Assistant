from github import Github, GithubException
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config.settings import settings
from src.models.schemas import HistoricalReview, CodeChange, CodeLanguage, PullRequest
from datetime import datetime
import re


class GitHubClient:
    def __init__(self):
        if not settings.github_token or settings.github_token == "your_github_token_here":
            logger.warning("GitHub token is not set or using placeholder. GitHub integration will not work.")
            self.client = None
        else:
            self.client = Github(settings.github_token)
            logger.info("GitHub client initialized")
        self.language_extensions = {
            '.py': CodeLanguage.PYTHON,
            '.js': CodeLanguage.JAVASCRIPT,
            '.ts': CodeLanguage.TYPESCRIPT,
            '.java': CodeLanguage.JAVA,
            '.go': CodeLanguage.GO,
            '.rs': CodeLanguage.RUST,
        }
    
    def _detect_language(self, file_path: str) -> CodeLanguage:
        """Detect programming language from file extension"""
        if not file_path or not isinstance(file_path, str):
            return CodeLanguage.OTHER
        ext = '.' + file_path.split('.')[-1] if '.' in file_path else ''
        return self.language_extensions.get(ext.lower(), CodeLanguage.OTHER)
    
    def fetch_historical_reviews(
        self,
        repo_name: str,
        max_prs: int = 100
    ) -> List[HistoricalReview]:
        """Fetch historical code reviews from a repository"""
        if not self.client:
            logger.warning("GitHub client not initialized - skipping fetch")
            return []

        reviews = []
        processed_prs = 0
        error_count = 0

        try:
            # Check rate limit before starting
            rate_limit = self.client.get_rate_limit()
            if rate_limit.core.remaining < 100:
                logger.warning(f"Low GitHub API rate limit remaining: {rate_limit.core.remaining}")
                if rate_limit.core.remaining < 10:
                    raise Exception("GitHub API rate limit nearly exhausted")

            repo = self.client.get_repo(repo_name)
            pulls = repo.get_pulls(state='closed', sort='updated', direction='desc')

            for pr in pulls:
                if processed_prs >= max_prs:
                    break

                try:
                    # Get review comments (inline comments on code)
                    review_comments = pr.get_review_comments()

                    comments_processed = 0
                    for comment in review_comments:
                        try:
                            # Skip comments without body or from bots
                            if not comment.body or not comment.body.strip():
                                continue
                            if comment.user.login.endswith('[bot]'):
                                continue

                            # Extract code snippet around the comment
                            code_snippet = self._extract_code_snippet(comment)

                            # Validate comment content
                            if len(comment.body) > 10000:  # Skip extremely long comments
                                logger.warning(f"Skipping overly long comment in PR #{pr.number}")
                                continue

                            review = HistoricalReview(
                                pr_number=pr.number,
                                repository=repo_name,
                                file_path=comment.path or "unknown",
                                code_snippet=code_snippet,
                                review_comment=comment.body.strip(),
                                reviewer=comment.user.login,
                                comment_type=self._classify_comment(comment.body),
                                language=self._detect_language(comment.path or ""),
                                created_at=comment.created_at,
                                was_resolved=self._check_if_resolved(pr, comment),
                                resolution_note=None
                            )
                            reviews.append(review)
                            comments_processed += 1

                        except Exception as e:
                            logger.warning(f"Error processing comment in PR #{pr.number}: {e}")
                            error_count += 1
                            continue

                    if comments_processed > 0:
                        processed_prs += 1
                        if processed_prs % 10 == 0:
                            logger.info(f"Processed {processed_prs} PRs, collected {len(reviews)} reviews")

                except GithubException as e:
                    logger.warning(f"Error fetching comments for PR #{pr.number}: {e}")
                    error_count += 1
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error processing PR #{pr.number}: {e}")
                    error_count += 1
                    continue

            logger.info(f"Collected {len(reviews)} historical reviews from {repo_name} ({error_count} errors)")

            # Check rate limit after completion
            final_rate_limit = self.client.get_rate_limit()
            logger.info(f"Final rate limit: {final_rate_limit.core.remaining} requests remaining")

            return reviews

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in fetch_historical_reviews: {e}")
            raise
    
    def _extract_code_snippet(self, comment) -> str:
        """Extract code snippet from review comment context"""
        # GitHub provides diff_hunk which shows the code context
        if hasattr(comment, 'diff_hunk'):
            return comment.diff_hunk
        return ""
    
    def _classify_comment(self, comment_text: str) -> str:
        """Classify the type of review comment"""
        if not comment_text or not isinstance(comment_text, str):
            return 'issue'
        comment_lower = comment_text.lower()

        if any(word in comment_lower for word in ['good', 'nice', 'great', 'excellent', 'lgtm']):
            return 'praise'
        elif '?' in comment_text:
            return 'question'
        elif any(word in comment_lower for word in ['should', 'consider', 'suggest', 'maybe', 'could']):
            return 'suggestion'
        else:
            return 'issue'
    
    def _check_if_resolved(self, pr, comment) -> bool:
        """Check if a review comment was resolved"""
        # Simple heuristic: if there are replies from the PR author, consider it engaged with
        # More sophisticated: check if subsequent commits addressed it
        try:
            # Check for resolution in comment thread
            # GitHub doesn't have a direct "resolved" field in older APIs
            # This is a simplified check
            return pr.merged  # If PR was merged, assume major issues were resolved
        except Exception as e:
            logger.warning(f"Error checking resolution for comment: {e}")
            return False
    
    def get_pr_changes(self, repo_name: str, pr_number: int) -> PullRequest:
        """Get detailed changes from a pull request"""
        if not self.client:
            logger.warning("GitHub client not initialized - cannot fetch PR changes")
            raise Exception("GitHub client not available")

        try:
            # Check rate limit
            rate_limit = self.client.get_rate_limit()
            if rate_limit.core.remaining < 10:
                logger.warning(f"Low GitHub API rate limit remaining: {rate_limit.core.remaining}")
                raise Exception("GitHub API rate limit nearly exhausted")

            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            changes = []
            files = pr.get_files()

            for file in files:
                try:
                    code_change = CodeChange(
                        file_path=file.filename,
                        diff=file.patch if file.patch else "",
                        language=self._detect_language(file.filename),
                        added_lines=file.additions,
                        removed_lines=file.deletions
                    )
                    changes.append(code_change)
                except Exception as e:
                    logger.warning(f"Error processing file {file.filename} in PR #{pr_number}: {e}")
                    continue

            pull_request = PullRequest(
                pr_number=pr.number,
                title=pr.title,
                description=pr.body,
                author=pr.user.login,
                repository=repo_name,
                branch=pr.head.ref,
                changes=changes,
                created_at=pr.created_at
            )

            logger.info(f"Fetched PR #{pr_number} with {len(changes)} file changes")
            return pull_request

        except GithubException as e:
            logger.error(f"Error fetching PR #{pr_number}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_pr_changes: {e}")
            raise
    
    def post_review_comment(
        self,
        repo_name: str,
        pr_number: int,
        suggestions: List[Dict[str, Any]]
    ) -> bool:
        """Post review suggestions as PR comments"""
        if not self.client:
            logger.warning("GitHub client not initialized - cannot post review comment")
            return False

        try:
            # Check rate limit
            rate_limit = self.client.get_rate_limit()
            if rate_limit.core.remaining < 5:
                logger.warning(f"Low GitHub API rate limit remaining: {rate_limit.core.remaining}")
                return False

            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)

            # Format suggestions into a comment body
            comment_body = "## 🤖 AI Code Review\n\n"

            for idx, suggestion in enumerate(suggestions, 1):
                comment_body += f"### {idx}. {suggestion['category'].title()}\n"
                comment_body += f"**Severity:** {suggestion['severity'].upper()}\n"
                comment_body += f"{suggestion['suggestion']}\n\n"

            # Post as a review comment
            pr.create_issue_comment(comment_body)
            logger.info(f"Posted review comment to PR #{pr_number}")
            return True

        except GithubException as e:
            logger.error(f"Error posting review comment: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in post_review_comment: {e}")
            return False