#!/bin/bash

# BGX Navigation Dashboard Startup Script

echo "🏆 Starting BGX Navigation Championship Dashboard..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt

# Start the server
echo "🚀 Starting server on http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python main.py

