#!/bin/bash

# Backend Deployment Script for Render
# Usage: ./scripts/deploy_backend.sh

echo "🚀 Deploying Nippon India RAG API to Render..."

# Check if we're on main branch
if [[ "$GITHUB_REF" != "refs/heads/main" ]]; then
    echo "⚠️  Skipping deployment: Not on main branch"
    echo "Current branch: $GITHUB_REF"
    exit 0
fi

# Install dependencies
echo "📦 Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run health check
echo "🏥 Running health check..."
python -c "
import requests
import sys
import time

def wait_for_backend():
    for i in range(10):
        try:
            response = requests.get('http://localhost:8000/api/health', timeout=5)
            if response.status_code == 200:
                print('✅ Backend health check passed')
                return True
        except requests.exceptions.ConnectionError:
            print(f'⏳ Attempt {i+1}/10: Backend not ready yet...')
        except Exception as e:
            print(f'❌ Health check error: {e}')
        
        time.sleep(2)
    
    print('❌ Backend health check failed after 10 attempts')
    return False

if wait_for_backend():
    print('✅ Backend ready for deployment')
    sys.exit(0)
else:
    print('❌ Backend health check failed')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    echo "✅ Backend ready for deployment"
else
    echo "❌ Backend health check failed"
    exit 1
fi

echo "🎉 Backend deployment complete!"
