"""Route handlers for the BGX Navigation Dashboard."""

from datetime import datetime
from fasthtml.common import *
from .config import CATEGORIES, APP_VERSION
from .database import track_visit, visits_table
from .data_loader import load_category_data, get_race_columns
from .ui_components import create_leaderboard_table, create_footer, get_styles


def setup_routes(app, rt):
    """Set up all application routes."""
    
    @rt("/health")
    def health():
        """Health check endpoint for monitoring."""
        return {
            "status": "healthy",
            "service": "bgx-navigation-dashboard",
            "version": APP_VERSION
        }

    @rt("/stats")
    def stats(request):
        """Statistics page showing visit analytics."""
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
                get_styles()
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
                create_footer(),
                
                cls="min-h-screen py-8"
            )
        )

    @rt("/")
    def get(request, category: str = "expert"):
        """Main page route with Tailwind styling."""
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
                get_styles()
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
                create_footer(),
                cls="min-h-screen py-8"
            )
        )

