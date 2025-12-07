"""
Options Chain Service V3 - Database-Based Fetching
Fetches options chains from local PostgreSQL database.
This is the most efficient approach since we already have a database running.
"""

from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import create_engine, text, and_
from ..config.logging import logger
from ..config.settings import settings


class OptionsChainServiceV3:
    """Service to fetch options chains from PostgreSQL database"""
    
    def __init__(self):
        self.db_url = settings.database_url
        self.engine = None
        self.is_initialized = False
        self.last_updated: Optional[datetime] = None
    
    def initialize_sync(self) -> bool:
        """
        Initialize connection to PostgreSQL database (synchronous version)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.is_initialized and self.engine:
                return True
                
            logger.info("🔄 Initializing Options Service V3 (Database-based)...")
            
            # Create engine
            self.engine = create_engine(self.db_url, echo=False)
            
            # Test connection
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.close()
            
            self.is_initialized = True
            self.last_updated = datetime.utcnow()
            logger.info("✅ Options Service V3 initialized (connected to PostgreSQL)")
            
            # Log statistics
            stats = self.get_stats()
            logger.info(f"   📊 Total option contracts in DB: {stats.get('total_options', 0)}")
            logger.info(f"   📊 Base symbols: {stats.get('total_symbols', 0)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize options service V3: {e}")
            self.is_initialized = False
            return False
    
    async def initialize(self) -> bool:
        """
        Initialize connection to PostgreSQL database
        
        Returns:
            True if successful, False otherwise
        """
        return self.initialize_sync()
    
    def get_chain_for_symbol(
        self,
        base_symbol: str,
        expiry: Optional[str] = None
    ) -> List[Dict]:
        """
        Get options chain for a symbol from database
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE")
            expiry: Optional expiry filter (ISO format YYYY-MM-DD)
        
        Returns:
            List of option contracts
        
        Example:
            chain = service.get_chain_for_symbol("RELIANCE")
            chain = service.get_chain_for_symbol("RELIANCE", expiry="2025-12-25")
        """
        if not self.engine:
            logger.error("❌ Database not initialized")
            return []
        
        try:
            with self.engine.connect() as conn:
                # Build query
                query = text("""
                    SELECT 
                        symbol,
                        strike_price as strike,
                        option_type as type,
                        expiry_date as expiry,
                        trading_symbol as tradingsymbol,
                        lot_size,
                        exchange_token
                    FROM option_chains
                    WHERE UPPER(symbol) = UPPER(:symbol)
                """)
                
                params = {"symbol": base_symbol}
                
                # Add expiry filter if provided
                if expiry:
                    query = text("""
                        SELECT 
                            symbol,
                            strike_price as strike,
                            option_type as type,
                            expiry_date as expiry,
                            trading_symbol as tradingsymbol,
                            lot_size,
                            exchange_token
                        FROM option_chains
                        WHERE UPPER(symbol) = UPPER(:symbol)
                        AND expiry_date = :expiry
                    """)
                    params["expiry"] = expiry
                
                result = conn.execute(query, params)
                rows = result.fetchall()
                result.close()
                
                # Convert to list of dicts
                options = [
                    {
                        "symbol": row[0],
                        "strike": float(row[1]) if row[1] else 0.0,
                        "type": row[2],
                        "expiry": row[3],
                        "tradingsymbol": row[4],
                        "lot_size": row[5],
                        "exchange_token": row[6],
                    }
                    for row in rows
                ]
                
                logger.debug(f"📊 Found {len(options)} options for {base_symbol}")
                return options
                
        except Exception as e:
            logger.error(f"❌ Error fetching options for {base_symbol}: {e}")
            return []
    
    def get_available_expiries(self, base_symbol: Optional[str] = None) -> List[str]:
        """
        Get available expiry dates
        
        Args:
            base_symbol: Optional - if provided, only expiries for that symbol
        
        Returns:
            Sorted list of expiry dates
        """
        if not self.engine:
            logger.error("❌ Database not initialized")
            return []
        
        try:
            with self.engine.connect() as conn:
                if base_symbol:
                    query = text("""
                        SELECT DISTINCT expiry_date
                        FROM option_chains
                        WHERE UPPER(symbol) = UPPER(:symbol)
                        AND expiry_date IS NOT NULL
                        ORDER BY expiry_date ASC
                    """)
                    result = conn.execute(query, {"symbol": base_symbol})
                else:
                    query = text("""
                        SELECT DISTINCT expiry_date
                        FROM option_chains
                        WHERE expiry_date IS NOT NULL
                        ORDER BY expiry_date ASC
                    """)
                    result = conn.execute(query)
                
                expiries = [row[0] for row in result.fetchall()]
                result.close()
                return expiries
                
        except Exception as e:
            logger.error(f"❌ Error getting expiries: {e}")
            return []
    
    def get_available_strikes(self, base_symbol: str, expiry: Optional[str] = None) -> List[float]:
        """
        Get available strike prices for a symbol
        
        Args:
            base_symbol: Base symbol
            expiry: Optional expiry filter
        
        Returns:
            Sorted list of strikes
        """
        if not self.engine:
            logger.error("❌ Database not initialized")
            return []
        
        try:
            with self.engine.connect() as conn:
                if expiry:
                    query = text("""
                        SELECT DISTINCT strike_price
                        FROM option_chains
                        WHERE UPPER(symbol) = UPPER(:symbol)
                        AND expiry_date = :expiry
                        ORDER BY strike_price ASC
                    """)
                    result = conn.execute(query, {"symbol": base_symbol, "expiry": expiry})
                else:
                    query = text("""
                        SELECT DISTINCT strike_price
                        FROM option_chains
                        WHERE UPPER(symbol) = UPPER(:symbol)
                        ORDER BY strike_price ASC
                    """)
                    result = conn.execute(query, {"symbol": base_symbol})
                
                strikes = [float(row[0]) for row in result.fetchall() if row[0]]
                result.close()
                return sorted(strikes)
                
        except Exception as e:
            logger.error(f"❌ Error getting strikes: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Get statistics about the options database"""
        if not self.engine:
            return {
                "initialized": False,
                "total_options": 0,
                "total_symbols": 0,
            }
        
        try:
            with self.engine.connect() as conn:
                # Count total options
                result = conn.execute(text("SELECT COUNT(*) FROM option_chains"))
                total_options = result.scalar() or 0
                result.close()
                
                # Count unique symbols
                result = conn.execute(text(
                    "SELECT COUNT(DISTINCT UPPER(symbol)) FROM option_chains"
                ))
                total_symbols = result.scalar() or 0
                result.close()
                
                # Count expiries
                result = conn.execute(text(
                    "SELECT COUNT(DISTINCT expiry_date) FROM option_chains WHERE expiry_date IS NOT NULL"
                ))
                total_expiries = result.scalar() or 0
                result.close()
                
                return {
                    "initialized": self.is_initialized,
                    "last_updated": self.last_updated.isoformat() if self.last_updated else None,
                    "total_options": total_options,
                    "total_symbols": total_symbols,
                    "total_expiries": total_expiries,
                    "mode": "Database (PostgreSQL)",
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting stats: {e}")
            return {"initialized": False, "error": str(e)}


# Global instance
options_service_v3 = OptionsChainServiceV3()


async def initialize_options_service_v3() -> bool:
    """Initialize options service V3 at application startup"""
    return await options_service_v3.initialize()


def get_options_service_v3() -> OptionsChainServiceV3:
    """Get the options service V3 instance (auto-initialize if needed)"""
    if not options_service_v3.is_initialized:
        options_service_v3.initialize_sync()
    return options_service_v3
