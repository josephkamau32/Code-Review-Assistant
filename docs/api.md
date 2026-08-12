# API Documentation

## Endpoints

### POST `/api/v1/webhook/github`
Handles GitHub webhook events for automatic PR reviews.

**Headers:**
- `X-Hub-Signature-256`: Webhook signature for verification

**Triggers review on:**
- PR opened
- PR synchronized (new commits)
- PR reopened

### POST `/api/v1/review/manual`
Manually trigger a code review for testing.

**Parameters:**
- `repo_name` (string): Repository in format `owner/repo`
- `pr_number` (integer): Pull request number

**Response:**
```json
{
  "pr_number": 123,
  "repository": "owner/repo",
  "suggestions": [
    {
      "file_path": "src/main.py",
      "line_number": 42,
      "suggestion": "Consider using a more descriptive variable name",
      "severity": "info",
      "category": "style",
      "confidence": 0.85,
      "similar_past_reviews": ["..."]
    }
  ],
  "summary": "Found 3 suggestions for style and best practices",
  "processing_time_seconds": 2.34
}
```

### POST `/api/v1/feedback`
Submit feedback on review suggestions to improve the system.

**Request Body:**
```json
{
  "suggestion_id": "unique-id",
  "pr_number": 123,
  "was_helpful": true,
  "developer_comment": "This suggestion was very helpful"
}
```

### GET `/api/v1/stats`
Get system statistics and health information.

### GET `/api/v1/health`
Basic health check endpoint.
