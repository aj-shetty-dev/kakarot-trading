"""
Migration script to fix Signal table constraints
"""
import sys
import os

# Add the current directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data.database import engine
from sqlalchemy import text

def migrate():
    print("🚀 Starting database migration...")
    try:
        with engine.connect() as conn:
            # 1. Make tick_id nullable in signals table
            print("Updating 'signals' table: making 'tick_id' nullable...")
            conn.execute(text("ALTER TABLE signals ALTER COLUMN tick_id DROP NOT NULL;"))
            
            # 2. Ensure new tables are created (Candle, MLFeatureLog)
            from src.data.models import Base
            Base.metadata.create_all(bind=engine)
            
            conn.commit()
            print("✅ Migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
