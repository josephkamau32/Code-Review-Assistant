from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks
from typing import Optional
from loguru import logger
from src.models.schemas import ReviewResponse, FeedbackRequest
from src.rag.pipeline import RAGPipeline
from src.utils.github_client import GitHubClient
from src.config.settings import settings
import hmac
import hashlib
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
    if not signature_header:
        return False
    hash_object = hmac.new(
        settings.github_webhook_secret.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)
@router.post("/webhook/github")
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
        # Fetch PR changes
        pull_request = github_client.get_pr_changes(repo_name, pr_number)

        # Run RAG pipeline
        review_response = rag_pipeline.review_pull_request(pull_request)

        # Post review to GitHub
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

        logger.info(f"Successfully posted review for PR #{pr_number}")

    except Exception as e:
        logger.error(f"Error processing PR #{pr_number}: {e}")
@router.post("/review/manual", response_model=ReviewResponse)
async def manual_review(repo_name: str, pr_number: int):
    """
    Manually trigger a code review for a specific PR
    Useful for testing and on-demand reviews
    """
    if not github_client:
        raise HTTPException(status_code=503, detail="GitHub integration not available - please configure GitHub token")

    try:
        logger.info(f"Manual review requested for {repo_name} PR #{pr_number}")
        # Fetch PR changes
        pull_request = github_client.get_pr_changes(repo_name, pr_number)

        # Run RAG pipeline
        review_response = rag_pipeline.review_pull_request(pull_request)

        return review_response

    except Exception as e:
        logger.error(f"Error in manual review: {e}")
        raise HTTPException(status_code=500, detail=str(e))
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
        return {
            "status": "healthy",
            "vector_db": stats
        }
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
