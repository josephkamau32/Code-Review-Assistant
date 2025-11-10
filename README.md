```markdown
# Code Review Assistant with RAG

AI-powered code review assistant that learns from your team's historical reviews and provides intelligent, context-aware feedback on pull requests.

## Features

- 🤖 **Intelligent Reviews**: Uses RAG to provide context-aware suggestions based on historical reviews
- 📚 **Learns from History**: Ingests past code reviews to maintain consistency
- 🎯 **Customizable**: Supports custom style guides and coding standards
- 🔄 **Real-time**: Automatic reviews via GitHub webhooks
- 📊 **Analytics**: Track review patterns and improvements

## Architecture
```
Pull Request → GitHub Webhook → FastAPI Backend → RAG Pipeline
                                                      ↓
                                    Vector DB ← Embeddings ← Historical Reviews
                                                      ↓
                                                  LLM (GPT-4)
                                                      ↓
                                            Review Suggestions → GitHub Comment

Quick Start
1. Installation
bash

# Clone repository
git clone <your-repo-url>
cd code-review-assistant

# Run setup
chmod +x scripts/setup.sh
./scripts/setup.sh
source venv/bin/activate

2. Configuration

Update .env with your credentials:
bash

OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=your-secret

3. Ingest Historical Data
bash

# Ingest reviews from your repository
python scripts/ingest_reviews.py --repo your-org/your-repo --max-prs 100

# Optional: Add style guide
python scripts/ingest_style_guide.py --file docs/style-guide.md --language python

4. Start the API
bash

# Development
uvicorn src.api.app:app --reload

# Production with Docker
docker-compose up -d

5. Setup GitHub Webhook

    Go to your repository Settings → Webhooks
    Add webhook:
        Payload URL: https://your-domain.com/api/v1/webhook/github
        Content type: application/json
        Secret: Your GITHUB_WEBHOOK_SECRET
        Events: Select "Pull requests"

Usage
Automatic Reviews

Once the webhook is set up, reviews are automatic:

    Open a new PR → Review posted automatically
    Push new commits → Updated review posted

Manual Reviews
bash

curl -X POST "http://localhost:8000/api/v1/review/manual?repo_name=owner/repo&pr_number=123"

Python API
python

from src.utils.github_client import GitHubClient
from src.rag.pipeline import RAGPipeline

# Initialize
github_client = GitHubClient()
pipeline = RAGPipeline()

# Get PR
pr = github_client.get_pr_changes("owner/repo", 123)

# Review
review = pipeline.review_pull_request(pr)

print(f"Found {len(review.suggestions)} suggestions")
for suggestion in review.suggestions:
    print(f"- [{suggestion.severity}] {suggestion.suggestion}")
```

## Project Structure
```
code-review-assistant/
├── src/
│   ├── api/              # FastAPI application
│   ├── rag/              # RAG pipeline components
│   ├── models/           # Pydantic models
│   ├── utils/            # Utility functions
│   └── config/           # Configuration
├── scripts/              # CLI scripts
├── tests/                # Unit & integration tests
├── data/                 # Data storage
├── logs/                 # Application logs
├── notebooks/            # Jupyter notebooks for analysis
├── docker-compose.yml
├── Dockerfile
└── requirements.txt

Testing
bash

# Run all tests
pytest

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_rag_pipeline.py -v

Performance

    Review Time: ~5-15 seconds per PR (depends on changes)
    Cost: ~$0.01-0.05 per review (using GPT-4 Turbo)
    Accuracy: Improves with more historical data (recommend 50+ PRs minimum)

Monitoring

Check system health:
bash

curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/stats

View logs:
bash

tail -f logs/app.log

Customization
Add Custom Review Categories

Edit src/models/schemas.py:
python

class ReviewCategory(str, Enum):
    STYLE = "style"
    BUG = "bug"
    PERFORMANCE = "performance"
    SECURITY = "security"
    YOUR_CUSTOM = "your_custom"  # Add here

Adjust Retrieval Parameters

Edit .env:
bash

TOP_K_RESULTS=10  # More similar reviews
SIMILARITY_THRESHOLD=0.6  # Lower = more lenient matching

Use Different Models
bash

# Cheaper option
LLM_MODEL=gpt-3.5-turbo
EMBEDDING_MODEL=text-embedding-ada-002

# Better quality
LLM_MODEL=gpt-4-turbo-preview
EMBEDDING_MODEL=text-embedding-3-large
```

## Troubleshooting

### "No reviews found in vector database"
Run the ingestion script first to populate with historical data.

### "Rate limit exceeded"
Adjust retry settings in `src/rag/embeddings.py` or upgrade your OpenAI plan.

### "Webhook signature invalid"
Ensure `GITHUB_WEBHOOK_SECRET` matches what's configured in GitHub.

## Future Enhancements

- [ ] Fine-tuned model on your codebase
- [ ] Support for more languages (C++, Ruby, etc.)
- [ ] Integration with Jira/Linear for tracking
- [ ] A/B testing framework
- [ ] Custom evaluation metrics
- [ ] Web dashboard for analytics

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

MIT License - See LICENSE file for details
```

