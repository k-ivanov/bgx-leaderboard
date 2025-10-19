"""UI components and styling for the dashboard."""

import pandas as pd
from fasthtml.common import *
from .config import CATEGORIES
from .data_loader import get_race_columns, format_race_name


def get_styles():
    """Return the CSS styles for the application."""
    return Style("""
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


def create_position_badge(position: int):
    """Create a position badge with appropriate styling."""
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


def create_leaderboard_table(df, category: str):
    """Create the leaderboard table with Tailwind styling."""
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


def create_footer():
    """Create the footer component."""
    return Div(
        Div(
            P(
                "v0.0.1",
                cls="text-slate-500 text-sm font-mono"
            ),
            cls="max-w-7xl mx-auto px-4 py-6 text-right"
        ),
        cls="border-t border-slate-700/50"
    )

