"""
FNO (Futures & Options) Symbol Universe Management
Fetches and manages the list of tradeable symbols from Upstox
"""

import asyncio
from typing import List, Set
from sqlalchemy.orm import Session
import aiohttp

from ..config.settings import settings
from ..config.constants import EXCLUDED_SYMBOLS
from ..config.logging import logger
from ..data.models import Symbol
from ..data.database import SessionLocal


class FNOUniverse:
    """Manages FNO symbol universe"""

    def __init__(self):
        self.symbols: Set[str] = set()
        self.excluded_symbols: Set[str] = EXCLUDED_SYMBOLS
        self.last_updated = None

    async def fetch_from_upstox(self) -> List[str]:
        """
        Fetch all FNO symbols from Upstox API
        
        Returns:
            List of FNO symbols
        """
        try:
            # TODO: Implement actual Upstox API call to get all FNO symbols
            # For now, returning a sample list
            logger.info("Fetching FNO symbols from Upstox...")
            
            # Sample FNO symbols (replace with actual API call)
            sample_symbols = [
                "INFY", "TCS", "RELIANCE", "HDFC", "ICICIBANK",
                "SBIN", "WIPRO", "LT", "MARUTI", "BAJAJFINSV",
                "BRITANNIA", "HCLTECH", "MINDTREE", "AXISBANK", "NTPC",
                "POWERGRID", "INDIGO", "APOLLOHOSP", "HEROMOTOCO", "BHARTIARTL",
                "JSWSTEEL", "TATASTEEL", "COALINDIA", "GAIL", "ONGC",
                "BPCL", "HDFCBANK", "EICHERMOT", "SUNPHARMA", "BAJAJFINSV"
            ]
            
            return sample_symbols
            
        except Exception as e:
            logger.error(f"Error fetching FNO symbols: {e}")
            raise

    def filter_symbols(self, symbols: List[str]) -> List[str]:
        """
        Filter symbols by excluding specified ones
        
        Args:
            symbols: List of symbols to filter
            
        Returns:
            Filtered list of symbols
        """
        filtered = [s for s in symbols if s not in self.excluded_symbols]
        logger.info(f"Filtered {len(symbols)} symbols to {len(filtered)} (excluded: {len(self.excluded_symbols)})")
        logger.debug(f"Excluded symbols: {self.excluded_symbols}")
        return filtered

    async def refresh_universe(self, db: Session) -> Set[str]:
        """
        Refresh FNO universe from Upstox API and store in database
        
        Args:
            db: Database session
            
        Returns:
            Set of active FNO symbols
        """
        try:
            logger.info("Starting FNO universe refresh...")
            
            # Fetch symbols from Upstox
            fno_symbols = await self.fetch_from_upstox()
            
            # Filter excluded symbols
            filtered_symbols = self.filter_symbols(fno_symbols)
            
            # Store in database
            for symbol_name in filtered_symbols:
                existing = db.query(Symbol).filter(Symbol.symbol == symbol_name).first()
                
                if not existing:
                    symbol = Symbol(
                        symbol=symbol_name,
                        name=symbol_name,  # TODO: Get full name from API
                        is_fno=True,
                        has_options=True,
                        has_futures=True,
                    )
                    db.add(symbol)
                    logger.debug(f"Added symbol: {symbol_name}")
            
            db.commit()
            self.symbols = set(filtered_symbols)
            
            logger.info(f"✅ FNO universe refreshed: {len(self.symbols)} symbols")
            return self.symbols
            
        except Exception as e:
            logger.error(f"Error refreshing FNO universe: {e}")
            db.rollback()
            raise

    def get_active_symbols(self) -> List[str]:
        """Get current list of active symbols"""
        return sorted(list(self.symbols))

    def is_tradeable(self, symbol: str) -> bool:
        """Check if symbol is tradeable"""
        return symbol in self.symbols and symbol not in self.excluded_symbols


# Global FNO universe instance
fno_universe = FNOUniverse()


async def initialize_fno_universe():
    """Initialize FNO universe at startup"""
    try:
        db = SessionLocal()
        await fno_universe.refresh_universe(db)
        db.close()
    except Exception as e:
        logger.error(f"Failed to initialize FNO universe: {e}")
        raise
