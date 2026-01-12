"""
Database initialization and connection management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import os

from .models import Base
from ..config.settings import settings
from ..config.logging import logger

# Create engine
if "sqlite" in settings.database_url:
    engine = create_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        settings.database_url,
        echo=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # Check connection health before using
        pool_recycle=3600,    # Recycle connections every hour
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    """Initialize database - create all tables and seed symbols"""
    import time
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized successfully")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Failed to initialize database after {max_retries} attempts: {e}")
                raise
            logger.warning(f"⚠️ Database initialization attempt {attempt+1} failed: {e}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)
            
    # Seed FNO symbols after tables are created
    db = SessionLocal()
    try:
        from .seed_symbols import seed_symbols
        added = seed_symbols(db, use_api=False)  # use_api=False to use our FNO_SYMBOLS list
        logger.info(f"✅ Seeded {added} FNO symbols into database")
    except Exception as e:
        logger.warning(f"Database initialization warning (app will continue): {e}")
    finally:
        db.close()
        # Don't raise - allow app to start even if DB connection fails
        # This is useful for testing and verification


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def close_db():
    """Close database connection"""
    engine.dispose()
