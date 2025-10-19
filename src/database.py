"""Database initialization and operations."""

from datetime import datetime
from fastlite import Database
from .config import DB_PATH
from .models import Visit


# Initialize database
db = Database(DB_PATH)

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
    """Detect if the request is from mobile or desktop based on User-Agent."""
    if not user_agent:
        return "unknown"
    
    user_agent_lower = user_agent.lower()
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    
    for indicator in mobile_indicators:
        if indicator in user_agent_lower:
            return "mobile"
    
    return "desktop"


def track_visit(page: str, category: str = "", user_agent: str = ""):
    """Track a page visit with device type."""
    device_type = detect_device_type(user_agent)
    visits_table.insert(
        timestamp=datetime.now().isoformat(),
        page=page,
        category=category,
        device_type=device_type
    )

