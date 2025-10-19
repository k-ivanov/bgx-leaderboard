# 🚀 Quick Hosting Guide

## Fastest Way to Host Online (5 minutes)

### Railway (Recommended - Free Tier)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Deploy (from bgx-navigation-dashboard directory)
cd bgx-navigation-dashboard
railway init
railway up

# 4. Get your public URL
railway open
```

**That's it!** Your dashboard is now live with a public URL! 🎉

---

## Other Quick Options

### Local Network (Free - No Cloud)

```bash
cd bgx-navigation-dashboard
./deploy.sh
# Choose option 1
```

Access from any device on your network at: `http://YOUR_IP:5001`

---

### Docker (For VPS/Server)

```bash
cd bgx-navigation-dashboard
docker-compose up -d
```

Access at: `http://localhost:5001` or `http://YOUR_SERVER_IP:5001`

---

## Comparison Table

| Method | Cost | Setup Time | Public URL | Best For |
|--------|------|------------|------------|----------|
| **Railway** | Free tier | 2 min | ✅ Yes | Quick online hosting |
| **Render** | Free tier | 3 min | ✅ Yes | GitHub integration |
| **Fly.io** | Free tier | 5 min | ✅ Yes | Edge hosting |
| **Docker** | VPS cost | 2 min | ❌ Need domain | Full control |
| **Local Network** | Free | 1 min | ❌ Local only | Internal use |

---

## Step-by-Step: Railway Deployment

### Prerequisites
- Node.js installed (for Railway CLI)
- Git repository (optional but recommended)

### Steps

**1. Install Railway CLI:**
```bash
npm i -g @railway/cli
```

**2. Login to Railway:**
```bash
railway login
```
This opens a browser for authentication.

**3. Navigate to your project:**
```bash
cd bgx-navigation-dashboard
```

**4. Initialize Railway project:**
```bash
railway init
```
Choose "Create new project" and give it a name like "bgx-navigation"

**5. Deploy:**
```bash
railway up
```
Wait for the build and deployment to complete.

**6. Generate public URL:**
```bash
railway domain
```

**7. Open your dashboard:**
```bash
railway open
```

### Environment Variables (Optional)

Set custom port or host:
```bash
railway variables set PORT=8080
railway variables set HOST=0.0.0.0
```

---

## Troubleshooting

### "Command not found: railway"
```bash
# Install Node.js first, then:
npm i -g @railway/cli
```

### "Permission denied"
```bash
# On macOS/Linux, use:
sudo npm i -g @railway/cli
```

### "Port already in use"
```bash
# Change port in railway variables:
railway variables set PORT=8080
```

### Data not loading
```bash
# Ensure data path is correct in main.py
# Check that CSV files are included in deployment
```

---

## Need More Details?

- See `DEPLOYMENT.md` for comprehensive deployment guide
- See `README.md` for application documentation
- See `QUICKSTART.md` for local development

---

## Support

Having issues? Common solutions:

1. **Check logs:** `railway logs` or `docker-compose logs`
2. **Verify data path:** Ensure CSV files are accessible
3. **Check port:** Default is 5001, may need to change
4. **Restart:** `railway restart` or `docker-compose restart`

---

**🎯 Recommendation:** Start with Railway for easiest setup and free hosting!

