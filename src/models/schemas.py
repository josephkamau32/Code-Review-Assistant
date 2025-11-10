from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class CodeLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    OTHER = "other"


class CodeChange(BaseModel):
    file_path: str
    diff: str
    language: CodeLanguage
    added_lines: int
    removed_lines: int


class PullRequest(BaseModel):
    pr_number: int
    title: str
    description: Optional[str] = None
    author: str
    repository: str
    branch: str
    changes: List[CodeChange]
    created_at: datetime
    

class HistoricalReview(BaseModel):
    pr_number: int
    repository: str
    file_path: str
    code_snippet: str
    review_comment: str
    reviewer: str
    comment_type: str  # suggestion, issue, praise, question
    language: CodeLanguage
    created_at: datetime
    was_resolved: bool
    resolution_note: Optional[str] = None


class ReviewSuggestion(BaseModel):
    file_path: str
    line_number: Optional[int] = None
    suggestion: str
    severity: str  # info, warning, error
    category: str  # style, bug, performance, security, best_practice
    confidence: float = Field(..., ge=0.0, le=1.0)
    similar_past_reviews: List[str] = []


class ReviewResponse(BaseModel):
    pr_number: int
    repository: str
    suggestions: List[ReviewSuggestion]
    summary: str
    processing_time_seconds: float


class FeedbackRequest(BaseModel):
    suggestion_id: str
    pr_number: int
    was_helpful: bool
    developer_comment: Optional[str] = None