# Nippon India Mutual Fund RAG System - Deployment Plan

## 📋 Overview
This document outlines the comprehensive deployment strategy for the Nippon India Mutual Fund RAG System, covering automated scheduling, backend deployment, and frontend deployment.

## 🎯 Deployment Architecture

### **Production Environment Setup**
- **Scheduler**: GitHub Actions (Automated CI/CD)
- **Backend**: Render (Python FastAPI)
- **Frontend**: Vercel (Next.js)
- **Database**: SQLite with Vector Extensions
- **Monitoring**: Built-in health checks and logging

---

## 🔄 GitHub Actions - Automated Scheduling

### **Scheduler Workflow Configuration**
```yaml
# .github/workflows/scheduler.yml
name: Data Ingestion Scheduler
on:
  schedule:
    # Run daily at 2:00 AM IST (8:30 PM UTC previous day)
    - cron: '30 20 * * *'
    # Run on manual trigger
    workflow_dispatch:
  workflow_dispatch:
jobs:
  data-ingestion:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install requests beautifulsoup4 pandas numpy
      
      - name: Run data ingestion pipeline
        run: |
          python scripts/run_scheduler_locally.py
        env:
          PYTHONPATH: ${{ github.workspace }}
      
      - name: Upload logs
        uses: actions/upload-artifact@v3
        with:
          name: scheduler-logs
          path: logs/
          retention-days: 30
```

### **CI/CD Pipeline Workflow**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      
      - name: Run tests
        run: |
          pytest tests/ -v
      
      - name: Run scheduler test
        run: |
          python scripts/test_scheduler_simple.py

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to Render
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RENDER_DEPLOY_HOOK }}" \
            -H "Content-Type: application/json" \
            -d '{"branch": "main"}' \
            https://api.render.com/v1/services/${{ secrets.RENDER_SERVICE_ID }}/deploys

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v20
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./nippon-india-frontend
```

---

## 🖥 Backend Deployment - Render

### **Render Service Configuration**
```yaml
# render.yaml
services:
  - type: web
    name: nippon-india-rag-api
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python src/api/multi_threaded_api_gateway.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
      - key: PORT
        value: 10000
    healthCheckPath: /api/health
    healthCheckTimeout: 300
    autoDeploy: true
```

### **Environment Variables for Production**
```bash
# Render Environment Variables
PYTHON_VERSION=3.11
PORT=10000
NEXT_PUBLIC_API_URL=https://nippon-india-rag-api.onrender.com
LOG_LEVEL=INFO
MAX_WORKERS=10

# Database Configuration
DATABASE_URL=sqlite:///data/nippon_funds.db
VECTOR_STORE_PATH=data/vector_store
EMBEDDINGS_PATH=data/embeddings

# Security
SECRET_KEY=${RANDOM_SECRET_KEY}
CORS_ORIGINS=https://nippon-india-faq.vercel.app,https://nipponindiaim.com
```

### **Backend Deployment Script**
```bash
#!/bin/bash
# scripts/deploy_backend.sh

echo "🚀 Deploying Nippon India RAG API to Render..."

# Check if we're on main branch
if [[ "$GITHUB_REF" != "refs/heads/main" ]]; then
    echo "⚠️  Skipping deployment: Not on main branch"
    exit 0
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run health check
echo "🏥 Running health check..."
python -c "
import requests
import sys
try:
    response = requests.get('http://localhost:8000/api/health', timeout=10)
    if response.status_code == 200:
        print('✅ Backend health check passed')
        sys.exit(0)
    else:
        print('❌ Backend health check failed')
        sys.exit(1)
except Exception as e:
    print(f'❌ Health check error: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Backend ready for deployment"
else
    echo "❌ Backend health check failed"
    exit 1
fi

echo "🎉 Backend deployment complete!"
```

---

## 🎨 Frontend Deployment - Vercel

### **Vercel Configuration**
```json
// vercel.json
{
  "version": 2,
  "name": "nippon-india-faq",
  "builds": [
    {
      "src": "nippon-india-frontend/package.json",
      "use": "@vercel/next"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/index.html"
    }
  ],
  "env": {
    "NEXT_PUBLIC_API_URL": "https://nippon-india-rag-api.onrender.com"
  },
  "functions": {
    "nippon-india-frontend/src/app/api/chat/route.js": {
      "maxDuration": 30
    }
  }
}
```

### **Frontend Build Configuration**
```javascript
// nippon-india-frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  experimental: {
    serverActions: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
    ];
  },
  webpack: (config) => {
    config.resolve.fallback = {
      fs: false,
    };
    return config;
  },
};

