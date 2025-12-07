"""
Options Chain Service V2 - API-Based Fetching
Fetches options chains dynamically from Upstox API instead of static JSON file.
This is more efficient and reliable than downloading the massive complete.json.gz.
"""

from typing import List, Dict, Optional, Set
from datetime import datetime, date
import httpx
from ..config.logging import logger
from ..config.settings import settings


class OptionsChainServiceV2:
    """Service to fetch options chains via Upstox API on-demand"""
    
    def __init__(self):
        self.access_token = settings.upstox_access_token  # Use JWT access token for authentication
        self.base_url = "https://api.upstox.com/v3"
        self.cached_options: Dict[str, List[Dict]] = {}  # symbol -> list of options
        self.cached_expiries: Dict[str, List[str]] = {}  # symbol -> list of expiries
        self.available_expiries_global: Set[str] = set()
        self.is_initialized = False
        self.last_updated: Optional[datetime] = None
    
    async def initialize(self) -> bool:
        """
        Initialize the options service
        In V2, we don't pre-load everything - we fetch on-demand
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("🔄 Initializing Options Service V2 (API-based)...")
            self.is_initialized = True
            self.last_updated = datetime.utcnow()
            logger.info("✅ Options Service V2 initialized (ready for on-demand fetching)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize options service V2: {e}")
            return False
    
    async def fetch_options_chain(
        self,
        base_symbol: str,
        expiry: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch options chain for a symbol from Upstox API
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE")
            expiry: Optional expiry date (ISO format or Unix timestamp)
        
        Returns:
            List of option contracts
        
        Example:
            chain = await service.fetch_options_chain("RELIANCE")
            # or with specific expiry
            chain = await service.fetch_options_chain("RELIANCE", "2025-12-25")
        """
        cache_key = f"{base_symbol}_{expiry}" if expiry else base_symbol
        
        # Check cache first
        if cache_key in self.cached_options:
            logger.debug(f"📦 Using cached options for {cache_key}")
            return self.cached_options[cache_key]
        
        try:
            logger.debug(f"🔄 Fetching options chain from API for {base_symbol}...")
            
            # Build query parameters
            params = {
                "instrument_key": f"NSE_FO|{base_symbol}",  # NSE FO format
            }
            
            if expiry:
                params["expiry"] = expiry
            
            # Call Upstox API
            # API endpoint: GET /v3/options-chain
            # Note: Adjust based on actual Upstox API documentation
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try multiple possible endpoints
                endpoints = [
                    f"{self.base_url}/options-chain",
                    f"{self.base_url}/market-data/options-chain",
                    f"{self.base_url}/instruments",  # Fallback
                ]
                
                for endpoint in endpoints:
                    try:
                        response = await client.get(endpoint, params=params, headers=headers)
                        
                        if response.status_code == 200:
                            data = response.json()
                            logger.debug(f"✅ Got options chain for {base_symbol}: {len(data)} records")
                            
                            # Parse and cache
                            options = self._parse_options_response(data)
                            self.cached_options[cache_key] = options
                            return options
                        
                        elif response.status_code == 401:
                            logger.warning(f"⚠️  Unauthorized (401) - API key may be invalid")
                            break  # Don't retry
                        
                    except Exception as e:
                        logger.debug(f"  Endpoint {endpoint} failed: {e}")
                        continue
                
                # If all endpoints fail, return empty
                logger.warning(f"⚠️  Could not fetch options for {base_symbol} from any endpoint")
                return []
            
        except Exception as e:
            logger.error(f"❌ Error fetching options for {base_symbol}: {e}")
            return []
    
    async def get_available_expiries(self, base_symbol: str) -> List[str]:
        """
        Get available expiry dates for a symbol
        
        Args:
            base_symbol: Base symbol (e.g., "RELIANCE")
        
        Returns:
            Sorted list of expiry dates
        """
        try:
            # Fetch full chain
            chain = await self.fetch_options_chain(base_symbol)
            
            if not chain:
                logger.debug(f"⚠️  No expiries found for {base_symbol}")
                return []
            
            # Extract unique expiries
            expiries = sorted(set(o.get("expiry", "") for o in chain if o.get("expiry")))
            logger.debug(f"Found {len(expiries)} expiries for {base_symbol}: {expiries[:3]}")
            return expiries
            
        except Exception as e:
            logger.error(f"❌ Error getting expiries for {base_symbol}: {e}")
            return []
    
    async def get_strikes_for_expiry(
        self,
        base_symbol: str,
        expiry: str
    ) -> List[float]:
        """
        Get all strike prices for a symbol on a specific expiry
        
        Args:
            base_symbol: Base symbol
            expiry: Expiry date
        
        Returns:
            Sorted list of strikes
        """
        try:
            chain = await self.fetch_options_chain(base_symbol, expiry)
            strikes = sorted(set(o.get("strike", 0.0) for o in chain if o.get("strike")))
            return strikes
            
        except Exception as e:
            logger.error(f"❌ Error getting strikes: {e}")
            return []
    
    async def get_option_contract(
        self,
        base_symbol: str,
        strike: float,
        option_type: str,  # "CE" or "PE"
        expiry: str
    ) -> Optional[Dict]:
        """
        Get a specific option contract
        
        Args:
            base_symbol: Base symbol
            strike: Strike price
            option_type: "CE" or "PE"
            expiry: Expiry date
        
        Returns:
            Option contract details or None
        """
        try:
            chain = await self.fetch_options_chain(base_symbol, expiry)
            
            for option in chain:
                if (option.get("strike") == strike and 
                    option.get("type") == option_type):
                    return option
            
            logger.debug(f"⚠️  Option not found: {base_symbol} {strike} {option_type} {expiry}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting option contract: {e}")
            return None
    
    def _parse_options_response(self, data: dict) -> List[Dict]:
        """
        Parse Upstox API response into standardized option format
        
        Args:
            data: Raw API response
        
        Returns:
            List of standardized option dicts
        """
        options = []
        
        # Handle different response formats
        records = data.get("records", data.get("data", []))
        
        if not isinstance(records, list):
            records = []
        
        for record in records:
            option = {
                "tradingsymbol": record.get("trading_symbol", record.get("tradingsymbol", "")),
                "exchange_token": record.get("exchange_token", ""),
                "type": record.get("option_type", record.get("type", "")),  # CE or PE
                "strike": float(record.get("strike_price", record.get("strike", 0))),
                "expiry": record.get("expiry", ""),
                "lot_size": int(record.get("lot_size", 1)),
                "tick_size": float(record.get("tick_size", 0.05)),
                "segment": record.get("segment", ""),
                "underlying_symbol": record.get("underlying_symbol", ""),
            }
            options.append(option)
        
        return options
    
    def get_stats(self) -> Dict:
        """Get statistics about the options service"""
        total_cached = sum(len(opts) for opts in self.cached_options.values())
        
        return {
            "initialized": self.is_initialized,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "cached_chains": len(self.cached_options),
            "total_cached_options": total_cached,
            "mode": "API-based (on-demand)",
        }


# Global instance
options_service_v2 = OptionsChainServiceV2()


async def initialize_options_service_v2() -> bool:
    """Initialize options service V2 at application startup"""
    return await options_service_v2.initialize()


def get_options_service_v2() -> OptionsChainServiceV2:
    """Get the options service V2 instance"""
    return options_service_v2
