# Security Policy

## Supported Versions

We actively support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. Do Not Disclose Publicly

Please do not open a public GitHub issue for security vulnerabilities. This helps protect users until a fix is available.

### 2. Report Via Email

Send details to: **security@your-domain.com** (Please update with your actual security contact)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### 3. Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Varies by severity (typically 30-90 days)

## Security Best Practices

When deploying this application:

### Required Security Measures

1. **Environment Variables**
   - Never commit `.env` files to version control
   - Use strong, random secrets for `JWT_SECRET_KEY` and `SECRET_KEY`
   - Rotate API keys regularly

2. **Authentication**
   - Enable authentication in production (`ENABLE_AUTHENTICATION=true`)
   - Use strong admin passwords (min 12 characters, mixed case, numbers, symbols)
   - Set `ADMIN_PASSWORD_HASH` using the setup script

3. **Network Security**
   - Use HTTPS in production (never HTTP)
   - Configure `CORS_ORIGINS` to only allowed domains
   - Use `GITHUB_WEBHOOK_SECRET` for webhook verification

4. **API Keys**
   - Store OpenAI/Gemini API keys securely
   - Use environment-specific keys
   - Monitor API usage for anomalies

5. **Docker Security**
   - Run containers as non-root user (already configured)
   - Keep base images updated
   - Scan images for vulnerabilities regularly

### Recommended Security Headers

Configure your reverse proxy (nginx, Apache, etc.) to add:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self'" always;
```

## Known Security Considerations

1. **Rate Limiting**: Built-in rate limiting is enabled by default. Adjust `RATE_LIMIT_REQUESTS` based on your needs.

2. **Input Validation**: All user inputs are validated using Pydantic models. Additional validation in API routes.

3. **Dependency Security**: Regular dependency updates are recommended. Run `pip-audit` to check for known vulnerabilities.

4. **Logging**: Sensitive data (API keys, tokens) are not logged. Review logs before sharing.

## Security Checklist for Production

- [ ] All secrets are stored securely (environment variables, secrets manager)
- [ ] Authentication is enabled
- [ ] Strong admin password is set
- [ ] CORS origins are configured
- [ ] HTTPS is enforced
- [ ] Webhook secret is configured for GitHub integration
- [ ] Rate limiting is properly configured
- [ ] Dependencies are up to date
- [ ] Docker image is scanned for vulnerabilities
- [ ] Monitoring and alerting are configured

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [GitHub Webhook Security](https://docs.github.com/en/developers/webhooks-and-events/webhooks/securing-your-webhooks)
