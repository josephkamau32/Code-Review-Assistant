from github import Github, GithubException
from typing import List, Dict, Any, Optional
from loguru import logger
from src.config.settings import settings
from src.models.schemas import HistoricalReview, CodeChange, CodeLanguage, PullRequest
from datetime import datetime
import re


class GitHubClient:
    def __init__(self):
        self.client = Github(settings.github_token)
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
        ext = '.' + file_path.split('.')[-1] if '.' in file_path else ''
        return self.language_extensions.get(ext.lower(), CodeLanguage.OTHER)
    
    def fetch_historical_reviews(
        self,
        repo_name: str,
        max_prs: int = 100
    ) -> List[HistoricalReview]:
        """Fetch historical code reviews from a repository"""
        reviews = []
        
        try:
            repo = self.client.get_repo(repo_name)
            pulls = repo.get_pulls(state='closed', sort='updated', direction='desc')
            
            count = 0
            for pr in pulls:
                if count >= max_prs:
                    break
                
                # Get review comments (inline comments on code)
                review_comments = pr.get_review_comments()
                
                for comment in review_comments:
                    try:
                        # Extract code snippet around the comment
                        code_snippet = self._extract_code_snippet(comment)
                        
                        review = HistoricalReview(
                            pr_number=pr.number,
                            repository=repo_name,
                            file_path=comment.path,
                            code_snippet=code_snippet,
                            review_comment=comment.body,
                            reviewer=comment.user.login,
                            comment_type=self._classify_comment(comment.body),
                            language=self._detect_language(comment.path),
                            created_at=comment.created_at,
                            was_resolved=self._check_if_resolved(pr, comment),
                            resolution_note=None
                        )
                        reviews.append(review)
                    except Exception as e:
                        logger.warning(f"Error processing comment in PR #{pr.number}: {e}")
                        continue
                
                count += 1
                if count % 10 == 0:
                    logger.info(f"Processed {count} PRs, collected {len(reviews)} reviews")
            
            logger.info(f"Collected {len(reviews)} historical reviews from {repo_name}")
            return reviews
            
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise
    
    def _extract_code_snippet(self, comment) -> str:
        """Extract code snippet from review comment context"""
        # GitHub provides diff_hunk which shows the code context
        if hasattr(comment, 'diff_hunk'):
            return comment.diff_hunk
        return ""
    
    def _classify_comment(self, comment_text: str) -> str:
        """Classify the type of review comment"""
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
        except:
            return False
    
    def get_pr_changes(self, repo_name: str, pr_number: int) -> PullRequest:
        """Get detailed changes from a pull request"""
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            changes = []
            files = pr.get_files()
            
            for file in files:
                code_change = CodeChange(
                    file_path=file.filename,
                    diff=file.patch if file.patch else "",
                    language=self._detect_language(file.filename),
                    added_lines=file.additions,
                    removed_lines=file.deletions
                )
                changes.append(code_change)
            
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
    
    def post_review_comment(
        self,
        repo_name: str,
        pr_number: int,
        suggestions: List[Dict[str, Any]]
    ) -> bool:
        """Post review suggestions as PR comments"""
        try:
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