module.exports = nextConfig;
```

---

## 🔧 Environment Setup

### **Required Environment Variables**

#### **GitHub Secrets**
```bash
# GitHub Repository Secrets
RENDER_DEPLOY_HOOK=your_render_deploy_hook
RENDER_SERVICE_ID=your_render_service_id
VERCEL_TOKEN=your_vercel_token
VERCEL_ORG_ID=your_vercel_org_id
VERCEL_PROJECT_ID=your_vercel_project_id
```

#### **Render Environment Variables**
```bash
# Production Backend Variables
PYTHON_VERSION=3.11
PORT=10000
NEXT_PUBLIC_API_URL=https://nippon-india-rag-api.onrender.com
LOG_LEVEL=INFO
MAX_WORKERS=10
SECRET_KEY=your_production_secret_key
CORS_ORIGINS=https://nippon-india-faq.vercel.app,https://nipponindiaim.com
```

#### **Vercel Environment Variables**
```bash
# Production Frontend Variables
NEXT_PUBLIC_API_URL=https://nippon-india-rag-api.onrender.com
NEXT_PUBLIC_APP_NAME=Nippon India Mutual Fund FAQ
NEXT_PUBLIC_VERSION=2.0.0
```

---

## 📊 Monitoring & Logging

### **Health Check Endpoints**
```bash
# Backend Health Check
GET /api/health
Response:
{
  "status": "healthy",
  "timestamp": "2026-05-07T10:30:00Z",
  "active_threads": 5,
  "active_sessions": 3,
  "pending_queries": 0,
  "uptime": "2 days, 14 hours"
}

# Frontend Health Check
GET /api/health (via Next.js API route)
Response:
{
  "status": "healthy",
  "frontend": "Next.js 14.0.0",
  "backend_connection": "connected",
  "last_check": "2026-05-07T10:30:00Z"
}
```

### **Logging Strategy**
```python
# Centralized Logging Configuration
import logging
import sys
from datetime import datetime

