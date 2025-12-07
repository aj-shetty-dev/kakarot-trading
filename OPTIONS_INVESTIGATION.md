# Options Chain Investigation: How to List Options for a Symbol

## Problem Statement
Given an instrument symbol (e.g., "RELIANCE", "TCS", "INFY"), how can we programmatically list all its available options (calls, puts, different strike prices, expiries)?

---

## Solution Architecture: 3 Approaches

### Approach 1: Use Upstox `/v3/instruments` Endpoint
**Status**: ✅ **Recommended** (Most reliable)

#### How It Works
Upstox has a complete instrument database that includes all options chains. The complete list is available as a JSON file.

#### File Source
- **Endpoint**: `https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz` (3.2MB)
- **Contains**: 118,052 instruments across all segments
- **Parsing Time**: ~2-3 seconds for first load, cached in memory

#### Data Structure
```json
{
  "segment": "NSE_FO",                    // Futures & Options segment
  "exchange_token": 42949408,
  "tradingsymbol": "RELIANCE23D18000CE",  // Actual trading symbol  
  "instrument_name": "CALL OPTIONS",
  "instrument_type": "CE",                // CE = Call, PE = Put, FUT = Future
  "name": "Reliance Industries Limited",  // Base name
  "expiry": "2025-12-25",                 // Expiration date
  "strike": 1800.0,                       // Strike price
  "tick_size": 0.05,
  "lot_size": 1,
  "isin": "...",
  "underlying_key": "NSE_EQ|RELIANCE"     // Links back to base symbol
}
```

#### Implementation: Extract Options Chain
```python
import gzip
import json
from typing import List, Dict

async def fetch_options_chain(base_symbol: str, expiry_date: str = None) -> List[Dict]:
    """
    Fetch all options for a given base symbol
    
    Args:
        base_symbol: e.g., "RELIANCE", "TCS", "INFY"
        expiry_date: Optional filter, e.g., "2025-12-25" (ISO format)
    
    Returns:
        List of options contracts with details
    """
    import httpx
    
    # Download complete instruments file
    url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        decompressed = gzip.decompress(response.content)
        all_instruments = json.loads(decompressed)
    
    # Filter for this symbol's options
    options = []
    for instrument in all_instruments:
        # Check if this is an option for our symbol
        name = instrument.get("name", "")
        sym = instrument.get("tradingsymbol", "")
        
        # Match base symbol in the name
        if base_symbol in sym and instrument.get("instrument_type") in ["CE", "PE"]:
            # Optional: filter by expiry
            if expiry_date and instrument.get("expiry") != expiry_date:
                continue
            
            options.append({
                "symbol": sym,                    # e.g., "RELIANCE23D18000CE"
                "type": instrument["instrument_type"],  # "CE" or "PE"
                "strike": instrument["strike"],
                "expiry": instrument["expiry"],
                "lot_size": instrument["lot_size"],
                "tick_size": instrument["tick_size"],
                "exchange_token": instrument["exchange_token"],
                "underlying": base_symbol,
            })
    
    return sorted(options, key=lambda x: (x["expiry"], x["strike"]))
```

#### Example Output
```python
# await fetch_options_chain("RELIANCE", "2025-12-25")

[
  {
    "symbol": "RELIANCE25D18000CE",
    "type": "CE",
    "strike": 1800.0,
    "expiry": "2025-12-25",
    "lot_size": 1,
    "tick_size": 0.05,
    "exchange_token": 42949408,
    "underlying": "RELIANCE"
  },
  {
    "symbol": "RELIANCE25D18000PE",
    "type": "PE",
    "strike": 1800.0,
    "expiry": "2025-12-25",
    "lot_size": 1,
    "tick_size": 0.05,
    "exchange_token": 42949409,
    "underlying": "RELIANCE"
  },
  # ... more strikes
]
```

#### Advantages
✅ Complete data (all NSE options)  
✅ No API rate limits  
✅ Can be cached locally  
✅ Includes all metadata (lot_size, tick_size, expiry)  
✅ Fast (<3s for initial load)  

#### Disadvantages
❌ 3.2MB file download needed  
❌ Need to filter and parse 118K+ instruments  
❌ File updated daily ~6 AM IST  

---

### Approach 2: Build In-Memory Options Index
**Status**: ✅ **Recommended** (Performance optimized)

Instead of parsing the JSON every time, build an indexed lookup table at startup.

