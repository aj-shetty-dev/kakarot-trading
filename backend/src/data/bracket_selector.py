"""
Bracket Selector Service
Selects bracketing PE/CE options for each symbol based on current price
Uses OptionsChainServiceV3 (database-based) for reliable symbol lookup
"""

from typing import Dict, List, Optional, Tuple
from ..config.logging import logger
from .options_service_v3 import get_options_service_v3


class BracketSelector:
    """Service to select bracketing options (PE above, CE below current price)"""
    
    def __init__(self):
        self.bracket_options: Dict[str, Dict] = {}  # symbol -> {pe: {...}, ce: {...}}
        self.is_initialized = False
    
    def select_bracket_options(
        self,
        base_symbol: str,
        current_price: float,
        expiry: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Select bracketing PE and CE for a symbol at current price
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE")
            current_price: Current LTP/price
            expiry: Optional expiry (if None, uses nearest)
        
        Returns:
            Dict with PE and CE selections or None if not found
            {
                "symbol": "RELIANCE",
                "price": 1250.0,
                "expiry": "2025-12-30",
                "pe": {
                    "tradingsymbol": "RELIANCE 1300 PE 30 DEC 25",
                    "strike": 1300.0,
                    "exchange_token": 123456,
                    ...
                },
                "ce": {
                    "tradingsymbol": "RELIANCE 1200 CE 30 DEC 25",
                    "strike": 1200.0,
                    "exchange_token": 123457,
                    ...
                }
            }
        """
        service = get_options_service_v3()
        
        if not service.is_initialized:
            logger.warning(f"❌ Options service not initialized")
            return None
        
        # Get available expiries for this symbol
        available_expiries = service.get_available_expiries(base_symbol)
        
        if not available_expiries:
            logger.warning(f"⚠️  No options found for symbol: {base_symbol}")
            return None
        
        # Use provided expiry or nearest one
        if expiry is None:
            selected_expiry = available_expiries[0]  # First = nearest
            logger.debug(f"Using nearest expiry for {base_symbol}: {selected_expiry}")
        else:
            if expiry not in available_expiries:
                logger.warning(f"⚠️  Expiry {expiry} not available for {base_symbol}")
                return None
            selected_expiry = expiry
        
        # Get all strikes for this symbol and expiry
        all_options = service.get_chain_for_symbol(base_symbol, expiry=selected_expiry)
        
        if not all_options:
            logger.warning(f"⚠️  No options for {base_symbol} on expiry {selected_expiry}")
            return None
        
        # Get unique strikes
        strikes = sorted(set(o["strike"] for o in all_options))
        
        # Find closest strike ABOVE current price (for PE)
        pe_strike = None
        for strike in strikes:
            if strike >= current_price:
                pe_strike = strike
                break
        
        # Find closest strike BELOW current price (for CE)
        ce_strike = None
        for strike in reversed(strikes):
            if strike <= current_price:
                ce_strike = strike
                break
        
        # If price is at edge, we might not have both
        if pe_strike is None or ce_strike is None:
            logger.warning(
                f"⚠️  Could not find bracket for {base_symbol} at price {current_price}. "
                f"PE: {pe_strike}, CE: {ce_strike}"
            )
            return None
        
        # Get the actual option contracts
        pe_option = None
        ce_option = None
        
        for option in all_options:
            if option["strike"] == pe_strike and option["type"] == "PE":
                pe_option = option
            if option["strike"] == ce_strike and option["type"] == "CE":
                ce_option = option
        
        if not pe_option or not ce_option:
            logger.warning(f"⚠️  Could not find PE or CE for {base_symbol}")
            return None
        
        result = {
            "symbol": base_symbol,
            "price": current_price,
            "expiry": selected_expiry,
            "pe": pe_option,
            "ce": ce_option,
        }
        
        return result
    
    def get_bracket_symbols(self) -> List[Dict]:
        """
        Get list of all bracket options selected
        
        Returns:
            List of bracket option dicts
        """
        return list(self.bracket_options.values())
    
    def get_bracket_tradingsymbols(self) -> List[str]:
        """
        Get trading symbols for all selected bracket options (for WebSocket subscription)
        
        Returns:
            List of trading symbols like ["RELIANCE 1300 PE 30 DEC 25", ...]
        """
        symbols = []
        for bracket in self.bracket_options.values():
            symbols.append(bracket["pe"]["tradingsymbol"])
            symbols.append(bracket["ce"]["tradingsymbol"])
        return symbols
    
    def get_bracket_upstox_symbols(self) -> List[str]:
        """
        Get Upstox format trading symbols for WebSocket subscription
        
        Returns:
            List of symbols like ["NSE_FO|RELIANCE 1300 PE 30 DEC 25", ...]
        """
        upstox_symbols = []
        for ts in self.get_bracket_tradingsymbols():
            upstox_symbols.append(f"NSE_FO|{ts}")
        return upstox_symbols


# Global instance
_bracket_selector: Optional[BracketSelector] = None


def get_bracket_selector() -> BracketSelector:
    """Get or create the bracket selector instance"""
    global _bracket_selector
    if _bracket_selector is None:
        _bracket_selector = BracketSelector()
    return _bracket_selector