## Phase 10: Advanced Features & Optimization

### Step 10.1: Feedback Loop (src/rag/feedback_loop.py)
```python
"""
Feedback loop to improve the system based on developer interactions
"""

from typing import Dict, List
from loguru import logger
import json
from pathlib import Path


class FeedbackCollector:
    def __init__(self, feedback_file: str = "data/feedback.jsonl"):
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
    
    def record_feedback(
        self,
        pr_number: int,
        suggestion_id: str,
        was_helpful: bool,
        suggestion_text: str,
        category: str,
        severity: str,
        developer_comment: str = None
    ):
        """Record developer feedback on a suggestion"""
        feedback_entry = {
            "pr_number": pr_number,
            "suggestion_id": suggestion_id,
            "was_helpful": was_helpful,
            "suggestion_text": suggestion_text,
            "category": category,
            "severity": severity,
            "developer_comment": developer_comment,
            "timestamp": str(datetime.now())
        }
        
        with open(self.feedback_file, 'a') as f:
            f.write(json.dumps(feedback_entry) + '\n')
        
        logger.info(f"Recorded feedback for PR #{pr_number}")
    
    def get_feedback_stats(self) -> Dict:
        """Analyze collected feedback"""
        if not self.feedback_file.exists():
            return {"total": 0}
        
        feedbacks = []
        with open(self.feedback_file, 'r') as f:
            for line in f:
                feedbacks.append(json.loads(line))
        
        total = len(feedbacks)
        helpful = sum(1 for f in feedbacks if f['was_helpful'])
        
        by_category = {}
        for f in feedbacks:
            cat = f['category']
            if cat not in by_category:
                by_category[cat] = {"total": 0, "helpful": 0}
            by_category[cat]['total'] += 1
            if f['was_helpful']:
                by_category[cat]['helpful'] += 1
        
        return {
            "total_feedback": total,
            "helpful_count": helpful,
            "helpfulness_rate": helpful / total if total > 0 else 0,
            "by_category": by_category
        }
```

### Step 10.2: Monitoring Dashboard Data (src/utils/metrics.py)
```python
"""
Collect metrics for monitoring dashboard
"""

from dataclasses import dataclass, asdict
from typing import List, Dict
from datetime import datetime
import json
from pathlib import Path


@dataclass
class ReviewMetrics:
    timestamp: str
    pr_number: int
    repository: str
    processing_time: float
    suggestions_count: int
    errors_count: int
    warnings_count: int
    info_count: int
    files_reviewed: int
    vector_db_queries: int
    llm_tokens_used: int
    

class MetricsCollector:
    def __init__(self, metrics_file: str = "data/metrics.jsonl"):
        self.metrics_file = Path(metrics_file)
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    def record_review_metrics(self, metrics: ReviewMetrics):
        """Record metrics for a code review"""
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(asdict(metrics)) + '\n')
    
    def get_summary_stats(self, days: int = 7) -> Dict:
        """Get summary statistics for the last N days"""
        if not self.metrics_file.exists():
            return {}
        
        # Read all metrics
        all_metrics = []
        with open(self.metrics_file, 'r') as f:
            for line in f:
                all_metrics.append(json.loads(line))
        
        # Calculate stats
        total_reviews = len(all_metrics)
        avg_processing_time = sum(m['processing_time'] for m in all_metrics) / total_reviews if total_reviews > 0 else 0
        total_suggestions = sum(m['suggestions_count'] for m in all_metrics)
        
        return {
            "total_reviews": total_reviews,
            "avg_processing_time_seconds": round(avg_processing_time, 2),
            "total_suggestions": total_suggestions,
            "avg_suggestions_per_review": round(total_suggestions / total_reviews, 2) if total_reviews > 0 else 0
        }
```

## Final Steps: Running the System

### Step 1: Complete Setup
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 4. Create directories
mkdir -p data/vector_db logs
```

### Step 2: Ingest Historical Data
```bash
# Ingest historical reviews from your repo
python scripts/ingest_reviews.py --repo facebook/react --max-prs 50

# The more historical data, the better the reviews!
```

### Step 3: Start the API Server
```bash
# Development mode
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose up -d
```

### Step 4: Test Manual Review
```bash
# Test with a real PR
curl -X POST "http://localhost:8000/api/v1/review/manual?repo_name=facebook/react&pr_number=28208"
```

### Step 5: Set Up GitHub Webhook

1. Go to your repository → Settings → Webhooks → Add webhook
2. Set:

