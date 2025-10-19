# BGX Navigation Championship Leaderboard

A modern, responsive web application built with FastHTML to display the BGX Navigation Championship 2025 results.

## Features

- 🏆 **Beautiful Leaderboard Interface** - Modern dark theme with gradient effects
- 📊 **Multiple Categories** - Support for 8 categories:
  - Expert
  - Profi
  - Standard
  - Standard Junior
  - Junior
  - Women
  - Seniors 40+
  - Seniors 50+
- 🎨 **Responsive Design** - Works perfectly on desktop, tablet, and mobile devices
- ⚡ **Fast & Lightweight** - Built with FastHTML for optimal performance
- 🎯 **Easy Navigation** - Quick category switching with intuitive tabs
- 📈 **Race-by-Race Breakdown** - View detailed scores for each race:
  - Alba Damascena
  - Buhovo
  - Gorna Malina
  - Kirkovo
  - Kyrnare
  - Six Days
  - Stara Zagora
- 🥇 **Visual Ranking** - Gold, silver, bronze badges for top 3 positions
- 📊 **Statistics Display** - Quick overview of total riders, races, and current category
- 🎪 **Score Highlighting** - Special styling for top scores and race results

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

### Option 1: Using the start script (recommended)
```bash
./start.sh
```

### Option 2: Manual start
```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python main.py
```

The application will be available at `http://localhost:5001`

## Usage

Once the server is running, you can:

1. **Browse Categories**: Click on any category tab (Expert, Profi, Standard, etc.) to view that category's leaderboard
2. **View Results**: See comprehensive race results including:
   - Final position with visual badges for top 3
   - Rider number and name
   - Total points accumulated
   - Number of races participated
   - Best position achieved
   - Individual race scores
3. **Mobile Access**: Open `http://localhost:5001` on any device on the same network
4. **Share Results**: The URL can be shared with query parameters, e.g., `http://localhost:5001/?category=profi`

### URL Parameters

- `category`: Specify which category to display (default: `expert`)
  - Valid values: `expert`, `profi`, `standard`, `standard_junior`, `junior`, `women`, `seniors_40`, `seniors_50`

Example URLs:
- `http://localhost:5001/` - Default (Expert category)
- `http://localhost:5001/?category=women` - Women's category
- `http://localhost:5001/?category=profi` - Profi category

## Data Source

The application reads data from the `bgx-result-2025-full` folder, which contains CSV files for each category:
- `expert.csv`
- `profi.csv`
- `standard.csv`
- `standard_junior.csv`
- `junior.csv`
- `women.csv`
- `seniors_40.csv`
- `seniors_50.csv`

## Technology Stack

- **FastHTML**: Modern Python web framework
- **Pandas**: Data processing and CSV reading
- **Bootstrap 5**: CSS framework for responsive design
- **Uvicorn**: ASGI server

## Customization

You can customize the appearance by modifying the CSS variables in the `Style` section of `main.py`:
- Colors
- Fonts
- Spacing
- Responsive breakpoints

### Color Variables

```css
--primary-color: #2563eb;
--secondary-color: #7c3aed;
--background: #0f172a;
--card-bg: #1e293b;
--text-primary: #f1f5f9;
--text-secondary: #94a3b8;
```

## Production Deployment

For production deployment, you can use the following options:

### Option 1: Using Uvicorn directly
```bash
uvicorn main:app --host 0.0.0.0 --port 5001 --workers 4
```

### Option 2: Behind a reverse proxy (Nginx)
```bash
uvicorn main:app --host 127.0.0.1 --port 5001 --workers 4
```

Then configure Nginx to proxy to port 5001.

### Option 3: Using Docker
Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## Troubleshooting

### Port Already in Use
If port 5001 is already in use, you can modify the port in `main.py`:
```python
if __name__ == "__main__":
    serve(port=8000)  # Change to desired port
```

### Data Not Loading
- Verify the CSV files exist in `../result-parsing/bgx-result-2025-full/`
- Check file permissions
- Ensure CSV files have the correct column structure

### Import Errors
Make sure the virtual environment is activated:
```bash
source venv/bin/activate  # On Unix/macOS
# or
venv\Scripts\activate  # On Windows
```

## Future Enhancements

Potential features for future versions:
- [ ] Export to PDF functionality
- [ ] Search/filter riders
- [ ] Historical data comparison
- [ ] Real-time updates during races
- [ ] Admin panel for data management
- [ ] Multi-language support

## 🚀 Hosting / Deployment

Want to make your dashboard accessible online or on your network?

### Quick Options:

**1. Railway (Easiest - Free):**
```bash
npm i -g @railway/cli
railway login
railway init && railway up
```

**2. Local Network:**
```bash
./deploy.sh  # Choose option 1
```

**3. Docker:**
```bash
docker-compose up -d
```

See `HOSTING-QUICKSTART.md` for quick setup or `DEPLOYMENT.md` for comprehensive guide.

## License

MIT License

