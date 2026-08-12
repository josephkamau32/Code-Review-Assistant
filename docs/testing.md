# Testing

## Running Tests

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

## Test Structure

```
tests/
├── test_end_to_end.py      # Full pipeline tests
├── test_integration.py     # Component integration tests
├── test_rag_pipeline.py    # RAG pipeline unit tests
└── __init__.py
```