#### Implementation
```python
from typing import Dict, List, Set
import gzip
import json
from ..config.logging import logger

class OptionsChainIndex:
    """Build and maintain an indexed options chain"""
    
    def __init__(self):
        self.index: Dict[str, List[Dict]] = {}  # base_symbol -> list of options
        self.expiries: Set[str] = set()          # all available expiries
        self.strikes_by_symbol: Dict[str, Set[float]] = {}  # symbol -> set of strikes
    
    async def build_index(self):
        """Build the index from Upstox JSON"""
        import httpx
        
        logger.info("Building options chain index...")
        
        url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
            data = json.loads(gzip.decompress(response.content))
        
        for instrument in data:
            if instrument.get("instrument_type") not in ["CE", "PE"]:
                continue
            
            # Extract base symbol from trading symbol
            # e.g., "RELIANCE25D18000CE" -> "RELIANCE"
            sym = instrument["tradingsymbol"]
            
            # Heuristic: base symbol is usually first word of name
            base = instrument["name"].split()[0]
            
            if base not in self.index:
                self.index[base] = []
                self.strikes_by_symbol[base] = set()
            
            option_data = {
                "tradingsymbol": sym,
                "type": instrument["instrument_type"],
                "strike": instrument["strike"],
                "expiry": instrument["expiry"],
                "lot_size": instrument["lot_size"],
                "exchange_token": instrument["exchange_token"],
            }
            
            self.index[base].append(option_data)
            self.expiries.add(instrument["expiry"])
            self.strikes_by_symbol[base].add(instrument["strike"])
        
        logger.info(f"✅ Index built: {len(self.index)} base symbols, {len(self.expiries)} expiries")
    
    def get_options_chain(self, base_symbol: str, expiry: str = None) -> List[Dict]:
        """Get options chain for a symbol, optionally filtered by expiry"""
        options = self.index.get(base_symbol, [])
        
        if expiry:
            options = [o for o in options if o["expiry"] == expiry]
        
        # Sort by strike, then by type (CE first)
        return sorted(options, key=lambda x: (x["strike"], x["type"] == "PE"))
    
    def get_strikes(self, base_symbol: str) -> List[float]:
        """Get all available strike prices for a symbol"""
        return sorted(self.strikes_by_symbol.get(base_symbol, []))
    
    def get_expiries(self) -> List[str]:
        """Get all available expiry dates"""
        return sorted(self.expiries)

# Global instance
options_index = OptionsChainIndex()

async def initialize_options_index():
    """Initialize at application startup"""
    await options_index.build_index()
```

#### Usage
```python
# At app startup
await initialize_options_index()

# Later, when user requests options
chain = options_index.get_options_chain("RELIANCE", expiry="2025-12-25")
strikes = options_index.get_strikes("RELIANCE")
expiries = options_index.get_expiries()
```

#### Advantages
✅ O(1) lookup time after build  
✅ Can filter by expiry instantly  
✅ Get all strikes quickly  
✅ Memory efficient with indexed structure  

#### Disadvantages
❌ Requires rebuild daily (or periodic refresh)  
❌ Memory usage for 50K+ options in RAM  

---

### Approach 3: Use Upstox Market Quote API (Real-time)
**Status**: ⚠️ **Alternative** (Rate-limited, requires auth)

For specific requests, could use REST API endpoints if available.

#### Challenges
- Upstox `/v3/instruments` endpoint returns 404 (UDAPI100060)
- Market Quote API requires authentication
- Rate-limited to ~600 calls/minute
- Not suitable for bulk options listing

#### Possible Implementation
```python
async def get_options_from_api(base_symbol: str, access_token: str) -> List[Dict]:
    """
    Try using Upstox API (if available)
    
    Endpoint: https://api.upstox.com/v3/market-quote/instruments
    Requires: Bearer token authentication
    """
    import httpx
    
    url = "https://api.upstox.com/v3/market-quote/instruments"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "mode": "ltp",
        "filter": f"symbol:{base_symbol}.*"  # Hypothetical
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API Error: {response.status_code}")
                return []
    except Exception as e:
        logger.error(f"Failed to fetch options: {e}")
        return []
```

**Status**: Currently returns 404, not recommended.

---

## Recommended Implementation

### Step 1: Create Options Service
```python
# backend/src/data/options_service.py

from typing import List, Dict, Optional
from ..config.logging import logger

class OptionsChainService:
    """Service to fetch and manage options chains"""
    
    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}
        self._last_update = None
    
    async def get_chain_for_symbol(
        self, 
        base_symbol: str, 
        expiry: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all options for a given symbol
        
        Args:
            base_symbol: e.g., "RELIANCE"
            expiry: Optional filter for expiry date, e.g., "2025-12-25"
        
        Returns:
            List of options contracts
        
        Example:
            chain = await service.get_chain_for_symbol("RELIANCE")
            # Returns all RELIANCE options across all expirations
            
            chain = await service.get_chain_for_symbol("RELIANCE", "2025-12-25")
            # Returns only Dec 25 expiry options
        """
        pass
    
    async def get_available_strikes(self, base_symbol: str) -> List[float]:
        """Get all available strike prices for a symbol"""
        pass
    
    async def get_available_expiries(self, base_symbol: str) -> List[str]:
        """Get all available expiry dates for a symbol"""
        pass
```

