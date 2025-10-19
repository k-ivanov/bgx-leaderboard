#!/bin/bash

# BGX Navigation Dashboard - Quick Deploy Script

echo "🚀 BGX Navigation Dashboard - Deployment Script"
echo "================================================"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Menu
echo "Select deployment method:"
echo ""
echo "1) Local Network (accessible on your network)"
echo "2) Docker (containerized deployment)"
echo "3) Railway (cloud hosting - easiest)"
echo "4) Show deployment info"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "🌐 Starting local network server..."
        echo ""
        
        # Get local IP
        if [[ "$OSTYPE" == "darwin"* ]]; then
            LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
        else
            LOCAL_IP=$(hostname -I | awk '{print $1}')
        fi
        
        echo "Your local IP: $LOCAL_IP"
        echo ""
        echo "Server will be accessible at:"
        echo "  - Local: http://localhost:5001"
        echo "  - Network: http://$LOCAL_IP:5001"
        echo ""
        echo "Press Ctrl+C to stop the server"
        echo ""
        
        # Start server
        source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
        pip install -q -r requirements.txt
        HOST=0.0.0.0 PORT=5001 python main.py
        ;;
        
    2)
        echo ""
        echo "🐳 Docker Deployment"
        echo ""
        
        if ! command_exists docker; then
            echo "❌ Docker is not installed. Please install Docker first:"
            echo "   https://docs.docker.com/get-docker/"
            exit 1
        fi
        
        echo "Building and starting Docker container..."
        docker-compose up --build -d
        
        echo ""
        echo "✅ Dashboard is running!"
        echo ""
        echo "Access at: http://localhost:5001"
        echo ""
        echo "Useful commands:"
        echo "  - View logs: docker-compose logs -f"
        echo "  - Stop: docker-compose down"
        echo "  - Restart: docker-compose restart"
        ;;
        
    3)
        echo ""
        echo "☁️  Railway Cloud Deployment"
        echo ""
        
        if ! command_exists railway; then
            echo "Installing Railway CLI..."
            npm i -g @railway/cli
        fi
        
        echo ""
        echo "Logging into Railway..."
        railway login
        
        echo ""
        echo "Initializing and deploying..."
        railway init
        railway up
        
        echo ""
        echo "✅ Deployed to Railway!"
        echo ""
        echo "Opening dashboard..."
        railway open
        ;;
        
    4)
        echo ""
        echo "📖 Deployment Information"
        echo ""
        echo "Available deployment options:"
        echo ""
        echo "1. Local Network:"
        echo "   - Run: ./deploy.sh (choose option 1)"
        echo "   - Access from any device on your network"
        echo "   - Free, no external dependencies"
        echo ""
        echo "2. Docker:"
        echo "   - Run: docker-compose up -d"
        echo "   - Portable, isolated environment"
        echo "   - Easy to deploy on any VPS"
        echo ""
        echo "3. Railway (Recommended for cloud):"
        echo "   - Run: railway login && railway init && railway up"
        echo "   - Free tier available"
        echo "   - Automatic SSL and deployments"
        echo ""
        echo "4. Other options:"
        echo "   - Render.com - Free tier available"
        echo "   - Fly.io - Fast edge hosting"
        echo "   - PythonAnywhere - Python-focused hosting"
        echo ""
        echo "See DEPLOYMENT.md for detailed instructions!"
        ;;
        
    *)
        echo "Invalid choice. Please run the script again."
        exit 1
        ;;
esac

