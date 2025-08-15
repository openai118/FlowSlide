# FlowSlide Docker Deployment Guide

## 🐳 Docker Hub Repository

**Registry**: `openai118/flowslide`

## 📋 Build and Push Commands

### Local Build
```bash
# Build image
docker build -t openai118/flowslide:latest .

# Tag for specific version
docker tag openai118/flowslide:latest openai118/flowslide:v2.0.0

# Push to Docker Hub
docker push openai118/flowslide:latest
docker push openai118/flowslide:v2.0.0
```

### Using Docker Compose
```bash
# Build and start locally
docker-compose up --build

# Build with PostgreSQL
docker-compose -f docker-compose.postgres.yml up --build
```

## 🚀 Quick Start with Docker Hub Image

### Option 1: Standalone Container
```bash
docker run -d \
  --name flowslide \
  -p 8000:8000 \
  -e DATABASE_URL="sqlite:///app/data/flowslide.db" \
  -v flowslide_data:/app/data \
  openai118/flowslide:latest
```

### Option 2: With PostgreSQL
```yaml
version: '3.8'
services:
  flowslide:
    image: openai118/flowslide:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/flowslide_db
    depends_on:
      - postgres
      
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: flowslide_db
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
```

## 🔧 Environment Variables

### Required
- `DATABASE_URL`: Database connection string

### Optional
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `ZHIPU_API_KEY`: Zhipu AI API key
- `DEEPSEEK_API_KEY`: DeepSeek API key
- `ANTHROPIC_API_KEY`: Anthropic Claude API key
- `GEMINI_API_KEY`: Google Gemini API key

### Storage & Backup
- `R2_ACCESS_KEY_ID`: Cloudflare R2 access key
- `R2_SECRET_ACCESS_KEY`: Cloudflare R2 secret
- `R2_ENDPOINT`: Cloudflare R2 endpoint
- `R2_BUCKET_NAME`: Cloudflare R2 bucket name

## 📊 Health Check

The container includes built-in health checks:
- HTTP endpoint: `http://localhost:8000/health`
- Database connectivity verification
- Resource availability checks

## 🔍 Monitoring

Access logs and metrics:
```bash
# View application logs
docker logs flowslide

# Monitor with docker-compose
docker-compose logs -f flowslide
```

## 📁 Volume Mounts

Recommended persistent volumes:
- `/app/data` - Database and application data
- `/app/uploads` - User uploaded files
- `/app/logs` - Application logs
- `/app/temp` - Temporary files and cache

## 🔄 Updates

```bash
# Pull latest version
docker pull openai118/flowslide:latest

# Restart with new image
docker-compose down
docker-compose up -d
```

## 🏗️ GitHub Actions Integration

For automated builds, create `.github/workflows/docker.yml`:

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
      
    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
        
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: openai118/flowslide
        
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
```

## 📚 Documentation

- Main Repository: https://github.com/openai118/FlowSlide
- Docker Hub: https://hub.docker.com/r/openai118/flowslide
- Issues: https://github.com/openai118/FlowSlide/issues

License: Apache License 2.0 (see LICENSE)

## 🚪 Access

- 🏠 Public Home: http://localhost:8000/home
- 🌐 Web Console: http://localhost:8000/web
- 📚 API Docs: http://localhost:8000/docs
- 🩺 Health Check: http://localhost:8000/health