### Step 2: Create REST Endpoint
```python
# backend/src/api/routes/options.py

from fastapi import APIRouter, Query, HTTPException
from ..data.options_service import OptionsChainService

router = APIRouter(prefix="/api/v1/options", tags=["options"])
service = OptionsChainService()

@router.get("/chain/{symbol}")
async def get_options_chain(
    symbol: str,
    expiry: str = Query(None, description="Optional expiry date (YYYY-MM-DD)")
):
    """
    Get options chain for a symbol
    
    Example:
        GET /api/v1/options/chain/RELIANCE
        GET /api/v1/options/chain/RELIANCE?expiry=2025-12-25
    
    Returns:
        {
            "symbol": "RELIANCE",
            "options": [
                {
                    "symbol": "RELIANCE25D18000CE",
                    "type": "CE",
                    "strike": 1800.0,
                    "expiry": "2025-12-25",
                    ...
                }
            ]
        }
    """
    try:
        chain = await service.get_chain_for_symbol(symbol, expiry)
        return {"symbol": symbol, "expiry": expiry, "options": chain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strikes/{symbol}")
async def get_strikes(symbol: str):
    """Get all available strike prices for a symbol"""
    strikes = await service.get_available_strikes(symbol)
    return {"symbol": symbol, "strikes": strikes}

@router.get("/expiries/{symbol}")
async def get_expiries(symbol: str):
    """Get all available expiry dates for a symbol"""
    expiries = await service.get_available_expiries(symbol)
    return {"symbol": symbol, "expiries": expiries}
```

### Step 3: Add to WebSocket Stream
```python
# Subscribe to specific options
await ws_client.subscribe([
    "NSE_FO|RELIANCE25D18000CE",  # RELIANCE 1800 Call
    "NSE_FO|RELIANCE25D18000PE",  # RELIANCE 1800 Put
])
```

---

## Data Model Updates

```python
# backend/src/data/models.py

class OptionContract(Base):
    """Represents a single options contract"""
    __tablename__ = "option_contracts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identifiers
    tradingsymbol = Column(String(30), unique=True, nullable=False, index=True)
    exchange_token = Column(Integer, unique=True)
    
    # Contract Details
    base_symbol = Column(String(20), nullable=False, index=True)  # e.g., "RELIANCE"
    contract_type = Column(String(5), nullable=False)             # "CE" or "PE"
    strike_price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False)
    lot_size = Column(Integer)
    tick_size = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_base_expiry_strike", "base_symbol", "expiry_date", "strike_price"),
    )

class OptionsTick(Base):
    """Real-time tick data for options"""
    __tablename__ = "options_ticks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to contract
    option_contract_id = Column(UUID(as_uuid=True), ForeignKey("option_contracts.id"))
    option_contract = relationship("OptionContract")
    
    # Price data
    last_price = Column(Float)
    bid = Column(Float)
    ask = Column(Float)
    volume = Column(Integer)
    open_interest = Column(Integer)
    
    # Greeks
    iv = Column(Float)        # Implied Volatility
    delta = Column(Float)
    gamma = Column(Float)
    theta = Column(Float)
    vega = Column(Float)
    
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
```

---

## API Usage Examples

### Example 1: Get All RELIANCE Options
```bash
curl http://localhost:8000/api/v1/options/chain/RELIANCE

Response:
{
  "symbol": "RELIANCE",
  "expiry": null,
  "options": [
    {"symbol": "RELIANCE25D17900CE", "type": "CE", "strike": 1790.0, ...},
    {"symbol": "RELIANCE25D17900PE", "type": "PE", "strike": 1790.0, ...},
    {"symbol": "RELIANCE25D18000CE", "type": "CE", "strike": 1800.0, ...},
    ...
  ]
}
```

### Example 2: Get Only Dec 25 Expiry
```bash
curl "http://localhost:8000/api/v1/options/chain/RELIANCE?expiry=2025-12-25"
```

### Example 3: Get All Strike Prices
```bash
curl http://localhost:8000/api/v1/options/chain/RELIANCE/strikes

Response:
{
  "symbol": "RELIANCE",
  "strikes": [1700.0, 1710.0, 1720.0, ..., 1900.0]
}
```

---

## Performance Considerations

| Aspect | Performance |
|--------|-------------|
| Build index from JSON | ~2-3 seconds (first load) |
| Subsequent lookups | O(1) in-memory, <1ms |
| Chain for one symbol | ~10-50ms (depends on # options) |
| Index size in RAM | ~50-100MB for all options |
| Update frequency | Daily (market closed) |
| API rate limits | None (using JSON file, not REST) |

---

## Next Steps

1. ✅ Implement `OptionsChainService` 
2. ✅ Build in-memory index at startup
3. ✅ Add REST endpoints for `/options/chain/{symbol}`
4. ✅ Create `OptionContract` and `OptionsTick` models
5. ✅ Add options to WebSocket subscriptions
6. ✅ Stream live tick data for selected options

---

## References

- **Complete Instruments File**: `https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz`
- **WebSocket Format**: `NSE_FO|{tradingsymbol}` (e.g., `NSE_FO|RELIANCE25D18000CE`)
- **Data Structure**: See `complete.json.gz` for full schema
- **Updated**: Daily ~6 AM IST

