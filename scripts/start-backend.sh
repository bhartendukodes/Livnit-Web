#!/bin/bash

# Start the backend API server
# This script starts the FastAPI backend for development

set -e

echo "🚀 Starting Livinit Pipeline Backend..."

# Navigate to backend directory
cd "$(dirname "$0")/../livinit_pipeline-main"

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Start the API server
echo "🌐 Starting FastAPI server on http://localhost:8000"
echo "📖 API docs available at http://localhost:8000/docs"
echo "🔍 Health check at http://localhost:8000/health"
echo ""

python api.py