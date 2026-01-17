from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import re


class CodeLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    CLOJURE = "clojure"
    HASKELL = "haskell"
    ERLANG = "erlang"
    ELIXIR = "elixir"
    CPP = "cpp"
    C = "c"
    OBJECTIVE_C = "objective_c"
    DART = "dart"
    OTHER = "other"


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


class ManualReviewRequest(BaseModel):
    repo_name: str
    pr_number: int


class FeedbackRequest(BaseModel):
    suggestion_id: str
    pr_number: int
    was_helpful: bool
    developer_comment: Optional[str] = None


# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


class LoginRequest(BaseModel):
    username: str
    password: str

    @validator('username')
    def username_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()

    @validator('password')
    def password_must_be_valid(cls, v):
        if not v:
            raise ValueError('Password cannot be empty')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str

    @validator('username')
    def username_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Username cannot be empty')
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v.strip()

    @validator('email')
    def email_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Email cannot be empty')
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, v):
            raise ValueError('Invalid email format')
        return v.strip().lower()

    @validator('password')
    def password_must_be_valid(cls, v):
        if not v:
            raise ValueError('Password cannot be empty')
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v


class CodeChange(BaseModel):
    file_path: str
    diff: str
    language: CodeLanguage
    added_lines: int = Field(..., ge=0)
    removed_lines: int = Field(..., ge=0)

    @validator('file_path')
    def file_path_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('File path cannot be empty')
        if len(v) > 500:
            raise ValueError('File path too long')
        # Basic path validation
        if '..' in v or v.startswith('/'):
            raise ValueError('Invalid file path')
        return v.strip()

    @validator('diff')
    def diff_must_be_valid(cls, v):
        if v is not None and len(v) > 100000:  # 100KB limit
            raise ValueError('Diff too large')
        return v


class PullRequest(BaseModel):
    pr_number: int = Field(..., gt=0)
    title: str
    description: Optional[str] = None
    author: str
    repository: str
    branch: str
    changes: List[CodeChange]
    created_at: datetime

    @validator('title')
    def title_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        if len(v) > 200:
            raise ValueError('Title too long')
        return v.strip()

    @validator('repository')
    def repository_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Repository cannot be empty')
        # GitHub repo format: owner/repo
        if '/' not in v or len(v.split('/')) != 2:
            raise ValueError('Repository must be in format owner/repo')
        owner, repo = v.split('/')
        if not owner or not repo:
            raise ValueError('Invalid repository format')
        return v.strip()

    @validator('changes')
    def changes_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('Changes cannot be empty')
        if len(v) > 100:  # Reasonable limit
            raise ValueError('Too many changes in PR')
        return v


class ManualReviewRequest(BaseModel):
    repo_name: str
    pr_number: int = Field(..., gt=0)

    @validator('repo_name')
    def repo_name_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Repository name cannot be empty')
        # GitHub repo format: owner/repo
        if '/' not in v or len(v.split('/')) != 2:
            raise ValueError('Repository must be in format owner/repo')
        owner, repo = v.split('/')
        if not owner or not repo:
            raise ValueError('Invalid repository format')
        if len(owner) > 100 or len(repo) > 100:
            raise ValueError('Repository name components too long')
        return v.strip()