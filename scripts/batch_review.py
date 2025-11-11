# Process multiple PRs in batch to save on API calls

def batch_review_prs(repo_name: str, pr_numbers: List[int]):
    """Review multiple PRs in one go"""
    github_client = GitHubClient()
    pipeline = RAGPipeline()
    
    # Fetch all PRs
    prs = [github_client.get_pr_changes(repo_name, num) for num in pr_numbers]
    
    # Collect all code snippets
    all_snippets = []
    for pr in prs:
        for change in pr.changes:
            all_snippets.append(change.diff)
    
    # Batch embed (much cheaper!)
    embeddings = pipeline.embedding_service.embed_batch(all_snippets)
    
    # Continue with reviews...