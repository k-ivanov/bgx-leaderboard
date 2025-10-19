"""Database models for visit tracking."""

from dataclasses import dataclass


@dataclass
class Visit:
    """Model for tracking page visits."""
    id: int = None
    timestamp: str = None
    page: str = None
    category: str = None
    device_type: str = None

