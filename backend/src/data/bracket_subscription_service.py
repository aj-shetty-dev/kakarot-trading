"""
Bracket Options Auto-Subscription Service
Automatically selects and subscribes to bracket options (PE/CE) for all symbols
"""

from typing import Dict, List, Optional
from ..config.logging import logger
from .bracket_selector import get_bracket_selector
from .fno_fetcher import get_fno_symbols


class BracketSubscriptionService:
    """Service to auto-subscribe to bracket options based on current prices"""
    
    def __init__(self):
        self.is_initialized = False
        self.symbol_prices: Dict[str, float] = {}  # symbol -> current price
        self.selected_brackets: Dict[str, Dict] = {}  # symbol -> bracket info
    
    async def initialize(self, symbol_prices: Dict[str, float]) -> bool:
        """
        Initialize and select bracket options for all symbols
        
        Args:
            symbol_prices: Dict mapping symbol -> current LTP price
                          e.g., {"RELIANCE": 1250.5, "TCS": 3500.0}
        
        Returns:
            True if successful
        """
        try:
            logger.info("🎯 Initializing bracket subscription service...")
            
            selector = get_bracket_selector()
            self.symbol_prices = symbol_prices
            
            # Select bracket options for each symbol
            for symbol, price in symbol_prices.items():
                try:
                    bracket = selector.select_bracket_options(symbol, price)
                    
                    if bracket:
                        self.selected_brackets[symbol] = bracket
                        logger.debug(
                            f"✅ Bracket for {symbol} @ {price}: "
                            f"PE({bracket['pe']['strike']}) / CE({bracket['ce']['strike']})"
                        )
                    else:
                        logger.warning(f"⚠️  No bracket for {symbol} @ {price}")
                
                except Exception as e:
                    logger.warning(f"⚠️  Error selecting bracket for {symbol}: {e}")
                    continue
            
            self.is_initialized = True
            
            logger.info(f"✅ Bracket service initialized: {len(self.selected_brackets)} symbols selected")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize bracket service: {e}")
            return False
    
    def get_bracket_upstox_symbols(self) -> List[str]:
        """
        Get all bracket options in Upstox format for WebSocket subscription
        
        Returns:
            List of symbols like ["NSE_FO|RELIANCE 1300 PE 30 DEC 25", ...]
        """
        upstox_symbols = []
        
        for symbol, bracket in self.selected_brackets.items():
            pe_symbol = f"NSE_FO|{bracket['pe']['tradingsymbol']}"
            ce_symbol = f"NSE_FO|{bracket['ce']['tradingsymbol']}"
            
            upstox_symbols.append(pe_symbol)
            upstox_symbols.append(ce_symbol)
        
        return upstox_symbols
    
    def get_bracket_stats(self) -> Dict:
        """Get statistics about selected brackets"""
        return {
            "initialized": self.is_initialized,
            "total_symbols": len(self.symbol_prices),
            "brackets_selected": len(self.selected_brackets),
            "total_options": len(self.selected_brackets) * 2,
            "symbols_with_brackets": list(self.selected_brackets.keys())
        }


# Global instance
_bracket_subscription_service: Optional[BracketSubscriptionService] = None


def get_bracket_subscription_service() -> BracketSubscriptionService:
    """Get or create the bracket subscription service"""
    global _bracket_subscription_service
    if _bracket_subscription_service is None:
        _bracket_subscription_service = BracketSubscriptionService()
    return _bracket_subscription_service


async def initialize_bracket_service(symbol_prices: Dict[str, float]) -> bool:
    """
    Initialize the bracket subscription service
    
    Args:
        symbol_prices: Dict mapping symbol -> current price
    
    Returns:
        True if successful
    """
    service = get_bracket_subscription_service()
    return await service.initialize(symbol_prices)
