# BGX Navigation Dashboard - Quick Start Guide

## 🚀 Get Started in 30 Seconds

```bash
cd bgx-navigation-dashboard
./start.sh
```

Then open your browser to: **http://localhost:5001**

## 📊 What You'll See

### Main Features:
- **Category Tabs**: Switch between Expert, Profi, Standard, Junior, Women, and Seniors categories
- **Statistics Bar**: View total riders, races, and current category at a glance
- **Leaderboard Table**: 
  - Position (with gold/silver/bronze badges for top 3)
  - Rider number and name
  - Total points
  - Races participated
  - Best position achieved
  - Individual race scores

### Categories Available:
1. **Expert** - 61 riders
2. **Profi** - 17 riders  
3. **Standard** - 118 riders
4. **Standard Junior** - Various riders
5. **Junior** - Various riders
6. **Women** - Various riders
7. **Seniors 40+** - Various riders
8. **Seniors 50+** - Various riders

### Race Results Displayed:
- Alba Damascena
- Buhovo
- Gorna Malina
- Kirkovo
- Kyrnare
- Six Days
- Stara Zagora

## 🎨 Design Highlights

- **Modern Dark Theme**: Sleek gradient backgrounds with blue and purple accents
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Visual Hierarchy**: Clear gold/silver/bronze medals for top positions
- **Score Highlighting**: Top scores (25 points) highlighted in green
- **Smooth Interactions**: Hover effects and transitions throughout

## 📱 Accessing from Other Devices

Find your computer's IP address and access from any device on the same network:
```
http://YOUR_IP:5001
```

## ⚡ Quick Tips

- Click any category tab to instantly switch views
- Scroll horizontally on mobile to see all race columns
- The leaderboard updates automatically when you refresh
- Bookmark specific categories: `http://localhost:5001/?category=women`

## 🛠️ Common Commands

```bash
# Start the server
./start.sh

# Or manually:
source venv/bin/activate
python main.py

# Install/update dependencies
pip install -r requirements.txt

# Stop the server
Press Ctrl+C
```

## 📝 File Structure

```
bgx-navigation-dashboard/
├── main.py              # Main application code
├── requirements.txt     # Python dependencies
├── start.sh            # Quick start script
├── README.md           # Full documentation
├── QUICKSTART.md       # This file
└── venv/               # Virtual environment (auto-created)
```

## 🎯 Next Steps

1. **Customize Colors**: Edit CSS variables in `main.py`
2. **Add Features**: Extend functionality as needed
3. **Deploy**: See README.md for production deployment options
4. **Share**: Send the URL to others on your network

Enjoy your BGX Navigation Championship Dashboard! 🏆

