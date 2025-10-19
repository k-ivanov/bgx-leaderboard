# Source Code Structure

This directory contains the modular source code for the BGX Navigation Dashboard.

## Module Overview

### `config.py`
Configuration and constants for the application:
- Application version
- File paths (database, data directory)
- Server settings (port, host)
- Category definitions
- Race order configuration

### `models.py`
Database models using dataclasses:
- `Visit` - Model for tracking page visits with device type

### `database.py`
Database initialization and operations:
- Database connection setup
- Table creation and migration
- `detect_device_type()` - User-Agent parsing
- `track_visit()` - Visit tracking function

### `data_loader.py`
Data loading and processing:
- `load_category_data()` - Load CSV files for each category
- `get_race_columns()` - Extract and sort race columns
- `format_race_name()` - Format race names for display

### `ui_components.py`
Reusable UI components and styling:
- `get_styles()` - CSS styles for the application
- `create_position_badge()` - Position badges (1st, 2nd, 3rd)
- `create_leaderboard_table()` - Main leaderboard table
- `create_footer()` - Footer component

### `routes.py`
HTTP route handlers:
- `setup_routes()` - Configure all application routes
- `/` - Main leaderboard page
- `/stats` - Visit statistics page
- `/health` - Health check endpoint

## Design Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Modularity**: Easy to test, maintain, and extend individual components
3. **Configuration Management**: All constants centralized in `config.py`
4. **Reusable Components**: UI components can be easily reused or modified
5. **Clean Entry Point**: `main.py` is minimal and imports from modules

## Benefits

- **Maintainability**: Easier to find and modify specific functionality
- **Testability**: Each module can be tested independently
- **Readability**: Clear structure makes the codebase easier to understand
- **Scalability**: Easy to add new features without cluttering existing code
- **Collaboration**: Multiple developers can work on different modules

