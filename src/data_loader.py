"""Data loading and processing functions."""

import pandas as pd
from .config import RESULTS_PATH, RACE_ORDER


def load_category_data(category: str):
    """Load CSV data for a specific category."""
    csv_path = RESULTS_PATH / f"{category}.csv"
    if not csv_path.exists():
        return None
    
    df = pd.read_csv(csv_path)
    return df


def get_race_columns(df):
    """Extract race column names from the dataframe and sort them by race order."""
    # Get all race columns from the dataframe
    race_cols = [col for col in df.columns if col.startswith('Race_')]
    
    # Sort by the defined order, put any unexpected columns at the end
    def sort_key(col):
        if col in RACE_ORDER:
            return RACE_ORDER.index(col)
        return len(RACE_ORDER)  # Put unknown races at the end
    
    race_cols.sort(key=sort_key)
    return race_cols


def format_race_name(race_col: str) -> str:
    """Format race column name for display."""
    name = race_col.replace('Race_', '').replace('_', ' ')
    return name.title()

