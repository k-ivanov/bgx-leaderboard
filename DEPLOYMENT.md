# BGX Navigation Dashboard - Deployment Guide

This guide covers multiple options for hosting your BGX Navigation Dashboard online.

## 🚀 Quick Deployment Options

### Option 1: Railway (Easiest - Free Tier Available)

**Railway** offers free hosting for Python apps with automatic deployments.

1. **Prepare your app:**
```bash
# No changes needed - already configured!
```

2. **Deploy:**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize and deploy
railway init
railway up
```

3. **Access your app:**
   - Railway will provide a public URL automatically
   - Example: `https://your-app.railway.app`

**Pros:** Free tier, automatic SSL, easy setup
**Cons:** Limited free hours per month

---

### Option 2: Render (Free Tier Available)

**Render** provides free static and web service hosting.

1. **Create `render.yaml`** in your project:
```yaml
services:
  - type: web
    name: bgx-navigation-dashboard
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PORT
        value: 5001
```

2. **Deploy:**
   - Go to [render.com](https://render.com)
   - Connect your GitHub repository
   - Select the `bgx-navigation-dashboard` directory
   - Deploy!

**Pros:** Free tier, automatic SSL, GitHub integration
**Cons:** Free tier may sleep after inactivity

---

### Option 3: Fly.io (Free Tier Available)

**Fly.io** is excellent for Python applications.

1. **Install Fly CLI:**
```bash
curl -L https://fly.io/install.sh | sh
```

2. **Create `fly.toml`:**
```toml
app = "bgx-navigation"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "5001"

[[services]]
  internal_port = 5001
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

3. **Deploy:**
```bash
cd bgx-navigation-dashboard
fly launch
fly deploy
```

**Pros:** Free tier, fast edge network, automatic SSL
**Cons:** Requires credit card for verification

---

### Option 4: PythonAnywhere (Python-Focused Hosting)

**PythonAnywhere** specializes in Python hosting.

1. **Sign up:** [pythonanywhere.com](https://www.pythonanywhere.com)

2. **Upload your code:**
   - Use Git or upload files directly
   - Set up virtual environment
   - Install dependencies

3. **Configure WSGI:**
```python
# WSGI configuration
import sys
path = '/home/yourusername/bgx-navigation-dashboard'
if path not in sys.path:
    sys.path.append(path)

from main import app as application
```

**Pros:** Python-focused, free tier available
**Cons:** Limited resources on free tier

---

### Option 5: Docker + Any VPS (DigitalOcean, AWS, etc.)

For more control, use Docker on any VPS.

1. **Create `Dockerfile`:**
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY ../result-parsing/bgx-result-2025-full ./data/

# Expose port
EXPOSE 5001

# Run the application
CMD ["python", "main.py"]
```

2. **Create `docker-compose.yml`:**
```yaml
version: '3.8'

services:
  dashboard:
    build: .
    ports:
      - "5001:5001"
    volumes:
      - ../result-parsing/bgx-result-2025-full:/app/data:ro
    restart: unless-stopped
```

3. **Deploy:**
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f
```

**Pros:** Full control, portable, scalable
**Cons:** Requires server management

---

### Option 6: Local Network Access

Make it accessible on your local network without cloud hosting.

1. **Find your local IP:**
```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Windows
ipconfig
```

2. **Update `main.py` for network access:**
```python
if __name__ == "__main__":
    serve(host="0.0.0.0", port=5001)
```

3. **Access from other devices:**
   - Use: `http://YOUR_LOCAL_IP:5001`
   - Example: `http://192.168.1.100:5001`

**Pros:** Free, fast, no external dependencies
**Cons:** Only accessible on same network

---

## 🔒 Production Best Practices

### 1. Environment Variables

Update `main.py` to use environment variables:

```python
import os
from pathlib import Path

PORT = int(os.getenv("PORT", 5001))
HOST = os.getenv("HOST", "0.0.0.0")
DATA_PATH = Path(os.getenv("DATA_PATH", "../result-parsing/bgx-result-2025-full"))

if __name__ == "__main__":
    serve(host=HOST, port=PORT)
```

### 2. Add Health Check Endpoint

```python
@rt("/health")
def health():
    return {"status": "healthy", "service": "bgx-navigation-dashboard"}
```

### 3. Use Production Server

Update `requirements.txt`:
```txt
python-fasthtml>=0.4.0
pandas>=2.0.0
uvicorn[standard]>=0.24.0
gunicorn>=21.0.0
```

Run with Gunicorn:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:5001
```

### 4. Add Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### 5. Set Up Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6. Enable SSL with Let's Encrypt

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

---

## 📊 Cost Comparison

| Platform | Free Tier | Paid Plans | Best For |
|----------|-----------|------------|----------|
| **Railway** | 500 hrs/month | $5/month | Quick deploys |
| **Render** | 750 hrs/month | $7/month | Simple apps |
| **Fly.io** | 3 VMs free | $1.94/month | Edge hosting |
| **PythonAnywhere** | Limited | $5/month | Python apps |
| **DigitalOcean** | - | $4/month | Full control |
| **AWS Lightsail** | - | $3.50/month | AWS ecosystem |

---

## 🎯 Recommended Setup

### For Personal/Testing:
**Railway or Render** - Easiest setup with free tier

### For Production:
**Fly.io + PostgreSQL** - Fast, scalable, global edge network

### For Full Control:
**Docker on DigitalOcean** - Complete control over infrastructure

---

## 🔧 Quick Start: Railway Deployment

The absolute easiest way to get started:

1. **Install Railway:**
```bash
npm i -g @railway/cli
railway login
```

2. **Deploy:**
```bash
cd bgx-navigation-dashboard
railway init
railway up
```

3. **Get URL:**
```bash
railway open
```

That's it! Your dashboard is now live! 🎉

---

## 📱 Custom Domain Setup

After deploying to any platform:

1. **Get your deployment URL** from the platform
2. **Add CNAME record** in your domain DNS:
   - Type: `CNAME`
   - Name: `dashboard` (or `@` for root)
   - Value: Your platform's URL

3. **Configure SSL** (usually automatic on modern platforms)

Example: `dashboard.your-domain.com` → Your BGX Dashboard

---

## 🐛 Troubleshooting

### Port Issues
```python
# Use environment variable
PORT = int(os.getenv("PORT", 5001))
serve(port=PORT)
```

### Data Path Issues
```python
# Use absolute paths
DATA_PATH = Path(__file__).parent / "data"
```

### Memory Issues
- Reduce pandas chunk size
- Use data caching
- Optimize CSV reading

---

## 📚 Additional Resources

- [FastHTML Deployment Docs](https://fastht.ml/)
- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)
- [Fly.io Docs](https://fly.io/docs/)

---

Need help? Open an issue or contact support! 🚀

