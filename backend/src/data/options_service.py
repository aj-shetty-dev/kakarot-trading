"""
Options Chain Service
Fetches and manages options chains for FNO symbols
Uses Upstox complete.json.gz for comprehensive options data
"""

import gzip
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, date
import httpx
from ..config.logging import logger


class OptionsChainService:
    """Service to fetch, cache, and query options chains"""
    
    def __init__(self):
        self.options_index: Dict[str, List[Dict]] = {}  # base_symbol -> list of options
        self.available_expiries: Set[str] = set()
        self.available_strikes: Dict[str, Set[float]] = {}  # base_symbol -> set of strikes
        self.is_initialized = False
        self.last_updated: Optional[datetime] = None
    
    async def initialize(self) -> bool:
        """
        Initialize the options chain index from Upstox JSON
        Should be called at application startup
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🔄 Initializing options chain index...")
            
            # Download the complete instruments file
            url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    logger.error(f"❌ Failed to download instruments: HTTP {response.status_code}")
                    return False
                
                logger.info(f"✅ Downloaded {len(response.content) / 1024 / 1024:.1f}MB")
            
            # Decompress and parse
            decompressed = gzip.decompress(response.content)
            all_instruments = json.loads(decompressed)
            
            logger.info(f"📊 Total instruments: {len(all_instruments)}")
            
            # Build index
            self._build_index(all_instruments)
            
            self.is_initialized = True
            self.last_updated = datetime.utcnow()
            
            logger.info(f"✅ Options index initialized: {len(self.options_index)} base symbols")
            logger.info(f"   Available expiries: {len(self.available_expiries)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize options chain: {e}")
            return False
    
    def _build_index(self, instruments: List[Dict]) -> None:
        """
        Build the in-memory index from all instruments
        
        Args:
            instruments: List of all instruments from complete.json.gz
        """
        options_count = 0
        
        for instrument in instruments:
            # Only process options (CE and PE)
            instrument_type = instrument.get("instrument_type", "")
            
            if instrument_type not in ["CE", "PE"]:
                continue
            
            # Skip if no trading symbol
            trading_symbol = instrument.get("trading_symbol", "")
            if not trading_symbol:
                continue
            
            options_count += 1
            
            # Extract base symbol - use underlying_symbol
            base_symbol = instrument.get("underlying_symbol", "")
            
            if not base_symbol:
                continue
            
            # Initialize if first time seeing this symbol
            if base_symbol not in self.options_index:
                self.options_index[base_symbol] = []
                self.available_strikes[base_symbol] = set()
            
            # Create option contract record
            strike = instrument.get("strike_price", 0.0)
            expiry = instrument.get("expiry", "")
            
            option_data = {
                "tradingsymbol": trading_symbol,
                "exchange_token": instrument.get("exchange_token", ""),
                "type": instrument_type,  # "CE" or "PE"
                "strike": strike,
                "expiry": expiry,
                "lot_size": instrument.get("lot_size", 1),
                "tick_size": instrument.get("tick_size", 0.05),
                "segment": instrument.get("segment", ""),
            }
            
            self.options_index[base_symbol].append(option_data)
            self.available_expiries.add(expiry)
            self.available_strikes[base_symbol].add(strike)
        
        logger.info(f"📈 Indexed {options_count} options contracts")
        logger.info(f"🗓️  Available expiries: {sorted(self.available_expiries)}")
    
    def get_chain_for_symbol(
        self,
        base_symbol: str,
        expiry: Optional[str] = None,
        strike: Optional[float] = None
    ) -> List[Dict]:
        """
        Get options chain for a symbol
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE", "TCS")
            expiry: Optional expiry filter (e.g., "2025-12-25")
            strike: Optional strike filter (e.g., 1800.0)
        
        Returns:
            List of option contracts, sorted by strike then type
        
        Example:
            # Get all RELIANCE options
            chain = service.get_chain_for_symbol("RELIANCE")
            
            # Get only Dec 25 expiry
            chain = service.get_chain_for_symbol("RELIANCE", expiry="2025-12-25")
            
            # Get specific strike
            chain = service.get_chain_for_symbol("RELIANCE", strike=1800.0)
        """
        if base_symbol not in self.options_index:
            logger.warning(f"⚠️  Symbol not found: {base_symbol}")
            return []
        
        options = self.options_index[base_symbol]
        
        # Apply filters
        if expiry:
            options = [o for o in options if o["expiry"] == expiry]
        
        if strike is not None:
            options = [o for o in options if o["strike"] == strike]
        
        # Sort: by expiry, then strike, then type (CE first)
        return sorted(options, key=lambda x: (x["expiry"], x["strike"], x["type"] == "PE"))
    
    def get_available_strikes(self, base_symbol: str, expiry: Optional[str] = None) -> List[float]:
        """
        Get all available strike prices for a symbol
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE")
            expiry: Optional expiry filter
        
        Returns:
            Sorted list of strike prices
        
        Example:
            strikes = service.get_available_strikes("RELIANCE")
            # [1700.0, 1710.0, 1720.0, ..., 1900.0]
        """
        if base_symbol not in self.available_strikes:
            return []
        
        # If expiry filter requested, filter first
        if expiry:
            options = self.get_chain_for_symbol(base_symbol, expiry=expiry)
            strikes = set(o["strike"] for o in options)
            return sorted(strikes)
        
        return sorted(self.available_strikes[base_symbol])
    
    def get_available_expiries(self, base_symbol: Optional[str] = None) -> List[str]:
        """
        Get all available expiry dates
        
        Args:
            base_symbol: Optional - if provided, only expiries for that symbol
        
        Returns:
            Sorted list of expiry dates (ISO format YYYY-MM-DD)
        
        Example:
            expiries = service.get_available_expiries("RELIANCE")
            # ["2025-12-25", "2026-01-22", "2026-02-26"]
        """
        if base_symbol:
            if base_symbol not in self.options_index:
                return []
            
            options = self.options_index[base_symbol]
            expiries = set(o["expiry"] for o in options)
            return sorted(expiries)
        
        return sorted(self.available_expiries)
    
    def get_contract_by_symbol(self, tradingsymbol: str) -> Optional[Dict]:
        """
        Get a specific option contract by trading symbol
        
        Args:
            tradingsymbol: Full trading symbol (e.g., "RELIANCE25D18000CE")
        
        Returns:
            Option contract details or None
        
        Example:
            contract = service.get_contract_by_symbol("RELIANCE25D18000CE")
        """
        # Search through all symbols
        for base_symbol, options in self.options_index.items():
            for option in options:
                if option["tradingsymbol"] == tradingsymbol:
                    return option
        
        return None
    
    def get_atm_chain(
        self,
        base_symbol: str,
        current_price: float,
        expiry: Optional[str] = None,
        num_strikes: int = 5
    ) -> List[Dict]:
        """
        Get ATM (at-the-money) options chain around a price
        
        Args:
            base_symbol: Base symbol
            current_price: Current stock price
            expiry: Optional expiry filter
            num_strikes: Number of strikes above and below ATM
        
        Returns:
            Options chain centered around ATM
        
        Example:
            # Get ±5 strikes around 1800
            chain = service.get_atm_chain("RELIANCE", 1800.0)
        """
        strikes = self.get_available_strikes(base_symbol, expiry)
        
        if not strikes:
            return []
        
        # Find closest strike to current price
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))
        atm_index = strikes.index(atm_strike)
        
        # Get nearby strikes
        start_index = max(0, atm_index - num_strikes)
        end_index = min(len(strikes), atm_index + num_strikes + 1)
        nearby_strikes = strikes[start_index:end_index]
        
        # Get all options for these strikes
        all_options = []
        for strike in nearby_strikes:
            options = self.get_chain_for_symbol(base_symbol, expiry=expiry, strike=strike)
            all_options.extend(options)
        
        return all_options
    
    def get_stats(self) -> Dict:
        """Get statistics about the options index"""
        total_options = sum(len(opts) for opts in self.options_index.values())
        
        return {
            "initialized": self.is_initialized,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "total_base_symbols": len(self.options_index),
            "total_option_contracts": total_options,
            "total_expiries": len(self.available_expiries),
            "available_expiries": sorted(self.available_expiries),
        }


# Global instance
options_service = OptionsChainService()


async def initialize_options_service() -> bool:
    """Initialize options service at application startup"""
    return await options_service.initialize()


def get_options_service() -> OptionsChainService:
    """Get the options service instance"""
    return options_service
