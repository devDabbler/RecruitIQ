# RecruitIQ Deployment Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
  - [Docker](#docker)
  - [Kubernetes](#kubernetes)
  - [AWS ECS](#aws-ecs)
  - [Azure App Service](#azure-app-service)
  - [Google Cloud Run](#google-cloud-run)
- [Scaling](#scaling)
- [Monitoring](#monitoring)
- [Backup & Recovery](#backup--recovery)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Infrastructure Requirements
- **Compute**: 4+ vCPUs, 8GB+ RAM (production)
- **Storage**: 50GB+ disk space
- **Networking**: HTTPS support (TLS 1.2+)
- **Database**: PostgreSQL 13+
- **Cache**: Redis 6+
- **Object Storage**: S3-compatible (MinIO, AWS S3, etc.)

### Software Dependencies
- Docker 20.10+
- Docker Compose 1.29+
- kubectl (for Kubernetes)
- Helm (for Kubernetes)

## Quick Start

### Local Development with Docker Compose

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/RecruitIQ.git
   cd RecruitIQ
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Run migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

5. **Access the application**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - Adminer (DB management): http://localhost:8080

## Configuration

### Environment Variables

#### Required
```
# Application
ENVIRONMENT=production
SECRET_KEY=your-secret-key
DOMAIN=yourdomain.com

# Database
POSTGRES_SERVER=db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=recruitiq

# Redis
REDIS_HOST=redis
REDIS_PASSWORD=your-redis-password

# Object Storage
STORAGE_PROVIDER=minio  # or aws_s3, azure_blob, gcp_storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
BUCKET_NAME=recruitiq

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Nebius AI (Required for resume parsing)
NEBIUS_API_KEY=your-nebius-api-key
NEBIUS_MODEL=microsoft/phi-4

# Rate Limiting
RATE_LIMIT=100/1m  # 100 requests per minute

# CORS (for frontend)
CORS_ORIGINS=https://yourdomain.com,http://localhost:8501
```

#### Optional
```
# Email
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=your-email-password
EMAIL_FROM=noreply@yourdomain.com

# Analytics
ENABLE_ANALYTICS=true
ANALYTICS_ID=your-analytics-id

# Resume Processing
RESUME_PARSING_STRATEGY=comprehensive  # 'fast' or 'comprehensive'
ENABLE_WEB_ENHANCEMENT=true  # Enhance profiles with web search

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json  # json or text

# Feature Flags
ENABLE_AI_ASSISTANT=true
ENABLE_MARKET_ANALYSIS=true
```

## Performance Considerations

### Resource Requirements

| Service        | CPU  | Memory | Storage | Notes                                  |
|----------------|------|--------|---------|----------------------------------------|
| Backend API    | 2-4  | 4-8GB  | 1GB     | Scales with traffic                    |
| Frontend       | 1-2  | 2-4GB  | 500MB   | Minimal resource usage                 |
| PostgreSQL     | 2-8  | 4-16GB | 50GB+   | Size based on data volume             |
| Redis          | 1-2  | 1-4GB  | 1GB     | In-memory cache                       |
| Nebius AI      | 2-4  | 8-16GB | 2GB     | For resume parsing                    |
| MinIO          | 1-2  | 2-4GB  | 100GB+  | For file storage                      |

### Scaling Recommendations

1. **Horizontal Scaling**:
   - Backend API: Scale to 2+ instances for high availability
   - Frontend: Use a CDN for static assets
   - Database: Consider read replicas for reporting

2. **Vertical Scaling**:
   - Increase database resources for large candidate volumes
   - Allocate more memory to Redis during high traffic

## Deployment Options

### Docker

#### Production Docker Compose

1. **Create a production docker-compose.yml**
   ```yaml
   version: '3.8'
   
   services:
     backend:
       image: your-registry/recruitiq-backend:latest
       restart: always
       env_file: .env
       ports:
         - "8000:8000"
       depends_on:
         - db
         - redis
         - minio
     
     frontend:
       image: your-registry/recruitiq-frontend:latest
       restart: always
       ports:
         - "8501:8501"
     
     db:
       image: postgres:13-alpine
       restart: always
       env_file: .env
       volumes:
         - postgres_data:/var/lib/postgresql/data
     
     redis:
       image: redis:6-alpine
       restart: always
       command: redis-server --requirepass ${REDIS_PASSWORD}
     
     minio:
       image: minio/minio
       restart: always
       command: server /data --console-address ":9001"
       environment:
         MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
         MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
       volumes:
         - minio_data:/data
   
   volumes:
     postgres_data:
     minio_data:
   ```

2. **Deploy**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Kubernetes

#### Prerequisites
- Kubernetes cluster (v1.20+)
- Helm (v3.0+)
- Ingress controller (Nginx, Traefik, etc.)
- Cert-manager (for TLS)

#### Deploy with Helm

1. **Add the Helm repository**
   ```bash
   helm repo add recruitiq https://charts.recruitiq.com
   helm repo update
   ```

2. **Create values.yaml**
   ```yaml
   # values.yaml
   global:
     domain: yourdomain.com
     
   frontend:
     replicaCount: 2
     
   backend:
     replicaCount: 3
     
   postgresql:
     enabled: true
     auth:
       database: recruitiq
       username: postgres
       password: your-db-password
     
   redis:
     enabled: true
     auth:
       password: your-redis-password
   ```

3. **Install the chart**
   ```bash
   helm install recruitiq recruitiq/recruitiq -f values.yaml
   ```

### AWS ECS

#### Prerequisites
- AWS CLI configured
- ECR repository
- RDS for PostgreSQL
- ElastiCache for Redis
- S3 bucket for storage

#### Deployment Steps

1. **Build and push Docker images**
   ```bash
   # Build images
   docker-compose -f docker-compose.build.yml build
   
   # Tag and push
   aws ecr get-login-password | docker login --username AWS --password-stdin your-account-id.dkr.ecr.region.amazonaws.com
   
   docker tag recruitiq-backend:latest your-account-id.dkr.ecr.region.amazonaws.com/recruitiq-backend:latest
   docker push your-account-id.dkr.ecr.region.amazonaws.com/recruitiq-backend:latest
   
   docker tag recruitiq-frontend:latest your-account-id.dkr.ecr.region.amazonaws.com/recruitiq-frontend:latest
   docker push your-account-id.dkr.ecr.region.amazonaws.com/recruitiq-frontend:latest
   ```

2. **Create ECS Task Definition**
   - Define containers for backend and frontend
   - Configure environment variables
   - Set up load balancing

3. **Create ECS Service**
   - Configure auto-scaling
   - Set up health checks
   - Configure logging with CloudWatch

## Scaling

### Horizontal Scaling
- **Backend**: Scale based on CPU/Memory usage
- **Frontend**: Use a CDN for static assets
- **Database**: Read replicas for reporting
- **Cache**: Redis cluster for high availability

### Vertical Scaling
- **Database**: Upgrade instance size for larger datasets
- **Cache**: Increase memory allocation

## Monitoring & Observability

### Key Metrics to Monitor

#### Application Metrics
- **API Response Times**: P95 < 500ms
- **Error Rates**: < 1% of requests
- **Queue Lengths**: Processing queues should be near zero
- **Cache Hit Rate**: Target > 90%

#### Resume Parsing Metrics
- **Parsing Success Rate**: > 95%
- **Average Processing Time**: < 3s (fast), < 10s (comprehensive)
- **Fallback Rate**: < 5% (fallback to regex extraction)
- **Quality Scores**: Monitor distribution of resume quality scores

### Logging

Structured JSON logs are available with the following fields:
```json
{
  "timestamp": "2025-08-28T18:45:30Z",
  "level": "INFO",
  "service": "resume_parser",
  "message": "Successfully parsed resume",
  "duration_ms": 1245,
  "strategy": "comprehensive",
  "resume_id": "res_12345",
  "file_size_kb": 245
}
```

### Alerting

Set up alerts for:
- High error rates (> 5% for 5 minutes)
- Increased response times (P95 > 1s)
- Queue buildup (> 100 items)
- Low cache hit rate (< 80%)
- Failed health checks

### Logging
- **Backend**: JSON-formatted logs with log levels
- **Frontend**: Client-side error tracking
- **Infrastructure**: Cloud provider logs (CloudWatch, Stackdriver, etc.)

### Metrics
- **Application**: Response times, error rates
- **Database**: Query performance, connection pool
- **Infrastructure**: CPU, memory, network usage

### Alerts
- Set up alerts for:
  - High error rates
  - Service unavailability
  - Resource constraints

## Backup & Recovery

### Database Backups
- **Automated Backups**: Daily snapshots
- **Point-in-time Recovery**: 7-day retention
- **Off-site Storage**: Copy backups to S3/Blob Storage

### Application Data
- **Object Storage**: Versioning enabled
- **Regular Exports**: Weekly exports of critical data

### Disaster Recovery
- **Multi-region**: Deploy to multiple regions
- **Backup Testing**: Regular restore tests
- **Runbook**: Documented recovery procedures

## Upgrading

### Version Compatibility
- Check release notes for breaking changes
- Test upgrades in staging first
- Follow semantic versioning

### Upgrade Procedure
1. **Backup** all data
2. **Deploy** new version
3. **Run migrations**
4. **Verify** functionality
5. **Monitor** for issues

## Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database logs
docker-compose logs db

# Test connection
psql -h localhost -U postgres -d recruitiq
```

#### Frontend Not Loading
- Clear browser cache
- Check browser console for errors
- Verify API endpoints are accessible

#### High CPU/Memory Usage
```bash
# Check container resources
docker stats

# Get process list inside container
docker-compose exec backend top
```

### Getting Help
- Check logs: `docker-compose logs -f`
- View documentation: [docs.recruitiq.com](https://docs.recruitiq.com)
- Open a support ticket: support@recruitiq.com

---
*Last Updated: August 2025*
