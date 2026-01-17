# Code Review Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)

An intelligent, AI-powered code review assistant that leverages Retrieval-Augmented Generation (RAG) to provide context-aware, consistent code reviews based on historical review patterns and customizable style guides.

## 🌟 Key Features

- **🤖 Intelligent Reviews**: Uses advanced RAG technology to analyze code changes and provide contextual suggestions
- **📚 Learning System**: Continuously learns from historical code reviews to maintain consistency across your team
- **🎯 Customizable Standards**: Supports custom style guides and coding standards for different languages
- **🔄 Automated Integration**: Seamless GitHub webhook integration for automatic PR reviews
- **📊 Analytics & Monitoring**: Built-in metrics collection and performance monitoring
- **🚀 Multiple LLM Support**: Choose between OpenAI GPT models or Google Gemini for reviews
- **🐳 Container Ready**: Full Docker support for easy deployment
- **⚡ High Performance**: Optimized for speed with batch processing and caching

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub PR     │────│   FastAPI        │────│   RAG Pipeline  │
│   Webhook       │    │   Backend        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Vector Store   │    │   LLM Service   │
                       │  (ChromaDB)     │    │  (GPT/Gemini)   │
                       └─────────────────┘    └─────────────────┘
                                ▲                        │
                                │                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ Historical      │    │  Embedding     │
                       │ Reviews         │    │  Service       │
                       └─────────────────┘    └─────────────────┘
```

### Core Components

- **API Layer**: FastAPI-based REST API with webhook handling
- **RAG Pipeline**: Orchestrates the retrieval-augmented generation process
- **Vector Store**: ChromaDB for efficient similarity search of historical reviews
- **Embedding Service**: Converts code and reviews into vector representations
- **LLM Service**: Generates intelligent review suggestions using context
- **GitHub Integration**: Handles PR fetching, webhook verification, and comment posting

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- GitHub Personal Access Token with repo permissions
- OpenAI API key (or Google Gemini API key)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/code-review-assistant.git
   cd code-review-assistant
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   Required environment variables:
   ```bash
   # API Keys
   OPENAI_API_KEY=sk-your-openai-key-here
   GITHUB_TOKEN=ghp_your-github-token-here
   GITHUB_WEBHOOK_SECRET=your-webhook-secret

   # Optional: Use Gemini instead of OpenAI
   GEMINI_API_KEY=your-gemini-api-key
   LLM_PROVIDER=gemini
   ```

### Data Ingestion

Populate the vector database with historical reviews:

```bash
# Ingest reviews from your repository
python scripts/ingest_reviews.py --repo your-org/your-repo --max-prs 100

# Optional: Add custom style guide
python scripts/ingest_style_guide.py --file docs/style-guide.md --language python
```

### Running the Application

**Development Mode:**
```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

**Production with Docker:**
```bash
docker-compose up -d
```

**Access the Web Dashboard:**
Once running, visit `http://localhost:8000` in your browser for the modern web interface with analytics and manual review capabilities.

**Manual Testing:**
```bash
# Test with a real PR
curl -X POST "http://localhost:8000/api/v1/review/manual?repo_name=facebook/react&pr_number=28208"
```

## 📖 API Documentation

### Endpoints

#### POST `/api/v1/webhook/github`
Handles GitHub webhook events for automatic PR reviews.

**Headers:**
- `X-Hub-Signature-256`: Webhook signature for verification

**Triggers review on:**
- PR opened
- PR synchronized (new commits)
- PR reopened

#### POST `/api/v1/review/manual`
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

#### POST `/api/v1/feedback`
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

#### GET `/api/v1/stats`
Get system statistics and health information.

#### GET `/api/v1/health`
Basic health check endpoint.

### Supported Languages

- Python
- JavaScript/TypeScript
- Java
- Go
- Rust
- C++
- Ruby
- PHP

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT models | - | Yes* |
| `GEMINI_API_KEY` | Google Gemini API key | - | Yes* |
| `GITHUB_TOKEN` | GitHub personal access token | - | Yes |
| `GITHUB_WEBHOOK_SECRET` | Secret for webhook verification | - | Yes |
| `LLM_PROVIDER` | LLM provider (`openai` or `gemini`) | `openai` | No |
| `LLM_MODEL` | Specific model to use | `gpt-4-turbo-preview` | No |
| `EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` | No |
| `TOP_K_RESULTS` | Number of similar reviews to retrieve | `5` | No |
| `SIMILARITY_THRESHOLD` | Minimum similarity score | `0.7` | No |
| `TEMPERATURE` | LLM temperature for generation | `0.3` | No |
| `API_HOST` | Server host | `0.0.0.0` | No |
| `API_PORT` | Server port | `8000` | No |

*Either OpenAI or Gemini API key is required

### Model Options

**OpenAI Models:**
- `gpt-4-turbo-preview` (recommended for quality)
- `gpt-4` (high quality, more expensive)
- `gpt-3.5-turbo` (faster, cheaper)

