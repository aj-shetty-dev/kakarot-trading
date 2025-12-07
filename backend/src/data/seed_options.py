"""
Seed options chains into the database
Generates mock options chains for testing
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..data.models import OptionChain, Symbol
from ..data.database import SessionLocal
from ..config.logging import logger

# Standard option strikes relative to spot price (in percentages)
STRIKE_INTERVALS = [
    -10, -9, -8, -7, -6, -5, -4, -3, -2, -1,  # ITM calls (OTM puts)
    0,                                           # ATM
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,            # OTM calls (ITM puts)
]

# Standard expiries
def get_standard_expiries():
    """Get standard option expiries (4 nearest Thursday/Friday expiries)"""
    today = datetime.utcnow()
    expiries = []
    
    # Find next 4 Thursdays
    current_date = today
    expiry_count = 0
    
    while expiry_count < 4:
        # Check if it's a Thursday (weekday 3) or Friday (weekday 4)
        if current_date.weekday() in [3, 4]:  # Thursday or Friday
            expiry_date = current_date.replace(hour=15, minute=30, second=0, microsecond=0)
            if expiry_date > today:  # Only future expiries
                expiries.append(expiry_date.strftime("%Y-%m-%d"))
                expiry_count += 1
        
        current_date += timedelta(days=1)
    
    return expiries


def generate_strikes_for_symbol(base_symbol: str, spot_price: float = 1000.0) -> list:
    """
    Generate strikes for a symbol
    
    Args:
        base_symbol: Symbol name (e.g., "RELIANCE")
        spot_price: Current spot price (default 1000 for testing)
    
    Returns:
        List of tuples: (strike_price, lot_size)
    """
    strikes = []
    
    for interval_pct in STRIKE_INTERVALS:
        strike = spot_price + (spot_price * interval_pct / 100)
        
        # Round to nearest standard strike interval (typically 10 for liquid symbols)
        strike = round(strike / 10) * 10
        
        # Determine lot size based on symbol (these are realistic NSE lot sizes)
        lot_sizes = {
            "RELIANCE": 1,
            "HDFC": 1,
            "TCS": 1,
            "INFY": 1,
            "MARUTI": 1,
            "ACC": 250,
            "VEDANT": 500,
            "UTPL": 1000,
            "SBIN": 1,
        }
        
        lot_size = lot_sizes.get(base_symbol, 100)  # Default 100 if not in list
        strikes.append((strike, lot_size))
    
    # Remove duplicates while preserving order
    seen_strikes = set()
    unique_strikes = []
    for strike, lot_size in strikes:
        if strike not in seen_strikes:
            seen_strikes.add(strike)
            unique_strikes.append((strike, lot_size))
    
    return unique_strikes


def seed_options_chains(db: Session) -> int:
    """
    Seed options chains into the database
    
    Args:
        db: Database session
    
    Returns:
        int: Number of option contracts added
    """
    try:
        added_count = 0
        
        # Get all symbols with options
        symbols = db.query(Symbol).filter(Symbol.has_options == True).all()
        
        logger.info(f"Starting to seed options chains for {len(symbols)} symbols...")
        
        # Get expiries
        expiries = get_standard_expiries()
        logger.info(f"Using {len(expiries)} expiries: {expiries}")
        
        for symbol in symbols:
            # Skip if too many symbols to avoid timeout
            if len(symbols) > 50:
                spot_price = 1000.0  # Default for testing
            else:
                spot_price = 1000.0
            
            # Generate strikes
            strikes = generate_strikes_for_symbol(symbol.symbol, spot_price)
            
            # Create option contracts for each expiry and strike
            for expiry in expiries:
                for strike_price, lot_size in strikes:
                    # Create CE (Call) option
                    ce_contract = OptionChain(
                        symbol=symbol.symbol,
                        option_type="CE",
                        strike_price=strike_price,
                        expiry_date=expiry,
                        trading_symbol=f"{symbol.symbol}{expiry[5:].replace('-', '')}{int(strike_price)}CE",
                        lot_size=lot_size,
                        exchange_token=f"CE_{symbol.symbol}_{strike_price}_{expiry}",
                    )
                    db.add(ce_contract)
                    added_count += 1
                    
                    # Create PE (Put) option
                    pe_contract = OptionChain(
                        symbol=symbol.symbol,
                        option_type="PE",
                        strike_price=strike_price,
                        expiry_date=expiry,
                        trading_symbol=f"{symbol.symbol}{expiry[5:].replace('-', '')}{int(strike_price)}PE",
                        lot_size=lot_size,
                        exchange_token=f"PE_{symbol.symbol}_{strike_price}_{expiry}",
                    )
                    db.add(pe_contract)
                    added_count += 1
            
            if symbols.index(symbol) % 10 == 0:
                logger.info(f"[VERBOSE] Processed {symbols.index(symbol)} symbols, {added_count} contracts so far...")
        
        # Commit
        db.commit()
        
        logger.info(f"✅ Seeding options complete!")
        logger.info(f"   Added: {added_count} option contracts")
        
        return added_count
        
    except Exception as e:
        logger.error(f"❌ Error seeding options: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        raise


def clear_options(db: Session) -> None:
    """
    Clear all options chains from the database
    
    Args:
        db: Database session
    """
    try:
        count = db.query(OptionChain).delete()
        db.commit()
        logger.info(f"Cleared {count} option contracts from database")
    except Exception as e:
        logger.error(f"Error clearing options: {e}")
        db.rollback()
        raise


if __name__ == "__main__":
    """Run seeder when executed directly"""
    from ..config.logging import setup_logging
    
    setup_logging()
    
    db = SessionLocal()
    try:
        # Clear existing options
        clear_options(db)
        
        # Seed options
        added = seed_options_chains(db)
        logger.info(f"Successfully seeded {added} options contracts!")
        
    finally:
        db.close()
