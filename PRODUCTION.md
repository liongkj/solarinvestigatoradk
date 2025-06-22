# Production Deployment Guide

## Overview
This guide explains how to deploy the Solar Investigator ADK application in production using Docker Compose.

## Prerequisites
- Docker and Docker Compose installed
- SSL certificates (for HTTPS - optional)
- Environment variables configured

## Quick Start

### 1. Environment Setup
```bash
# Copy the example environment file
cp .env.prod.example .env.prod

# Edit the environment file with your actual values
vim .env.prod
```

### 2. Required Environment Variables
Edit `.env.prod` and set:
- `POSTGRES_PASSWORD`: Secure database password
- `GEMINI_API_KEY`: Your Google Gemini API key
- `DOMAIN`: Your domain name (optional)

### 3. Deploy
```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. SSL/HTTPS Setup (Optional)
If you want to enable HTTPS:

1. Place your SSL certificates in `./nginx/ssl/`:
   - `cert.pem` (certificate)
   - `key.pem` (private key)

2. Uncomment SSL configuration in `nginx/nginx.conf`:
   ```nginx
   ssl_certificate /etc/nginx/ssl/cert.pem;
   ssl_certificate_key /etc/nginx/ssl/key.pem;
   ```

3. Restart nginx:
   ```bash
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

## Production Features

### Backend (FastAPI)
- ✅ Multi-stage build for smaller image size
- ✅ Non-root user for security
- ✅ Health checks
- ✅ Production dependencies only
- ✅ Environment-based configuration

### Frontend (Angular)
- ✅ Production build with optimization
- ✅ Nginx for serving static files
- ✅ Gzip compression
- ✅ Security headers
- ✅ Caching for static assets

### Database (PostgreSQL)
- ✅ Persistent volumes
- ✅ Health checks
- ✅ Secure password configuration

### Nginx Reverse Proxy
- ✅ Load balancing
- ✅ Rate limiting
- ✅ Security headers
- ✅ SSL termination (optional)
- ✅ Gzip compression

## Monitoring and Maintenance

### Health Checks
- Backend: `GET /health`
- Database: Built-in PostgreSQL health check
- All services have Docker health checks

### Logs
```bash
# View all logs
docker-compose -f docker-compose.prod.yml logs

# View specific service logs
docker-compose -f docker-compose.prod.yml logs frontend
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs adk_db
```

### Updates
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### Backup Database
```bash
# Create backup
docker exec adk_db_prod pg_dump -U adk_user adk_db > backup.sql

# Restore backup
docker exec -i adk_db_prod psql -U adk_user adk_db < backup.sql
```

## Security Considerations

1. **Environment Variables**: Never commit `.env.prod` to version control
2. **Database Password**: Use a strong, unique password
3. **SSL Certificates**: Use valid SSL certificates for production
4. **Firewall**: Configure firewall to only allow necessary ports
5. **Updates**: Keep Docker images and dependencies updated

## Troubleshooting

### Common Issues

1. **Services not starting**: Check logs with `docker-compose logs`
2. **Database connection issues**: Verify `DATABASE_URL` in environment
3. **SSL issues**: Check certificate paths and permissions
4. **Port conflicts**: Ensure ports 80/443 are available

### Performance Tuning

1. **Database**: Consider connection pooling for high traffic
2. **Nginx**: Adjust worker processes based on CPU cores
3. **Backend**: Configure uvicorn workers for production load

## Scaling

For high-traffic scenarios, consider:
- Multiple backend replicas
- External database (managed PostgreSQL)
- Redis for caching
- Container orchestration (Kubernetes)

## Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Build | Development build | Optimized production build |
| Server | Hot reload | Static files with Nginx |
| Database | Local SQLite/Dev DB | PostgreSQL with backups |
| SSL | HTTP only | HTTPS with certificates |
| Logging | Debug level | Info/Warn level |
| Security | Relaxed CORS | Strict security headers |
