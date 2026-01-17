# Code Review Assistant - Production Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Code Review Assistant to production after all comprehensive enhancements have been applied.

## Pre-Deployment Checklist

### ✅ Verification Steps

1. **Code Quality**
   ```bash
   # Compile  all Python files
   python -m py_compile src/**/*.py
   
   # Code formatting
   black --check src/ tests/
   
   # Linting
   flake8 src/ tests/
   
   # Type checking
   mypy src/
   ```

2. **Security Scan**
   ```bash
   # Dependency security audit
   pip-audit
   
   # Check for known vulnerabilities
   safety check
   ```

3. **Testing**
   ```bash
   # Run all tests
   pytest tests/ -v --cov=src --cov-report=html
   
   # Security tests specifically
   pytest tests/test_security.py -v
   ```

---

## Environment Setup

### 1. Configure Environment Variables

Copy the production template:
```bash
cp .env.production.example .env
```

Update `.env` with your production values:

```bash
# Generate strong secrets
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Set these in your .env file
```

**Required Variables:**
- `OPENAI_API_KEY` or `GEMINI_API_KEY` (based on provider)
- `GITHUB_TOKEN`
- `GITHUB_WEBHOOK_SECRET`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `ADMIN_PASSWORD_HASH`

### 2. Set Admin Password

```bash
python scripts/setup_admin.py
```

This will prompt for a password and generate the hash for `.env`.

---

## Docker Deployment

### Option 1: Docker Compose (Recommended)

1. **Build the image:**
   ```bash
   docker-compose build
   ```

2. **Start the service:**
   ```bash
   docker-compose up -d
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f api
   ```

4. **Verify health:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

### Option 2: Manual Docker

1. **Build:**
   ```bash
   docker build -t code-review-assistant:latest .
   ```

2. **Run:**
   ```bash
   docker run -d \
     --name code-review-assistant \
     -p 8000:8000 \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/logs:/app/logs \
     --env-file .env \
     code-review-assistant:latest
   ```

3. **Health check:**
   ```bash
   docker exec code-review-assistant curl http://localhost:8000/api/v1/health
   ```

---

## Cloud Deployment

### AWS (ECS/Fargate)

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URL
docker tag code-review-assistant:latest YOUR_ECR_URL/code-review-assistant:latest
docker push YOUR_ECR_URL/code-review-assistant:latest

# Deploy to ECS
aws ecs create-service \
  --cluster YOUR_CLUSTER \
  --service-name code-review-assistant \
  --task-definition code-review-assistant \
  --desired-count 2
```

### Google Cloud (Cloud Run)

```bash
# Build and push to Artifact Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT/code-review-assistant

# Deploy
gcloud run deploy code-review-assistant \
  --image gcr.io/YOUR_PROJECT/code-review-assistant \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Azure (Container Instances)

```bash
# Build and push to ACR
az acr build --registry YOUR_REGISTRY --image code-review-assistant:latest .

# Deploy
az container create \
  --resource-group YOUR_RG \
  --name code-review-assistant \
  --image YOUR_REGISTRY.azurecr.io/code-review-assistant:latest \
  --ports 8000 \
  --environment-variables @.env
```

---

## GitHub Integration Setup

### 1. Create Webhook

1. Go to your repository → Settings → Webhooks → Add webhook
2. **Payload URL**: `https://your-domain.com/api/v1/webhook/github`
3. **Content type**: `application/json`
4. **Secret**: Use the value from `GITHUB_WEBHOOK_SECRET`
5. **Events**: Select "Pull requests"
6. **Active**: ✓ Enabled

### 2. Verify Webhook

After deployment, test the webhook:
1. Open a test PR
2. Check application logs for webhook receipt
3. Verify review comments appear on the PR

---

## Data Ingestion

### Ingest Historical Reviews

```bash
# Ingest from your repository
python scripts/ingest_reviews.py \
  --repo your-org/your-repo \
  --max-prs 100

# Verify ingestion
curl http://localhost:8000/api/v1/stats
```

### Optional: Add Style Guide

```bash
python scripts/ingest_style_guide.py \
  --file docs/style-guide.md \
  --language python
```

---

## Monitoring Setup

### 1. Prometheus Metrics

Metrics available at: `http://localhost:8000/metrics`

**Key Metrics:**
- `http_requests_total`
- `http_request_duration_seconds`
- `review_processing_time`
- `llm_api_calls_total`

