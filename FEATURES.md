# BGX Navigation Dashboard - Feature Overview

## 🎯 Core Features

### 1. Multi-Category Support
The dashboard displays results for 8 different championship categories:
- **Expert**: Professional cross-country riders (61 participants)
- **Profi**: Advanced competitive riders (17 participants)
- **Standard**: Regular competitive category (118 participants)
- **Standard Junior**: Junior standard category
- **Junior**: Youth riders
- **Women**: Women's category
- **Seniors 40+**: Masters 40 and over
- **Seniors 50+**: Masters 50 and over

### 2. Comprehensive Race Data
Each category shows results from 7 major races:
- **Alba Damascena** - Spring race
- **Buhovo** - Technical course
- **Gorna Malina** - Mountain terrain (2 events)
- **Kirkovo** - Southern race
- **Kyrnare** - Central race
- **Six Days** - Endurance event
- **Stara Zagora** - Classic race

### 3. Detailed Leaderboard Information
For each rider, the system displays:
- **Final Position**: Overall championship standing
- **Race Number**: Unique rider identifier
- **Name**: First and last name
- **Total Points**: Accumulated championship points
- **Races Participated**: Number of races completed
- **Best Position**: Highest finish achieved
- **Individual Race Scores**: Points earned in each race

### 4. Visual Design Elements

#### Position Badges
- 🥇 **1st Place**: Gold gradient badge
- 🥈 **2nd Place**: Silver gradient badge
- 🥉 **3rd Place**: Bronze gradient badge
- 🔢 **Other**: Gray badge with position number

#### Score Highlighting
- **Top Scores** (25 points): Green highlight - indicates race win
- **Regular Scores**: Blue-tinted background
- **No Participation** (0 or empty): Em dash (—)

#### Color Scheme
- **Primary**: Blue (#2563eb)
- **Secondary**: Purple (#7c3aed)
- **Background**: Dark navy (#0f172a)
- **Cards**: Slate gray (#1e293b)
- **Text**: Light gray (#f1f5f9)

### 5. Statistics Dashboard
Quick overview bar showing:
- **Total Riders**: Count of participants in current category
- **Total Races**: Number of races in the championship
- **Current Category**: Active category being viewed

### 6. User Experience Features

#### Navigation
- **Category Tabs**: One-click switching between categories
- **Active State**: Currently selected category is highlighted
- **Hover Effects**: Visual feedback on interactive elements

#### Responsive Design
- **Desktop**: Full table view with all columns
- **Tablet**: Optimized layout with scrolling
- **Mobile**: Stacked layout with horizontal scroll for race columns

#### Performance
- **Fast Loading**: Instant category switching
- **Efficient Data**: CSV files loaded on-demand
- **Smooth Animations**: CSS transitions for professional feel

### 7. URL Parameter Support
Direct access to specific categories via URL:
```
http://localhost:5001/?category=expert
http://localhost:5001/?category=women
http://localhost:5001/?category=profi
```

## 🔧 Technical Features

### Backend
- **FastHTML Framework**: Modern Python web framework
- **Pandas Data Processing**: Efficient CSV handling
- **Dynamic Routing**: Category-based view switching
- **Path Resolution**: Automatic data file location

### Frontend
- **Bootstrap 5**: Responsive grid system
- **Custom CSS**: Tailored styling with CSS variables
- **Modern HTML5**: Semantic markup
- **Mobile-First**: Responsive from the ground up

### Data Processing
- **CSV Parsing**: Automatic column detection
- **Race Column Extraction**: Dynamic race identification
- **Score Formatting**: Intelligent display of points
- **Missing Data Handling**: Graceful handling of empty scores

## 📈 Supported Data Format

The system expects CSV files with the following structure:
```csv
FinalPosition,RaceNumber,FirstName,LastName,TotalPoints,RacesParticipated,BestPosition,WorstResultDropped,WorstRace,Race_alba_damascena,Race_buhovo,Race_gorna_malina,Race_kirkovo,Race_kyrnare,Race_six_days,Race_stara_zagora
1,255,Димитър,ТИНЧЕВ,147.0,6,1,,,25.0,25.0,25.0,0,25.0,25.0,22.0
```

### Required Columns
- `FinalPosition`: Overall ranking
- `RaceNumber`: Rider identification
- `FirstName`: Rider's first name
- `LastName`: Rider's surname
- `TotalPoints`: Championship points total
- `RacesParticipated`: Number of races completed
- `BestPosition`: Best finish in any race

### Dynamic Race Columns
Any column starting with `Race_` is automatically detected and displayed:
- Supports any number of races
- Race names are formatted for display (e.g., `Race_alba_damascena` → "Alba Damascena")

## 🎨 Customization Options

### Easy Changes
1. **Colors**: Modify CSS variables in `main.py`
2. **Port**: Change port number in the serve() call
3. **Categories**: Add/remove from the CATEGORIES dictionary
4. **Race Names**: Automatic from CSV column names

### Advanced Customization
1. **Styling**: Full CSS control in the Style section
2. **Layout**: Modify HTML structure in render functions
3. **Data Source**: Change RESULTS_PATH to load from different location
4. **Additional Stats**: Extend the statistics calculation

## 🚀 Performance Metrics

- **Page Load**: < 100ms (local)
- **Category Switch**: Instant (client-side navigation)
- **Data Processing**: On-demand CSV parsing
- **Memory Usage**: Minimal (single category loaded at a time)

## 🔒 Security Considerations

Current implementation is designed for local/internal use:
- No authentication (suitable for trusted networks)
- Read-only data access
- No user input processing
- Static data from CSV files

For public deployment, consider adding:
- User authentication
- HTTPS support
- Rate limiting
- Input validation

## 🎯 Use Cases

Perfect for:
- ✅ Championship organizers tracking standings
- ✅ Race coordinators viewing results
- ✅ Riders checking their positions
- ✅ Spectators following the championship
- ✅ Media accessing official results
- ✅ Historical data preservation

## 📊 Data Insights

The dashboard reveals:
- Championship leaders across categories
- Consistency of riders (races participated)
- Peak performance (best position achieved)
- Point distribution across races
- Competitive depth in each category

Enjoy exploring the BGX Navigation Championship 2025 results! 🏆

