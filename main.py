from fasthtml.common import *
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from fastlite import Database

# Initialize the FastHTML app with Tailwind CSS
app, rt = fast_app(
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
        Script("""
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            primary: '#2563eb',
                            secondary: '#7c3aed',
                        }
                    }
                }
            }
        """),
        Style("""
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
            
            * {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }
            
            body {
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            }
            
            .gradient-text {
                background: linear-gradient(135deg, #2563eb, #7c3aed);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            
            .gradient-bg {
                background: linear-gradient(135deg, #2563eb, #7c3aed);
            }
            
            .position-badge-1 {
                background: linear-gradient(135deg, #fbbf24, #f59e0b);
            }
            
            .position-badge-2 {
                background: linear-gradient(135deg, #e2e8f0, #94a3b8);
            }
            
            .position-badge-3 {
                background: linear-gradient(135deg, #f97316, #ea580c);
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            .animate-fade-in {
                animation: fadeIn 0.5s ease-out;
            }
        """)
    )
)

# Path to the results folder
RESULTS_PATH = Path(__file__).parent / "data" / "bgx-result-2025-full"

# Initialize database for visit tracking
DB_PATH = Path(__file__).parent / "data" / "visits.db"
db = Database(DB_PATH)

# Define visits dataclass for the table
from dataclasses import dataclass

@dataclass
class Visit:
    id: int = None
    timestamp: str = None
    page: str = None
    category: str = None
    device_type: str = None

# Create visits table if it doesn't exist
visits_table = db.create(Visit, pk="id", if_not_exists=True)

# Migrate existing table to add device_type column if it doesn't exist
# First check if the table exists (fastlite creates table name from class name)
table_exists = db.conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='visit'"
).fetchone()

if table_exists:
    # Check if device_type column exists
    columns = [row[1] for row in db.conn.execute("PRAGMA table_info(visit)")]
    if 'device_type' not in columns:
        print("Adding device_type column to visit table...")
        db.conn.execute("ALTER TABLE visit ADD COLUMN device_type TEXT DEFAULT 'unknown'")

def detect_device_type(user_agent: str) -> str:
    """Detect if the request is from mobile or desktop based on User-Agent"""
    if not user_agent:
        return "unknown"
    
    user_agent_lower = user_agent.lower()
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    
    for indicator in mobile_indicators:
        if indicator in user_agent_lower:
            return "mobile"
    
    return "desktop"

def track_visit(page: str, category: str = "", user_agent: str = ""):
    """Track a page visit with device type"""
    device_type = detect_device_type(user_agent)
    visits_table.insert(
        timestamp=datetime.now().isoformat(),
        page=page,
        category=category,
        device_type=device_type
    )

# Define categories with display names
CATEGORIES = {
    "profi": "Pro",
    "expert": "Expert",
    "standard": "Standard",
    "standard_junior": "Standard Junior",
    "junior": "Junior",
    "women": "Women",
    "seniors_40": "Senior 40+",
    "seniors_50": "Senior 50+"
}

def load_category_data(category):
    """Load CSV data for a specific category"""
    csv_path = RESULTS_PATH / f"{category}.csv"
    if not csv_path.exists():
        return None
    
    df = pd.read_csv(csv_path)
    return df

def get_race_columns(df):
    """Extract race column names from the dataframe and sort them by race order"""
    # Define the desired race order
    race_order = [
        'Race_kyrnare',
        'Race_stara_zagora',
        'Race_buhovo',
        'Race_gorna_malina',
        'Race_alba_damascena',
        'Race_six_days',
        'Race_kirkovo'
    ]
    
    # Get all race columns from the dataframe
    race_cols = [col for col in df.columns if col.startswith('Race_')]
    
    # Sort by the defined order, put any unexpected columns at the end
    def sort_key(col):
        if col in race_order:
            return race_order.index(col)
        return len(race_order)  # Put unknown races at the end
    
    race_cols.sort(key=sort_key)
    return race_cols