### 2. Grafana Dashboard

Import the provided dashboard:
```bash
# Import grafana-dashboard.json into your Grafana instance
```

### 3. Log Aggregation

Configure log shipping to your log aggregation service:
```bash
# Example for ELK stack
docker run -d \
  --name filebeat \
  --volume="$(pwd)/logs:/logs:ro" \
  docker.elastic.co/beats/filebeat:8.0.0
```

---

## Security Hardening

### 1. Enable HTTPS

Use a reverse proxy (nginx, Apache, Traefik) with Let's Encrypt:

**Nginx Example:**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000" always;
}
```

### 2. Enable Authentication

In `.env`:
```bash
ENABLE_AUTHENTICATION=true
ADMIN_PASSWORD_HASH=your_bcrypt_hash_here
```

### 3. Configure CORS

In `.env`:
```bash
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

### 4. Rate Limiting

Adjust based on your needs:
```bash
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

---

## Post-Deployment Verification

### 1. Health Checks

```bash
# Basic health
curl https://your-domain.com/api/v1/health

# Detailed health
curl https://your-domain.com/api/v1/stats
```

### 2. Manual Review Test

```bash
curl -X POST https://your-domain.com/api/v1/review/manual \
  -H "Content-Type: application/json" \
  -d '{
    "repo_name": "facebook/react",
    "pr_number": 28208
  }'
```

### 3. Authentication Test

```bash
# Login
curl -X POST https://your-domain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

---

## Troubleshooting

### Common Issues

**1. Application won't start**
- Check logs: `docker-compose logs api`
- Verify all required environment variables are set
- Ensure API keys are valid

**2. GitHub webhook not working**
- Verify webhook secret matches `.env`
- Check webhook delivery in GitHub settings
- Ensure application is accessible from internet

**3. Reviews not generating**
- Check LLM provider API key is valid
- Verify API quota/rate limits
- Check logs for specific errors

**4. High memory usage**
- Reduce `TOP_K_RESULTS` in `.env`
- Limit historical review ingestion
- Consider scaling horizontally

---

## Backup & Recovery

### Backup Vector Database

```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Upload to S3 (example)
aws s3 cp backup-$(date +%Y%m%d).tar.gz s3://your-bucket/backups/
```

### Restore

```bash
# Download backup
aws s3 cp s3://your-bucket/backups/backup-20260117.tar.gz .

# Extract
tar -xzf backup-20260117.tar.gz

# Restart service
docker-compose restart
```

---

## Scaling Considerations

### Horizontal Scaling

For high traffic:

1. **Load Balancer**: Use nginx, HAProxy, or cloud LB
2. **Multiple Instances**: Run multiple containers
3. **Shared Vector DB**: Use persistent volume
4. **Distributed Caching**: Configure Redis

**Example with Docker Compose:**
```yaml
version: '3.8'
services:
  api:
    build: .
    deploy:
      replicas: 3
    volumes:
      - ./data:/app/data  # Shared volume
```

### Performance Tuning

```bash
# In .env
TOP_K_RESULTS=3  # Reduce for faster queries
SIMILARITY_THRESHOLD=0.8  # Higher = fewer results
MAX_TOKENS=500  # Reduce LLM response size
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Monitor application logs
- Check error rates
- Verify webhook deliveries

**Weekly:**
- Review security scan results
- Update dependencies if needed
- Analyze usage metrics

**Monthly:**
- Rotate API keys
- Backup vector database
- Review and optimize queries

### Updates

```bash
# Pull latest code
git pull

# Rebuild and deploy
docker-compose build
docker-compose up -d
```

---

## Support

For issues or questions:
- Check logs first: `docker-compose logs -f api`
- Review [SECURITY.md](SECURITY.md) for security concerns
- Check [README.md](README.md) for general documentation

---

## Production Checklist

Before going live, verify:

- [ ] All environment variables configured
- [ ] Strong secrets generated and set
- [ ] Admin password configured
- [ ] HTTPS enabled
- [ ] Authentication enabled
- [ ] CORS properly configured
- [ ] GitHub webhook created and tested
- [ ] Historical reviews ingested
- [ ] Monitoring configured
- [ ] Backups configured
- [ ] Health checks passing
- [ ] Manual review tested
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Documentation reviewed

---

**Your Code Review Assistant is now production-ready! 🚀**
