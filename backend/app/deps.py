"""Shared FastAPI dependencies (eng-review N2).

Centralizes the common lookups that would otherwise repeat across every router:
  - DB session lifetime
  - Season-by-year (404 if missing)
  - Category-by-code (404 if missing within the season)
"""

from typing import Iterator

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Category, Season
from src.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    """Yields a SQLAlchemy session per request; commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_season(
    year: int = Path(..., ge=1900, le=2999),
    session: Session = Depends(get_session),
) -> Season:
    season = session.execute(select(Season).where(Season.year == year)).scalar_one_or_none()
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Season {year} not found",
        )
    return season


def get_category(
    category_code: str = Path(...),
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> Category:
    category = session.execute(
        select(Category).where(
            Category.season_id == season.id,
            Category.code == category_code,
        )
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_code}' not found in season {season.year}",
        )
    return category