def format_race_name(race_col):
    """Format race column name for display"""
    name = race_col.replace('Race_', '').replace('_', ' ')
    return name.title()

def create_position_badge(position):
    """Create a position badge with appropriate styling using Tailwind"""
    if position == 1:
        badge_class = "position-badge-1 text-amber-900"
    elif position == 2:
        badge_class = "position-badge-2 text-slate-800"
    elif position == 3:
        badge_class = "position-badge-3 text-white"
    else:
        badge_class = "bg-slate-700 text-slate-400"
    
    return Span(
        str(position), 
        cls=f"inline-flex items-center justify-center w-10 h-10 rounded-full font-bold text-base {badge_class}"
    )

def create_leaderboard_table(df, category):
    """Create the leaderboard table with Tailwind styling"""
    if df is None or df.empty:
        return Div(
            P("No data available for this category.", cls="text-center text-slate-400 p-8"),
            cls="bg-slate-800 rounded-xl shadow-2xl border border-slate-700"
        )
    
    race_cols = get_race_columns(df)
    
    # Table headers with Tailwind styling
    headers = [
        Th("Position", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Number", cls="px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Rider", cls="px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Total Points", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Races", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Best Pos", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Worst Dropped", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
        Th("Worst Race", cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
    ]
    
    # Add race columns
    for race_col in race_cols:
        headers.append(Th(format_race_name(race_col), cls="text-center px-3 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"))
    
    # Table rows with Tailwind styling
    rows = []
    for _, row in df.iterrows():
        # Handle worst result dropped
        worst_dropped = row.get('WorstResultDropped', '')
        if pd.isna(worst_dropped) or worst_dropped == '':
            worst_dropped_display = "—"
            worst_dropped_class = "text-slate-500"
        else:
            worst_dropped_display = f"{float(worst_dropped):.0f}"
            worst_dropped_class = "text-red-400"
        
        # Handle worst race
        worst_race = row.get('WorstRace', '')
        if pd.isna(worst_race) or worst_race == '':
            worst_race_display = "—"
            worst_race_class = "text-slate-500"
        else:
            worst_race_display = str(worst_race).replace('_', ' ').title()
            worst_race_class = "text-red-400 text-xs"
        
        cells = [
            Td(create_position_badge(int(row['FinalPosition'])), cls="text-center px-3 py-4"),
            Td(Strong(str(int(row['RaceNumber']))), cls="px-3 py-4 font-bold text-slate-200"),
            Td(f"{row['FirstName']} {row['LastName']}", cls="px-3 py-4 text-slate-200 min-w-[150px]"),
            Td(
                Span(
                    f"{row['TotalPoints']:.0f}", 
                    cls="px-3 py-1 gradient-bg rounded-full font-bold text-sm text-white"
                ), 
                cls="text-center px-3 py-4"
            ),
            Td(str(int(row['RacesParticipated'])), cls="text-center px-3 py-4 text-slate-300"),
            Td(str(int(row['BestPosition'])), cls="text-center px-3 py-4 text-slate-300"),
            Td(worst_dropped_display, cls=f"text-center px-3 py-4 {worst_dropped_class} font-semibold"),
            Td(worst_race_display, cls=f"text-center px-3 py-4 {worst_race_class}"),
        ]
        
        # Add race scores with Tailwind styling
        for race_col in race_cols:
            score = row[race_col]
            if pd.isna(score) or score == 0:
                cells.append(Td("—", cls="text-center px-3 py-4 text-slate-500"))
            else:
                # Check if this is the best score (25 points typically means 1st place)
                if score >= 25:
                    score_badge = Span(
                        f"{score:.0f}", 
                        cls="px-2 py-1 bg-green-500/10 text-green-400 rounded font-semibold text-sm"
                    )
                else:
                    score_badge = Span(
                        f"{score:.0f}", 
                        cls="px-2 py-1 bg-blue-500/10 text-blue-400 rounded text-sm"
                    )
                cells.append(Td(score_badge, cls="text-center px-3 py-4"))
        
        rows.append(Tr(*cells, cls="border-b border-slate-700/50 hover:bg-blue-500/5 transition-colors duration-200"))
    
    return Div(
        Div(
            H2(
                f"{CATEGORIES[category]} Leaderboard",
                cls="text-2xl font-bold text-slate-100"
            ),
            cls="px-6 py-5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-b border-slate-700"
        ),
        Div(
            Table(
                Thead(Tr(*headers), cls="bg-blue-500/5 sticky top-0 z-10"),
                Tbody(*rows),
                cls="w-full border-collapse"
            ),
            cls="w-full overflow-x-auto"
        ),
        cls="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 overflow-hidden animate-fade-in"
    )

@rt("/health")
def health():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "bgx-navigation-dashboard",
        "version": "1.0.0"
    }

@rt("/stats")
def stats(request):
    """Statistics page showing visit analytics"""
    # Track this visit
    user_agent = request.headers.get('user-agent', '')
    track_visit("stats", "", user_agent)
    
    # Get all visits
    all_visits = list(visits_table())
    total_visits = len(all_visits)
    
    # Count visits by page
    home_visits = sum(1 for v in all_visits if v.page == 'home')
    stats_visits = sum(1 for v in all_visits if v.page == 'stats')
    
    # Count visits by device type
    mobile_visits = sum(1 for v in all_visits if getattr(v, 'device_type', 'unknown') == 'mobile')
    desktop_visits = sum(1 for v in all_visits if getattr(v, 'device_type', 'unknown') == 'desktop')
    unknown_visits = sum(1 for v in all_visits if getattr(v, 'device_type', 'unknown') == 'unknown')
    
    # Count visits by category
    category_counts = {}
    for v in all_visits:
        if v.page == 'home' and v.category:
            category_counts[v.category] = category_counts.get(v.category, 0) + 1
    
    # Get recent visits (last 20)
    recent_visits = sorted(all_visits, key=lambda x: x.timestamp, reverse=True)[:20]
    
    # Create category stats rows
    category_rows = []
    for cat_key in sorted(category_counts.keys(), key=lambda k: category_counts[k], reverse=True):
        count = category_counts[cat_key]
        percentage = (count / home_visits * 100) if home_visits > 0 else 0
        category_rows.append(
            Tr(
                Td(CATEGORIES.get(cat_key, cat_key), cls="px-4 py-3 text-slate-200"),
                Td(str(count), cls="px-4 py-3 text-center text-slate-200 font-bold"),
                Td(
                    Div(
                        Div(cls=f"h-2 gradient-bg rounded-full", style=f"width: {percentage}%"),
                        cls="w-full bg-slate-700 rounded-full h-2"
                    ),
                    cls="px-4 py-3"
                ),
                Td(f"{percentage:.1f}%", cls="px-4 py-3 text-center text-slate-300"),
                cls="border-b border-slate-700/50"
            )
        )
    
    # Create recent visits rows
    recent_rows = []
    for visit in recent_visits:
        try:
            dt = datetime.fromisoformat(visit.timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = visit.timestamp
        
        page_display = "🏠 Home" if visit.page == 'home' else "📊 Stats"
        category_display = CATEGORIES.get(visit.category, visit.category) if visit.category else "—"
        
        # Get device type with fallback for old records
        device_type = getattr(visit, 'device_type', 'unknown')
        if device_type == 'mobile':
            device_display = "📱 Mobile"
            device_class = "text-blue-400"
        elif device_type == 'desktop':
            device_display = "💻 Desktop"
            device_class = "text-green-400"
        else:
            device_display = "❓ Unknown"
            device_class = "text-slate-500"
        
        recent_rows.append(
            Tr(
                Td(time_str, cls="px-4 py-3 text-slate-300 text-sm font-mono"),
                Td(page_display, cls="px-4 py-3 text-slate-200"),
                Td(category_display, cls="px-4 py-3 text-slate-300"),
                Td(device_display, cls=f"px-4 py-3 {device_class}"),
                cls="border-b border-slate-700/50"
            )
        )
    
    return Html(
        Head(
            Title("Visit Statistics - BGX Navigation Championship"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                tailwind.config = {
                    theme: {
                        extend: {
                            colors: {
                                primary: '#2563eb',
                                secondary: '#7c3aed',
                            }
                        }
                    }
                }
            """),
            Style("""
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
                
                * {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                }
                
                body {
                    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                }
                
                .gradient-text {
                    background: linear-gradient(135deg, #2563eb, #7c3aed);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                
                .gradient-bg {
                    background: linear-gradient(135deg, #2563eb, #7c3aed);
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .animate-fade-in {
                    animation: fadeIn 0.5s ease-out;
                }
            """)
        ),
        Body(
            # Header Section
            Div(
                H1(
                    "📊 Visit Statistics",
                    cls="text-4xl md:text-5xl font-black gradient-text mb-3"
                ),
                P(
                    "Real-time analytics for BGX Navigation Championship Dashboard",
                    cls="text-slate-400 text-lg md:text-xl"
                ),
                Div(
                    A(
                        "← Back to Championship",
                        href="/",
                        cls="inline-block mt-4 px-6 py-2 gradient-bg text-white rounded-lg font-semibold hover:scale-105 transition-all duration-200"
                    ),
                    cls="mt-6"
                ),
                cls="text-center py-12 px-4"
            ),
            
            # Stats Cards
            Div(
                Div(
                    Div(
                        Div(
                            Span("📈", cls="text-4xl mb-3"),
                            Div(str(total_visits), cls="text-4xl font-bold text-slate-100"),
                            Div("Total Visits", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                            cls="text-center"
                        ),
                        cls="bg-slate-800 rounded-xl p-8 border border-slate-700 shadow-lg"
                    ),
                    Div(
                        Div(
                            Span("🏠", cls="text-4xl mb-3"),
                            Div(str(home_visits), cls="text-4xl font-bold text-slate-100"),
                            Div("Home Page Visits", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                            cls="text-center"
                        ),
                        cls="bg-slate-800 rounded-xl p-8 border border-slate-700 shadow-lg"
                    ),
                    Div(
                        Div(
                            Span("📊", cls="text-4xl mb-3"),
                            Div(str(stats_visits), cls="text-4xl font-bold text-slate-100"),
                            Div("Stats Page Visits", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                            cls="text-center"
                        ),
                        cls="bg-slate-800 rounded-xl p-8 border border-slate-700 shadow-lg"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-3 gap-6"
                ),
                cls="max-w-7xl mx-auto px-4 pb-8"
            ),
            
            # Device Statistics
            Div(
                Div(
                    H2("Device Breakdown", cls="text-2xl font-bold text-slate-100 mb-6"),
                    Div(
                        Div(
                            Div(
                                Span("💻", cls="text-3xl mb-3"),
                                Div(str(desktop_visits), cls="text-3xl font-bold text-slate-100"),
                                Div("Desktop", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                                Div(
                                    f"{(desktop_visits/total_visits*100 if total_visits > 0 else 0):.1f}%",
                                    cls="text-xs text-slate-500 mt-1"
                                ),
                                cls="text-center"
                            ),
                            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
                        ),
                        Div(
                            Div(
                                Span("📱", cls="text-3xl mb-3"),
                                Div(str(mobile_visits), cls="text-3xl font-bold text-slate-100"),
                                Div("Mobile", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                                Div(
                                    f"{(mobile_visits/total_visits*100 if total_visits > 0 else 0):.1f}%",
                                    cls="text-xs text-slate-500 mt-1"
                                ),
                                cls="text-center"
                            ),
                            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
                        ),
                        Div(
                            Div(
                                Span("❓", cls="text-3xl mb-3"),
                                Div(str(unknown_visits), cls="text-3xl font-bold text-slate-100"),
                                Div("Unknown", cls="text-sm uppercase tracking-wider text-slate-400 font-semibold mt-2"),
                                Div(
                                    f"{(unknown_visits/total_visits*100 if total_visits > 0 else 0):.1f}%",
                                    cls="text-xs text-slate-500 mt-1"
                                ),
                                cls="text-center"
                            ),
                            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-3 gap-6"
                    ),
                    cls="bg-slate-900/50 rounded-xl p-6 border border-slate-700"
                ),
                cls="max-w-7xl mx-auto px-4 pb-8"
            ),
            
            # Category Statistics
            Div(
                Div(
                    Div(
                        H2("Category Popularity", cls="text-2xl font-bold text-slate-100"),
                        cls="px-6 py-5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-b border-slate-700"
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Category", cls="px-4 py-3 text-left text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Visits", cls="px-4 py-3 text-center text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Visual", cls="px-4 py-3 text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Percentage", cls="px-4 py-3 text-center text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                )
                            ),
                            Tbody(*category_rows) if category_rows else Tbody(
                                Tr(Td("No category data yet", colspan="4", cls="px-4 py-6 text-center text-slate-500"))
                            ),
                            cls="w-full"
                        ),
                        cls="overflow-x-auto"
                    ),
                    cls="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 overflow-hidden animate-fade-in"
                ),
                cls="max-w-7xl mx-auto px-4 pb-8"
            ),
            
            # Recent Activity
            Div(
                Div(
                    Div(
                        H2("Recent Activity", cls="text-2xl font-bold text-slate-100"),
                        cls="px-6 py-5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-b border-slate-700"
                    ),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("Timestamp", cls="px-4 py-3 text-left text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Page", cls="px-4 py-3 text-left text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Category", cls="px-4 py-3 text-left text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                    Th("Device", cls="px-4 py-3 text-left text-slate-400 uppercase text-xs font-semibold tracking-wider border-b-2 border-slate-700"),
                                )
                            ),
                            Tbody(*recent_rows) if recent_rows else Tbody(
                                Tr(Td("No visits yet", colspan="4", cls="px-4 py-6 text-center text-slate-500"))
                            ),
                            cls="w-full"
                        ),
                        cls="overflow-x-auto"
                    ),
                    cls="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 overflow-hidden animate-fade-in"
                ),
                cls="max-w-7xl mx-auto px-4 pb-12"
            ),
            
            # Footer
            Div(
                Div(
                    P(
                        "v0.0.1",
                        cls="text-slate-500 text-sm font-mono"
                    ),
                    cls="max-w-7xl mx-auto px-4 py-6 text-right"
                ),
                cls="border-t border-slate-700/50"
            ),
            
            cls="min-h-screen py-8"
        )
    )

@rt("/")
def get(request, category: str = "expert"):
    """Main page route with Tailwind styling"""
    # Track this visit
    user_agent = request.headers.get('user-agent', '')
    track_visit("home", category, user_agent)
    
    # Load data for selected category
    df = load_category_data(category)
    
    # Calculate some stats
    total_riders = len(df) if df is not None else 0
    total_races = len(get_race_columns(df)) if df is not None else 0
    
    # Create category tabs with Tailwind styling
    tabs = []
    for cat_key, cat_name in CATEGORIES.items():
        if cat_key == category:
            tabs.append(
                A(
                    cat_name, 
                    href=f"/?category={cat_key}", 
                    cls="px-6 py-3 gradient-bg text-white rounded-lg font-semibold shadow-lg transform hover:scale-105 transition-all duration-200"
                )
            )
        else:
            tabs.append(
                A(
                    cat_name, 
                    href=f"/?category={cat_key}", 
                    cls="px-6 py-3 bg-slate-800 text-slate-300 border-2 border-slate-700 rounded-lg font-semibold hover:border-blue-500 hover:bg-blue-500/10 hover:text-slate-100 transform hover:-translate-y-0.5 transition-all duration-200"
                )
            )
    
    # Stats with Tailwind styling
    stats = Div(
        Div(
            # Total Riders
            Div(
                Div(
                    Span("👥", cls="text-3xl mb-2"),
                    Div(str(total_riders), cls="text-3xl font-bold text-slate-100"),
                    Div("Total Riders", cls="text-xs uppercase tracking-wider text-slate-400 font-semibold mt-1"),
                    cls="text-center"
                ),
                cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
            ),
            # Total Races
            Div(
                Div(
                    Span("🏁", cls="text-3xl mb-2"),
                    Div(str(total_races), cls="text-3xl font-bold text-slate-100"),
                    Div("Total Races", cls="text-xs uppercase tracking-wider text-slate-400 font-semibold mt-1"),
                    cls="text-center"
                ),
                cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
            ),
            # Current Category
            Div(
                Div(
                    Span("🏆", cls="text-3xl mb-2"),
                    Div(CATEGORIES[category], cls="text-3xl font-bold text-slate-100"),
                    Div("Category", cls="text-xs uppercase tracking-wider text-slate-400 font-semibold mt-1"),
                    cls="text-center"
                ),
                cls="bg-slate-800 rounded-xl p-6 border border-slate-700 shadow-lg"
            ),
            cls="grid grid-cols-1 md:grid-cols-3 gap-4"
        ),
        cls="max-w-7xl mx-auto px-4 pb-8"
    )
    
    return Html(
        Head(
            Title("BGX Hard Enduro Championship 2025 (Unofficial)"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                tailwind.config = {
                    theme: {
                        extend: {
                            colors: {
                                primary: '#2563eb',
                                secondary: '#7c3aed',
                            }
                        }
                    }
                }
            """),
            Style("""
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
                
                * {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                }
                
                body {
                    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                }
                
                .gradient-text {
                    background: linear-gradient(135deg, #2563eb, #7c3aed);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                
                .gradient-bg {
                    background: linear-gradient(135deg, #2563eb, #7c3aed);
                }
                
                .position-badge-1 {
                    background: linear-gradient(135deg, #fbbf24, #f59e0b);
                }
                
                .position-badge-2 {
                    background: linear-gradient(135deg, #e2e8f0, #94a3b8);
                }
                
                .position-badge-3 {
                    background: linear-gradient(135deg, #f97316, #ea580c);
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .animate-fade-in {
                    animation: fadeIn 0.5s ease-out;
                }
            """)
        ),
        Body(
            # Header Section
            Div(
                H1(
                    "🏆 BGX Hard Enduro Championship 2025 (Unofficial)",
                    cls="text-4xl md:text-5xl lg:text-6xl font-black gradient-text mb-3"
                ),
                P(
                    "BGX Hard Enduro Championship 2025 Results from first navigation day",
                    cls="text-slate-400 text-lg md:text-xl"
                ),
                cls="text-center py-12 px-4"
            ),
            # Category Tabs
            Div(
                *tabs, 
                cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 max-w-5xl mx-auto mb-8 px-4"
            ),
            # Stats Section
            stats,
            # Leaderboard Section
            Div(
                create_leaderboard_table(df, category),
                cls="max-w-7xl mx-auto px-4 pb-12"
            ),
            # Footer
            Div(
                Div(
                    P(
                        "v0.0.1",
                        cls="text-slate-500 text-sm font-mono"
                    ),
                    cls="max-w-7xl mx-auto px-4 py-6 text-right"
                ),
                cls="border-t border-slate-700/50"
            ),
            cls="min-h-screen py-8"
        )
    )

if __name__ == "__main__":
    import os
    # Support environment variables for deployment
    port = int(os.getenv("PORT", 5001))
    host = os.getenv("HOST", "0.0.0.0")
    serve(host=host, port=port)

