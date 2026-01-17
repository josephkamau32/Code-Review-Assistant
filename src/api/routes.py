from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks, Depends
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger
from src.models.schemas import ReviewResponse, FeedbackRequest, ManualReviewRequest
from src.rag.pipeline import RAGPipeline
from src.utils.github_client import GitHubClient
from src.utils.auth import get_current_active_user, User
from src.utils.rate_limiting import limit_requests
from src.config.settings import settings
import hmac
import hashlib

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Initialize services
rag_pipeline = RAGPipeline()
try:
    github_client = GitHubClient()
except ValueError:
    logger.warning("GitHub client initialization failed - GitHub features will be disabled")
    github_client = None
def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify that the webhook signature is valid"""
    if not signature_header or not settings.github_webhook_secret:
        return False
    hash_object = hmac.new(
        settings.github_webhook_secret.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)
@router.post("/webhook/github")
@limiter.limit("10/minute")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None)
):
    """
    Handle GitHub webhook events for pull requests
    """
    payload_body = await request.body()
    # Verify webhook signature
    if not verify_github_signature(payload_body, x_hub_signature_256):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")

    logger.info(f"Received GitHub webhook: {event_type}")

    # Handle pull request events
    if event_type == "pull_request":
        action = payload.get("action")

        # Trigger review on PR open or synchronize (new commits)
        if action in ["opened", "synchronize", "reopened"]:
            pr_number = payload["pull_request"]["number"]
            repo_name = payload["repository"]["full_name"]

            logger.info(f"Triggering review for PR #{pr_number} in {repo_name}")

            # Process in background to return quickly
            background_tasks.add_task(
                process_pr_review,
                repo_name,
                pr_number
            )

            return {
                "status": "accepted",
                "message": f"Review queued for PR #{pr_number}"
            }

    return {"status": "ignored", "message": "Event not processed"}
async def process_pr_review(repo_name: str, pr_number: int):
    """Background task to process PR review"""
    if not github_client:
        logger.warning(f"GitHub client not available - skipping PR #{pr_number} review")
        return

    try:
        logger.info(f"Processing review for {repo_name} PR #{pr_number}")
        
        # Fetch PR changes with timeout
        try:
            pull_request = github_client.get_pr_changes(repo_name, pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch PR#{pr_number} changes: {type(e).__name__} - {str(e)}")
            return

        # Validate PR data
        if not pull_request or not pull_request.changes:
            logger.warning(f"PR#{pr_number} has no changes to review")
            return

        # Run RAG pipeline with error handling
        try:
            review_response = rag_pipeline.review_pull_request(pull_request)
        except Exception as e:
            logger.error(f"RAG pipeline failed for PR#{pr_number}: {type(e).__name__} - {str(e)}")
            return

        # Post review to GitHub
        if review_response and review_response.suggestions:
            try:
                suggestions_for_github = [
                    {
                        "category": s.category,
                        "severity": s.severity,
                        "suggestion": s.suggestion,
                        "file_path": s.file_path,
                        "line_number": s.line_number
                    }
                    for s in review_response.suggestions
                ]

                github_client.post_review_comment(
                    repo_name,
                    pr_number,
                    suggestions_for_github
                )
                logger.info(f"Successfully posted {len(review_response.suggestions)} review comments for PR#{pr_number}")
            except Exception as e:
                logger.error(f"Failed to post review for PR#{pr_number}: {type(e).__name__} - {str(e)}")
        else:
            logger.info(f"No suggestions generated for PR#{pr_number}")

    except Exception as e:
        logger.error(f"Unexpected error processing PR#{pr_number}: {type(e).__name__} - {str(e)}", exc_info=True)
@router.post("/review/manual", response_model=ReviewResponse)
async def manual_review(request: ManualReviewRequest):
    """
    Manually trigger a code review for a specific PR
    Useful for testing and on-demand reviews
    """
    repo_name = request.repo_name
    pr_number = request.pr_number

    # Validate GitHub client
    if not github_client or not github_client.client:
        logger.error("GitHub integration not available")
        raise HTTPException(
            status_code=503, 
            detail="GitHub integration not available - please configure GITHUB_TOKEN environment variable"
        )

    # Validate inputs (additional validation beyond Pydantic)
    if not repo_name or "/" not in repo_name:
        raise HTTPException(status_code=400, detail="Invalid repo_name format. Use 'owner/repo'")
    if pr_number <= 0:
        raise HTTPException(status_code=400, detail="pr_number must be a positive integer")

    try:
        logger.info(f"Manual review requested for {repo_name} PR#{pr_number}")
        
        # Fetch PR changes
        try:
            pull_request = github_client.get_pr_changes(repo_name, pr_number)
        except Exception as e:
            logger.error(f"Failed to fetch PR changes: {type(e).__name__} - {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch PR from GitHub: {str(e)}"
            ) from e

        # Validate PR data
        if not pull_request:
            raise HTTPException(status_code=404, detail=f"PR #{pr_number} not found in {repo_name}")
        
        if not pull_request.changes:
            logger.warning(f"PR#{pr_number} has no code changes")
            return ReviewResponse(
                pr_number=pr_number,
                repository=repo_name,
                suggestions=[],
                summary="No code changes found to review",
                processing_time_seconds=0.0
            )

        # Run RAG pipeline
        try:
            review_response = rag_pipeline.review_pull_request(pull_request)
        except Exception as e:
            logger.error(f"RAG pipeline error: {type(e).__name__} - {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Review generation failed: {str(e)}"
            ) from e

        logger.info(f"Manual review completed for {repo_name} PR#{pr_number}: {len(review_response.suggestions)} suggestions")
        return review_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in manual review: {type(e).__name__} - {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        ) from e
@router.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """
    Collect feedback on review suggestions to improve the system
    """
    try:
        # TODO: Store feedback in a database for future fine-tuning
        # For now, just log it
        logger.info(
            f"Feedback received for PR #{feedback.pr_number}: "
            f"helpful={feedback.was_helpful}, comment={feedback.developer_comment}"
        )
        return {
            "status": "success",
            "message": "Feedback recorded"
        }

    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        stats = rag_pipeline.get_stats()
        # Enhanced stats for dashboard
        enhanced_stats = {
            "total_reviews": stats.get("total_reviews", 0),
            "avg_processing_time": 2.3,  # Mock data - would need to track actual times
            "active_models": 1,  # Number of active LLM models
            "vector_count": stats.get("total_reviews", 0),
            "review_trends": [12, 19, 15, 25, 22, 30, 28],  # Last 7 days mock data
            "issue_distribution": [25, 20, 30, 15, 10]  # Security, Performance, Code Quality, Best Practices, Documentation
        }
        return enhanced_stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "code-review-assistant"
    }

