# Security Configuration

## Overview
This document outlines the security measures implemented in the DCPlant dental franchise case-sharing platform.

## TLS/HTTPS Configuration

### Production Settings
- **TLS Termination**: Handled at the Nginx reverse proxy level
- **HSTS (HTTP Strict Transport Security)**: Enabled with 1-year duration
  - `SECURE_HSTS_SECONDS = 31536000`
  - `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
  - `SECURE_HSTS_PRELOAD = True`
- **SSL Redirect**: All HTTP traffic redirected to HTTPS
  - `SECURE_SSL_REDIRECT = True`
- **Secure Cookies**: Session and CSRF cookies marked as secure
  - `SESSION_COOKIE_SECURE = True`
  - `CSRF_COOKIE_SECURE = True`

## Security Headers

### Django SecurityMiddleware
The following security headers are configured in production:

- **X-Content-Type-Options**: `nosniff` - Prevents MIME type sniffing
- **X-Frame-Options**: `DENY` - Prevents clickjacking attacks
- **X-XSS-Protection**: `1; mode=block` - Enables XSS filtering

## PHI (Protected Health Information) Protection

### Data Minimization
- Minimal PHI exposure through API serializers
- De-identification flags on shared cases
- Audit logging for all PHI access

### Encryption
- **At Rest**: Database encryption handled by AWS RDS/PostgreSQL
- **In Transit**: All connections use TLS 1.2+
- **File Storage**: S3 server-side encryption enabled

## Authentication & Authorization

### Password Requirements
- Minimum length: 8 characters
- Django password validators:
  - UserAttributeSimilarityValidator
  - MinimumLengthValidator
  - CommonPasswordValidator
  - NumericPasswordValidator

### Session Security
- Session cookies:
  - HTTPOnly flag enabled
  - Secure flag in production
  - SameSite attribute set

## CORS Configuration

### Development
- `CORS_ALLOW_ALL_ORIGINS = True` (development only)

### Production
- Whitelist specific origins via `CORS_ALLOWED_ORIGINS` environment variable
- Credentials supported for authenticated requests

## File Upload Security

### Validation
- MIME type validation
- File size limits
- Virus scanning hook (implementation pending)

### Storage
- S3 presigned URLs for direct uploads
- Private bucket with IAM policies
- No public file access

## Audit Logging

### Tracked Events
- User authentication (login/logout)
- PHI access (read/write)
- File downloads
- Permission changes
- Data exports

### Log Security
- PHI fields masked in logs
- Structured JSON logging
- Sentry integration with PII scrubbing

## Environment Variables

### Secret Management
- Secrets stored in environment variables
- Never committed to version control
- `.env.example` provided for reference

### Required Secrets
- `SECRET_KEY`: Django secret key
- `DB_PASSWORD`: Database password
- `AWS_SECRET_ACCESS_KEY`: AWS credentials
- `EMAIL_HOST_PASSWORD`: SMTP password

## Nginx Configuration (Production)

### Recommended Headers
```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
```

### Rate Limiting
```nginx
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
```

## Security Checklist

### Pre-Deployment
- [ ] Change default `SECRET_KEY`
- [ ] Set `DEBUG = False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable HTTPS/TLS
- [ ] Set up firewall rules
- [ ] Configure database SSL
- [ ] Enable S3 encryption
- [ ] Set up Sentry error tracking
- [ ] Configure backup encryption

### Regular Maintenance
- [ ] Security updates for dependencies
- [ ] SSL certificate renewal
- [ ] Audit log review
- [ ] Access control review
- [ ] Backup restoration testing
- [ ] Security scanning

## Compliance

### HIPAA Considerations
- Business Associate Agreement (BAA) with cloud providers
- Encryption for PHI at rest and in transit
- Access controls and audit logging
- Data retention and disposal policies
- Incident response procedures

### Best Practices
- Principle of least privilege
- Defense in depth
- Regular security assessments
- Employee training
- Incident response planning