**Gemini Models:**
- `gemini-1.5-flash` (fast and efficient)
- `gemini-1.5-pro` (higher quality)

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_rag_pipeline.py -v

# Run integration tests
pytest tests/test_integration.py
```

### Test Structure

```
tests/
├── test_end_to_end.py      # Full pipeline tests
├── test_integration.py     # Component integration tests
├── test_rag_pipeline.py    # RAG pipeline unit tests
└── __init__.py
```

## 🔧 Troubleshooting

### Common Issues

**"No reviews found in vector database"**
- Run the ingestion script first: `python scripts/ingest_reviews.py --repo your-repo --max-prs 50`
- Ensure you have at least 20-50 historical reviews for meaningful results

**"Rate limit exceeded"**
- OpenAI: Upgrade your plan or reduce request frequency
- GitHub: Check your token permissions and rate limits
- Add retry logic or implement request throttling

**"Webhook signature invalid"**
- Verify `GITHUB_WEBHOOK_SECRET` matches your GitHub webhook configuration
- Ensure the secret is URL-safe and properly encoded

**"Embedding service failed"**
- Check your API keys are valid and have sufficient credits
- Verify network connectivity to OpenAI/Gemini APIs
- Try switching between OpenAI and Gemini providers

**"PR changes not detected"**
- Ensure the PR has actual code changes (not just metadata)
- Check that the repository is accessible with your GitHub token
- Verify the PR number is correct

### Performance Tuning

**Slow Review Times:**
- Reduce `TOP_K_RESULTS` (try 3-5 instead of 10)
- Use faster models like `gpt-3.5-turbo` or `gemini-1.5-flash`
- Increase `SIMILARITY_THRESHOLD` to reduce irrelevant matches

**High Memory Usage:**
- Process reviews in smaller batches during ingestion
- Use lighter embedding models
- Implement proper cleanup of vector store connections

### Logs and Debugging

```bash
# View application logs
tail -f logs/app.log

# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn src.api.app:app --reload --log-level debug
```

## 🚀 Deployment

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f api

# Scale the service
docker-compose up -d --scale api=3
```

### Production Considerations

- Use environment-specific configuration files
- Set up proper logging aggregation (ELK stack, etc.)
- Implement health checks and monitoring
- Configure backup strategies for vector database
- Set up CI/CD pipelines for automated deployment

### Cloud Deployment Options

**AWS:**
```bash
# ECS with Fargate
aws ecs create-service --service-name code-review-assistant \
  --task-definition cra-task \
  --desired-count 2
```

**Google Cloud:**
```bash
# Cloud Run
gcloud run deploy code-review-assistant \
  --source . \
  --platform managed \
  --region us-central1
```

**Azure:**
```bash
# Container Instances
az container create \
  --resource-group myResourceGroup \
  --name cra-container \
  --image myregistry.azurecr.io/cra:latest \
  --ports 8000
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Set up pre-commit hooks: `pip install pre-commit && pre-commit install`
4. Make your changes
5. Add tests for new features
6. Ensure all tests pass: `pytest`
7. Update documentation if needed
8. Commit your changes: `git commit -m 'Add amazing feature'`
9. Push to the branch: `git push origin feature/amazing-feature`
10. Open a Pull Request

### Code Standards

- Follow PEP 8 for Python code
- Use type hints for all function parameters and return values
- Write comprehensive docstrings
- Add unit tests for all new functionality
- Ensure code coverage remains above 80%

### Testing Guidelines

- Write tests for both happy path and error scenarios
- Mock external API calls in unit tests
- Include integration tests for critical paths
- Test with different LLM providers when possible

## 📊 Performance & Metrics

### Typical Performance

- **Review Time**: 5-15 seconds per PR (depends on changes and model)
- **Cost**: $0.01-0.05 per review (GPT-4 Turbo)
- **Accuracy**: Improves with more historical data (50+ reviews recommended)
- **Memory Usage**: ~500MB base + ~100MB per 1000 reviews

### Monitoring

Track these key metrics:
- Review processing time
- API response times
- Error rates by category
- User feedback scores
- Vector database query performance

## 🔮 Future Enhancements

- [ ] Fine-tuned models on specific codebases
- [ ] Support for additional programming languages
- [ ] Integration with Jira/Linear for issue tracking
- [ ] A/B testing framework for review quality
- [ ] Custom evaluation metrics and benchmarks
- [x] Web dashboard for analytics and management
- [ ] Slack/Discord bot integration
- [ ] IDE plugins (VS Code, IntelliJ)
- [ ] Batch processing for multiple PRs
- [ ] Advanced filtering and customization options

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) for the API framework
- Powered by [LangChain](https://www.langchain.com/) for LLM orchestration
- Vector storage provided by [ChromaDB](https://www.trychroma.com/)
- Embeddings generated using [OpenAI](https://openai.com/) and [Google Gemini](https://gemini.google.com/)

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/code-review-assistant/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/code-review-assistant/discussions)
- **Documentation**: [Wiki](https://github.com/your-username/code-review-assistant/wiki)

---

**Made with ❤️ for developers, by developers**
