# Configuration

## Environment Variables

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

## Model Options

**OpenAI Models:**
- `gpt-4-turbo-preview` (recommended for quality)
- `gpt-4` (high quality, more expensive)
- `gpt-3.5-turbo` (faster, cheaper)

**Gemini Models:**
- `gemini-1.5-flash` (fast and efficient)
- `gemini-1.5-pro` (higher quality)
