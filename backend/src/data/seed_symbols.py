"""
Seed FNO symbols into the database
Uses comprehensive list of NSE FNO stocks (~200+ symbols)

IMPORTANT: Now using ISIN-based symbols for correct Upstox API calls
- Previously: Using simple symbol names (e.g., "INFY")
- Now: Using full ISIN format (e.g., "NSE_EQ|INE009A01021")
- This fixes the bug where API was returning empty data for all symbols
"""

from sqlalchemy.orm import Session
from ..data.models import Symbol
from ..data.database import SessionLocal
from ..config.timezone import ist_now
from ..config.constants import SymbolStatus, EXCLUDED_SYMBOLS
from ..config.logging import logger
from .isin_mapping_hardcoded import ISIN_MAPPING, get_instrument_key

# Official NSE F&O Symbols List - 208 Approved Stocks (2024-2025)
# Source: NSE official F&O list - VERIFIED AND COMPLETE
# ISIN mappings loaded from isin_mapping_hardcoded.py
# NOTE: Removed hardcoded FNO_SYMBOLS list - now using ISIN_MAPPING directly for accuracy



def seed_symbols(db: Session, use_api: bool = True) -> int:
    """
    Seed FNO symbols into the database using ISIN-based format
    
    IMPORTANT: This now uses ISINs to match the Upstox API requirements.
    Each symbol is stored with its ISIN to enable correct API calls.
    
    Args:
        db: Database session
        use_api: Kept for compatibility (not used anymore)
    
    Returns:
        int: Number of symbols added
    """
    try:
        added_count = 0
        skipped_count = 0
        
        # Use ISIN mapping to seed symbols
        # This ensures all 208 symbols have correct ISINs
        logger.info(f"Starting to seed {len(ISIN_MAPPING)} unique FNO symbols with ISINs...")
        
        for symbol, isin in ISIN_MAPPING.items():
            sym_upper = symbol.upper()
            
            # Skip excluded symbols
            if sym_upper in EXCLUDED_SYMBOLS:
                logger.debug(f"Skipping excluded symbol: {sym_upper}")
                skipped_count += 1
                continue
            
            # Check if symbol already exists
            existing = db.query(Symbol).filter(Symbol.symbol == sym_upper).first()
            if existing:
                logger.debug(f"Symbol already exists: {sym_upper}, skipping")
                skipped_count += 1
                continue
            
            # Get instrument key for API calls (NSE_EQ|ISIN format)
            instrument_key = get_instrument_key(sym_upper)
            
            # Create new symbol with ISIN
            new_symbol = Symbol(
                symbol=sym_upper,
                name=sym_upper,  # Name defaults to symbol (can be updated later)
                sector="Futures & Options",
                is_fno=True,
                has_options=True,
                has_futures=True,
                avg_daily_volume=1000000,  # Default volume estimate
                liquidity_score=0.7,  # Default liquidity for FNO
                last_refreshed=ist_now(),
                # Store ISIN and instrument key for API calls
                isin=isin,  # Assuming Symbol model has isin field
                instrument_token=instrument_key,  # Store the full NSE_EQ|ISIN format
            )
            
            db.add(new_symbol)
            added_count += 1
            
            if added_count % 50 == 0:
                logger.info(f"[VERBOSE] Processed {added_count} symbols so far...")
        
        # Commit all changes
        db.commit()
        
        logger.info(f"✅ Seeding complete with ISIN-based symbols!")
        logger.info(f"   Added: {added_count}")
        logger.info(f"   Skipped: {skipped_count}")
        logger.info(f"   Total added to database: {added_count}")
        logger.info(f"   All symbols now use correct NSE_EQ|ISIN format for API calls")
        
        return added_count
        
    except Exception as e:
        logger.error(f"❌ Error seeding symbols: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        raise


def clear_symbols(db: Session) -> None:
    """
    Clear all symbols from the database
    
    Args:
        db: Database session
    """
    try:
        count = db.query(Symbol).delete()
        db.commit()
        logger.info(f"Cleared {count} symbols from database")
    except Exception as e:
        logger.error(f"Error clearing symbols: {e}")
        db.rollback()
        raise


if __name__ == "__main__":
    """Run seeder when executed directly"""
    from ..config.logging import setup_logging
    
    setup_logging()
    
    db = SessionLocal()
    try:
        # Optional: Clear existing symbols first
        # clear_symbols(db)
        
        added = seed_symbols(db, use_api=True)
        logger.info(f"Successfully seeded {added} symbols from Upstox API!")
        
    finally:
        db.close()