def setup_production_logging():
    """Setup production logging with structured format"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/app_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

# Usage in production
logger = setup_production_logging()
logger.info("🚀 Nippon India RAG System started")
logger.info("📊 Active threads: %d", active_threads)
logger.info("🔗 Backend URL: %s", os.getenv('NEXT_PUBLIC_API_URL'))
```

---

## 🚀 Deployment Commands

### **Local Development**
```bash
# Start Backend
cd "d:\Challagulla Dedipya\Vibe Coding\P2"
python src/api/multi_threaded_api_gateway.py

# Start Frontend  
cd "d:\Challagulla Dedipya\Vibe Coding\P2\nippon-india-frontend"
npm run dev
```

### **Production Deployment**
```bash
# Deploy Backend (Triggered by GitHub Actions)
curl -X POST \
  -H "Authorization: Bearer $RENDER_DEPLOY_HOOK" \
  -H "Content-Type: application/json" \
  -d '{"branch": "main"}' \
  https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys

# Deploy Frontend (Triggered by GitHub Actions)
vercel --prod --token $VERCEL_TOKEN
```

### **Manual Deployment Commands**
```bash
# Manual Backend Deployment
scripts/deploy_backend.sh

# Manual Frontend Deployment
cd nippon-india-frontend
vercel --prod
```

---

## 🔒 Security Configuration

### **Production Security Headers**
```python
# Backend Security Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://nippon-india-faq.vercel.app", "https://nipponindiaim.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["nippon-india-rag-api.onrender.com", "*.onrender.com"]
)
```

### **API Rate Limiting**
```python
# Rate Limiting Configuration
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

@app.post("/api/chat")
@limiter.limit("100/minute")
async def chat_endpoint(request: ChatRequest):
    # Chat endpoint logic
    pass
```

---

## 📈 Performance Optimization

### **Backend Performance**
```python
# Production Optimizations
import uvicorn
from concurrent.futures import ThreadPoolExecutor

# Production Server Configuration
if __name__ == "__main__":
    uvicorn.run(
        "src.api.multi_threaded_api_gateway:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        workers=int(os.getenv("MAX_WORKERS", 4)),
        limit_concurrency=100,
        timeout_keep_alive=30,
        access_log=True,
        log_level="info"
    )
```

### **Frontend Performance**
```javascript
// Next.js Production Optimizations
const nextConfig = {
  // Enable production optimizations
  swcMinify: true,
  reactStrictMode: true,
  
  // Optimize images
  images: {
    domains: ['mf.nipponindiaim.com'],
    formats: ['image/webp', 'image/avif'],
  },
  
  // Enable compression
  compress: true,
  
  // Optimize bundle
  webpack: (config) => {
    config.optimization.splitChunks = {
      chunks: 'all',
      cacheGroups: {
        vendor: {
          test: /[\\/]node_modules[\\/]/,
          name: 'vendors',
          chunks: 'all',
        },
      },
    };
    return config;
  },
};
```

---

## 🔄 Deployment Pipeline

### **Step-by-Step Deployment Process**

#### **1. Pre-Deployment Checks**
```bash
# Health checks and validation
python scripts/test_scheduler_simple.py
python scripts/test_api_health.py
npm run build
npm run test
```

#### **2. Automated Data Ingestion**
```bash
# GitHub Actions Scheduler (Daily at 2:00 AM IST)
- Scrape latest fund data
- Process and chunk documents
- Generate embeddings
- Update vector store
- Validate system health
- Upload logs as artifacts
```

#### **3. Backend Deployment**
```bash
# Render Deployment (On main branch push)
- Run health checks
- Deploy to production
- Update environment variables
- Restart services
- Verify deployment
```

#### **4. Frontend Deployment**
```bash
# Vercel Deployment (On main branch push)
- Build optimized production bundle
- Deploy to Vercel
- Update environment variables
- Verify frontend-backend connectivity
- Run smoke tests
```

#### **5. Post-Deployment Validation**
```bash
# End-to-end testing
curl -X GET https://nippon-india-rag-api.onrender.com/api/health
curl -X GET https://nippon-india-faq.vercel.app/api/health
python scripts/test_production_integration.py
```

---

## 📝 Deployment Checklist

### **Pre-Deployment Checklist**
- [ ] All tests passing locally
- [ ] Environment variables configured
- [ ] Security headers implemented
- [ ] Rate limiting configured
- [ ] Health endpoints working
- [ ] Log rotation setup
- [ ] Backup strategy defined
- [ ] Monitoring alerts configured

### **Post-Deployment Checklist**
- [ ] Backend health check passing
- [ ] Frontend health check passing
- [ ] API endpoints responding correctly
- [ ] Database connectivity verified
- [ ] Scheduler running successfully
- [ ] Logs being collected
- [ ] Performance metrics available
- [ ] Error rates within acceptable limits
- [ ] User functionality verified

---

## 🚨 Rollback Strategy

### **Immediate Rollback Triggers**
- Health check failures > 5 minutes
- Error rate > 10%
- Response time > 5 seconds
- Database connection failures
- Critical security alerts

### **Rollback Commands**
```bash
# Backend Rollback
curl -X POST \
  -H "Authorization: Bearer $RENDER_DEPLOY_HOOK" \
  -H "Content-Type: application/json" \
  -d '{"branch": "main", "rollback": true}' \
  https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys

# Frontend Rollback
vercel rollback --token $VERCEL_TOKEN --to previous
```

---

## 📞 Support & Monitoring

### **Alerting Configuration**
```yaml
# Monitoring Alerts (configured in respective platforms)
alerts:
  - name: "Backend Down"
    condition: "health_check_failure > 3"
    action: "trigger_rollback"
  
  - name: "High Error Rate"
    condition: "error_rate > 10%"
    action: "notify_team"
  
  - name: "Scheduler Failure"
    condition: "scheduler_job_failed"
    action: "retry_job"
```

### **Contact Information**
- **Development Team**: [Contact details]
- **Emergency Contacts**: [Emergency contacts]
- **Documentation**: https://github.com/[repo]/docs
- **Status Page**: https://status.nipponindiaim.com (optional)

---

## 📅 Deployment Timeline

### **Phase 1: Foundation (Week 1)**
- Set up GitHub repositories
- Configure Vercel project
- Set up Render service
- Implement health checks
- Create deployment scripts

### **Phase 2: Integration (Week 2)**
- Connect frontend to backend
- Implement error handling
- Add monitoring
- Test end-to-end functionality
- Security hardening

### **Phase 3: Production (Week 3)**
- Deploy to production
- Configure automated scheduling
- Set up monitoring alerts
- Performance optimization
- Documentation finalization

### **Phase 4: Maintenance (Ongoing)**
- Regular updates
- Security patches
- Performance monitoring
- Log analysis
- User feedback integration

---

## 🎯 Success Metrics

### **Key Performance Indicators (KPIs)**
- **Uptime**: > 99.9%
- **Response Time**: < 2 seconds
- **Error Rate**: < 1%
- **Scheduler Success**: > 95%
- **User Satisfaction**: > 4.5/5

### **Monitoring Dashboard**
- Real-time system health
- API performance metrics
- Data ingestion status
- User activity analytics
- Error tracking and alerting

---

*This deployment plan provides a comprehensive, production-ready strategy for the Nippon India Mutual Fund RAG System with automated scheduling, robust monitoring, and scalable infrastructure.*
