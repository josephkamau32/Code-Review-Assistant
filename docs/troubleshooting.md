# Troubleshooting

## Common Issues

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

## Performance Tuning

**Slow Review Times:**
- Reduce `TOP_K_RESULTS` (try 3-5 instead of 10)
- Use faster models like `gpt-3.5-turbo` or `gemini-1.5-flash`
- Increase `SIMILARITY_THRESHOLD` to reduce irrelevant matches

**High Memory Usage:**
- Process reviews in smaller batches during ingestion
- Use lighter embedding models
- Implement proper cleanup of vector store connections

## Logs and Debugging

```bash
# View application logs
tail -f logs/app.log

# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn src.api.app:app --reload --log-level debug
```
