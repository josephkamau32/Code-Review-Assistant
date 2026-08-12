# Code Review Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![CI](https://github.com/josephkamau32/Code-Review-Assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/josephkamau32/Code-Review-Assistant/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/josephkamau32/Code-Review-Assistant/branch/main/graph/badge.svg)](https://codecov.io/gh/josephkamau32/Code-Review-Assistant)

A context-aware code review assistant that uses Retrieval-Augmented Generation (RAG) to provide consistent code reviews based on historical review patterns and customizable style guides. It integrates seamlessly with GitHub webhooks to automate pull request reviews.

![Demo Placeholder - Add a 10s GIF here](docs/assets/demo.gif)

[View Live Demo](https://demo.your-domain.com) *(Request access via issues)*

## Key Features

- **Contextual Reviews**: Uses RAG to analyze code changes and provide suggestions based on past reviews.
- **Continuous Learning**: Ingests historical PRs to maintain consistency across your team's specific coding standards.
- **Customizable Guidelines**: Supports custom style guides and rules across multiple programming languages (Python, TS, Go, etc.).
- **GitHub Integration**: Handles PR fetching, webhook verification, and automatic comment posting.
- **Container Deployment**: Includes Docker support with a FastAPI backend and ChromaDB vector store.

## Documentation

- [Architecture & Design](docs/architecture.md)
- [Quick Start & Configuration](docs/configuration.md)
- [API Documentation](docs/api.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Testing](docs/testing.md)
- [Troubleshooting](docs/troubleshooting.md)

## Quick Start

```bash
git clone https://github.com/your-username/code-review-assistant.git
cd code-review-assistant
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GITHUB_TOKEN and OPENAI_API_KEY
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

## Contributing

We welcome contributions! Please refer to the guidelines in our issues and discussions. Follow PEP 8 and ensure tests pass (`pytest --cov`).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
