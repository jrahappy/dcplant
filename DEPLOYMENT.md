# DCPlant Deployment Guide

This guide provides instructions for deploying DCPlant to various cloud platforms.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Local Docker Deployment](#local-docker-deployment)
- [AWS EC2 Deployment](#aws-ec2-deployment)
- [AWS ECS/Fargate Deployment](#aws-ecsfargate-deployment)
- [Heroku Deployment](#heroku-deployment)
- [DigitalOcean Deployment](#digitalocean-deployment)
- [Azure Deployment](#azure-deployment)
- [Google Cloud Platform](#google-cloud-platform)

## Prerequisites

1. **Domain Name** (optional but recommended)
2. **SSL Certificate** (Let's Encrypt or other)
3. **SMTP Email Service** (Gmail, SendGrid, AWS SES)
4. **Cloud Storage** (AWS S3, Azure Blob, or local)
5. **PostgreSQL Database**
6. **Redis Cache** (optional but recommended)

## Local Docker Deployment

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/dcplant.git
cd dcplant

# Copy and configure environment variables
cp .env.production.example .env.production
# Edit .env.production with your values

# Build and run with Docker Compose
docker-compose up --build -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Access at http://localhost
```

## AWS EC2 Deployment

### 1. Launch EC2 Instance

- **AMI**: Ubuntu 22.04 LTS
- **Instance Type**: t3.medium (minimum)
- **Storage**: 30GB minimum (more for DICOM storage)
- **Security Group**:
  - Port 22 (SSH)
  - Port 80 (HTTP)
  - Port 443 (HTTPS)

### 2. Connect and Deploy

```bash
# Connect to EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Run deployment script
curl -O https://raw.githubusercontent.com/yourusername/dcplant/main/deploy/deploy_aws_ec2.sh
chmod +x deploy_aws_ec2.sh
./deploy_aws_ec2.sh
```

### 3. Configure Domain

1. Point your domain to EC2 Elastic IP
2. Setup SSL with Let's Encrypt:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 4. Setup S3 for Media Storage (Optional)

1. Create S3 bucket: `dcplant-media`
2. Create IAM user with S3 access
3. Update `.env.production`:
```env
USE_S3=True
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=dcplant-media
```

## AWS ECS/Fargate Deployment

### 1. Build and Push Docker Image

```bash
# Build image
docker build -t dcplant .

# Tag for ECR
docker tag dcplant:latest YOUR_ECR_URI:latest

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URI
docker push YOUR_ECR_URI:latest
```

### 2. Create ECS Resources

```bash
# Create cluster
aws ecs create-cluster --cluster-name dcplant-cluster

# Register task definition
aws ecs register-task-definition --cli-input-json file://deploy/deploy_aws_ecs.yml

# Create service
aws ecs create-service \
  --cluster dcplant-cluster \
  --service-name dcplant-service \
  --task-definition dcplant:1 \
  --desired-count 2 \
  --launch-type FARGATE
```

### 3. Setup Application Load Balancer

1. Create ALB in AWS Console
2. Configure target groups
3. Setup health checks to `/health/`
4. Point domain to ALB

## Heroku Deployment

### One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yourusername/dcplant)

### Manual Deploy

```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create your-dcplant-app

# Add PostgreSQL
heroku addons:create heroku-postgresql:standard-0

# Add Redis
heroku addons:create heroku-redis:premium-0

# Configure environment
heroku config:set SECRET_KEY='your-secret-key'
heroku config:set DJANGO_SETTINGS_MODULE='core.settings.production'

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate

# Create superuser
heroku run python manage.py createsuperuser
```

## DigitalOcean Deployment

### Using App Platform

1. **Connect GitHub Repository**
2. **Configure App**:
   - **Web Service**: DCPlant
   - **Database**: PostgreSQL
   - **Redis**: Add Redis
3. **Environment Variables**:
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URL=${db.DATABASE_URL}
   REDIS_URL=${redis.REDIS_URL}
   ```
4. **Deploy**

### Using Droplet

```bash
# Create Ubuntu 22.04 Droplet
# SSH into droplet
ssh root@your-droplet-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose

# Clone and deploy
git clone https://github.com/yourusername/dcplant.git
cd dcplant
docker-compose up -d
```

## Azure Deployment

### Using Azure Container Instances

```bash
# Create resource group
az group create --name dcplant-rg --location eastus

# Create PostgreSQL
az postgres server create \
  --resource-group dcplant-rg \
  --name dcplant-db \
  --admin-user dcplantadmin \
  --admin-password YourPassword123!

# Deploy container
az container create \
  --resource-group dcplant-rg \
  --name dcplant \
  --image dcplant:latest \
  --dns-name-label dcplant \
  --ports 80 \
  --environment-variables \
    DATABASE_URL=postgresql://... \
    SECRET_KEY=your-secret-key
```

## Google Cloud Platform

### Using Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT-ID/dcplant

# Deploy to Cloud Run
gcloud run deploy dcplant \
  --image gcr.io/PROJECT-ID/dcplant \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://...
```

## Production Checklist

### Security
- [ ] Change SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS
- [ ] Enable HTTPS/SSL
- [ ] Setup CORS properly
- [ ] Configure CSP headers
- [ ] Enable rate limiting

### Performance
- [ ] Configure Redis cache
- [ ] Setup CDN for static files
- [ ] Enable gzip compression
- [ ] Optimize database queries
- [ ] Setup monitoring (New Relic, Datadog)

### Backup & Recovery
- [ ] Automated database backups
- [ ] Media files backup to S3
- [ ] Disaster recovery plan
- [ ] Test restore procedures

### Monitoring
- [ ] Error tracking (Sentry)
- [ ] Application monitoring
- [ ] Uptime monitoring
- [ ] Log aggregation

## Environment Variables

### Required
```env
SECRET_KEY=your-very-secure-secret-key
DATABASE_URL=postgres://user:pass@host:5432/dbname
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### Optional
```env
# Redis
REDIS_URL=redis://localhost:6379/1

# AWS S3
USE_S3=True
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=dcplant-media

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Monitoring
SENTRY_DSN=your-sentry-dsn
```

## Troubleshooting

### Common Issues

1. **Static files not loading**
   ```bash
   docker-compose exec web python manage.py collectstatic --noinput
   ```

2. **Database connection errors**
   - Check DATABASE_URL format
   - Ensure PostgreSQL is running
   - Check network connectivity

3. **Large DICOM upload failures**
   - Increase nginx client_max_body_size
   - Adjust timeout settings
   - Check available disk space

4. **Permission errors**
   ```bash
   docker-compose exec web chown -R dcplant:dcplant /app/media
   ```

## Support

For deployment support:
- GitHub Issues: https://github.com/yourusername/dcplant/issues
- Documentation: https://dcplant-docs.com
- Email: support@dcplant.com

## License

DCPlant is licensed under the MIT License.