# Architecture

```text
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

## Core Components

- **API Layer**: FastAPI-based REST API with webhook handling
- **RAG Pipeline**: Orchestrates the retrieval-augmented generation process
- **Vector Store**: ChromaDB for efficient similarity search of historical reviews
- **Embedding Service**: Converts code and reviews into vector representations
- **LLM Service**: Generates review suggestions using context
- **GitHub Integration**: Handles PR fetching, webhook verification, and comment posting
