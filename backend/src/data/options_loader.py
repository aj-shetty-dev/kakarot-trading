"""
Options Loader Service
Fetches options chains from Upstox at app startup
Filters to ATM ± 1 strike and stores in database for WebSocket subscription

IMPORTANT: Uses ISIN mapping for correct Upstox API calls
- Symbol names (e.g., "RELIANCE") are mapped to ISINs
- API calls use NSE_EQ|{ISIN} format (e.g., "NSE_EQ|INE002A01018")

API VERSIONS:
- v3 API: Used for LTP (batch mode supported) 
- Master Instruments File: Contains ALL option contracts (no API call per symbol)

OPTIMIZATION (v2 - BATCH ALL):
1. LTP: v3 API with comma-separated keys (208 symbols in 2-3 API calls)
2. Option Contracts: Master instruments file download (ALL contracts in 1 download)
   - Replaces 208 individual API calls with 1 file download
   - File URL: https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz
   - Contains ~32,000 FNO options with instrument_key, strike, expiry, lot_size
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
import httpx
import gzip
import json
from sqlalchemy.orm import Session

from ..config.logging import logger
from ..config.settings import settings
from .models import Symbol, SubscribedOption
from .database import SessionLocal
from .isin_mapping_hardcoded import get_instrument_key, validate_symbol, ISIN_MAPPING
from ..config.timezone import ist_now

# Maximum symbols per batch API call (safe limit to avoid URL length issues)
BATCH_SIZE = 100

# Upstox Master Instruments File URL (contains ALL option contracts)
NSE_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


class OptionsLoaderService:
    """Service to load options chains from Upstox and filter for subscription
    
    OPTIMIZATION: Uses master instruments file instead of individual API calls
    - Downloads NSE.json.gz once (contains ~32,000 FNO options)
    - Replaces 208 individual /option/contract API calls with 1 file download
    """
    
    def __init__(self):
        self.api_base_url_v3 = "https://api.upstox.com/v3"  # v3 for LTP (batch support)
        self.loaded_count = 0
        self.failed_symbols = []
        # Cache for master instruments file (all FNO options)
        self._all_fno_options: Dict[str, List[Dict]] = {}  # symbol -> contracts

    @property
    def headers(self):
        """Dynamic headers to ensure we always use the latest token from settings"""
        return {
            "Authorization": f"Bearer {settings.upstox_access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    
    async def fetch_all_option_contracts_from_master(self) -> Dict[str, List[Dict]]:
        """
        Download master instruments file and extract ALL FNO option contracts
        
        OPTIMIZATION: This replaces 208 individual API calls with 1 file download!
        
        The master file (NSE.json.gz) contains:
        - ~67,000 total instruments
        - ~32,000 FNO options (CE/PE)
        - All fields we need: instrument_key, strike_price, expiry, trading_symbol, lot_size
        
        Returns:
            Dict mapping underlying_symbol -> list of option contracts
            e.g., {"RELIANCE": [{...}, {...}], "INFY": [{...}], ...}
        """
        if self._all_fno_options:
            logger.debug("📋 Using cached FNO options from master file")
            return self._all_fno_options
        
        try:
            logger.info("📥 Downloading master instruments file (NSE.json.gz)...")
            
            # Retry logic for master file download
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                        response = await client.get(NSE_INSTRUMENTS_URL)
                        
                        if response.status_code == 200:
                            # Decompress gzip
                            content = gzip.decompress(response.content)
                            instruments = json.loads(content)
                            
                            # Clear response content from memory immediately
                            del response
                            
                            logger.info(f"✅ Downloaded {len(instruments)} instruments ({len(content)/1024/1024:.2f} MB)")
                            break
                        else:
                            logger.warning(f"⚠️ Attempt {attempt+1} failed: HTTP {response.status_code}")
                            if attempt == max_retries - 1:
                                return {}
                except (httpx.RequestError, gzip.BadGzipFile, json.JSONDecodeError) as e:
                    logger.warning(f"⚠️ Attempt {attempt+1} failed with error: {e}")
                    if attempt == max_retries - 1:
                        logger.error("❌ All attempts to download/process master file failed")
                        return {}
                    import asyncio
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
            
            # Filter to FNO options only (NSE_FO segment, CE/PE types)
            fno_options = [
                i for i in instruments 
                if i.get('segment') == 'NSE_FO' and i.get('instrument_type') in ['CE', 'PE']
            ]
            
            # Clear full instruments list to save memory
            del instruments
            
            logger.info(f"📊 Found {len(fno_options)} FNO options (CE/PE)")
            
            # Group by underlying symbol
            by_symbol: Dict[str, List[Dict]] = {}
            for opt in fno_options:
                symbol = opt.get('underlying_symbol') or opt.get('name', '').split()[0]
                if symbol:
                    if symbol not in by_symbol:
                        by_symbol[symbol] = []
                    
                    # Convert expiry from timestamp (ms) to date string
                    expiry_ts = opt.get('expiry')
                    expiry_date = None
                    if expiry_ts:
                        try:
                            # Upstox uses milliseconds timestamp
                            expiry_date = datetime.fromtimestamp(expiry_ts / 1000).strftime('%Y-%m-%d')
                        except:
                            expiry_date = str(expiry_ts)
                    
                    by_symbol[symbol].append({
                        'trading_symbol': opt.get('trading_symbol'),
                        'instrument_key': opt.get('instrument_key'),
                        'strike_price': opt.get('strike_price'),
                        'instrument_type': opt.get('instrument_type'),  # CE or PE
                        'expiry': expiry_date,
                        'lot_size': opt.get('lot_size'),
                        'exchange_token': opt.get('exchange_token'),
                    })
            
            logger.info(f"📊 Grouped options for {len(by_symbol)} underlying symbols")
            
            # Cache the result
            self._all_fno_options = by_symbol
            return by_symbol
                
        except Exception as e:
            logger.error(f"❌ Error downloading master instruments: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}
    
    async def fetch_option_contracts(self, symbol: str) -> List[Dict]:
        """
        Fetch all option contracts for a symbol from Upstox v2 API
        
        NOTE: Option Contracts API is only available in v2 (v3 returns 404)
        
        Args:
            symbol: Base symbol (e.g., "RELIANCE")
        
        Returns:
            List of option contract dicts with keys:
            - trading_symbol: "RELIANCE 1570 CE 30 DEC 25"
            - instrument_key: "NSE_FO|135476"
            - strike_price: 1570.0
            - instrument_type: "CE" or "PE"
            - expiry: "2025-12-30"
            - lot_size: 500
        """
        try:
            instrument_key = get_instrument_key(symbol)
            if not instrument_key:
                logger.warning(f"⚠️  No ISIN mapping for {symbol}")
                return []
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url_v2}/option/contract",
                    params={"instrument_key": instrument_key},
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        contracts = data.get("data", [])
                        logger.debug(f"✅ {symbol}: Got {len(contracts)} option contracts")
                        return contracts
                
                logger.warning(f"⚠️  Option contracts API failed for {symbol}: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.warning(f"⚠️  Error fetching option contracts for {symbol}: {e}")
            return []
    
    def find_atm_options(
        self, 
        spot_price: float, 
        contracts: List[Dict]
    ) -> Dict[str, Optional[Dict]]:
        """
        Find ATM and first OTM CE/PE options from contracts list
        
        Selection Logic:
        - ATM CE: Call at strike nearest to spot price
        - ATM PE: Put at strike nearest to spot price
        - OTM CE: Call at first strike ABOVE ATM strike (out-of-the-money call)
        - OTM PE: Put at first strike BELOW ATM strike (out-of-the-money put)
        
        Args:
            spot_price: Current spot price of underlying
            contracts: List of option contracts from API
        
        Returns:
            Dict with keys: 'atm_ce', 'atm_pe', 'otm_ce', 'otm_pe' (values are contract dicts or None)
        """
        result = {'atm_ce': None, 'atm_pe': None, 'otm_ce': None, 'otm_pe': None}
        
        if not contracts:
            return result
        
        # Get nearest expiry
        expiries = sorted(set(c.get('expiry') for c in contracts if c.get('expiry')))
        if not expiries:
            return result
        
        nearest_expiry = expiries[0]
        
        # Filter to nearest expiry only
        nearest_contracts = [c for c in contracts if c.get('expiry') == nearest_expiry]
        
        # Separate CE and PE
        ce_contracts = [c for c in nearest_contracts if c.get('instrument_type') == 'CE']
        pe_contracts = [c for c in nearest_contracts if c.get('instrument_type') == 'PE']
        
        # Get strikes for each option type (CE and PE may have different strikes!)
        ce_strikes = sorted(set(c.get('strike_price') for c in ce_contracts if c.get('strike_price')))
        pe_strikes = sorted(set(c.get('strike_price') for c in pe_contracts if c.get('strike_price')))
        
        if not ce_strikes and not pe_strikes:
            return result['atm_ce'], result['atm_pe'], result.get('otm_ce'), result.get('otm_pe')
        
        # Find ATM strike for CE (closest to spot from CE strikes)
        atm_ce_strike = min(ce_strikes, key=lambda x: abs(x - spot_price)) if ce_strikes else None
        
        # Find ATM strike for PE (closest to spot from PE strikes)
        atm_pe_strike = min(pe_strikes, key=lambda x: abs(x - spot_price)) if pe_strikes else None
        
        # Find OTM CE strike (first strike ABOVE ATM from CE strikes)
        if atm_ce_strike:
            ce_strikes_above_atm = [s for s in ce_strikes if s > atm_ce_strike]
            otm_ce_strike = ce_strikes_above_atm[0] if ce_strikes_above_atm else None
        else:
            otm_ce_strike = None
        
        # Find OTM PE strike (first strike BELOW ATM from PE strikes)
        if atm_pe_strike:
            pe_strikes_below_atm = [s for s in pe_strikes if s < atm_pe_strike]
            otm_pe_strike = pe_strikes_below_atm[-1] if pe_strikes_below_atm else None  # Last one (closest to ATM)
        else:
            otm_pe_strike = None
        
        # Find ATM contracts
        result['atm_ce'] = next((c for c in ce_contracts if c.get('strike_price') == atm_ce_strike), None)
        result['atm_pe'] = next((c for c in pe_contracts if c.get('strike_price') == atm_pe_strike), None)
        
        # Find OTM contracts
        if otm_ce_strike:
            result['otm_ce'] = next((c for c in ce_contracts if c.get('strike_price') == otm_ce_strike), None)
        if otm_pe_strike:
            result['otm_pe'] = next((c for c in pe_contracts if c.get('strike_price') == otm_pe_strike), None)
        
        return result['atm_ce'], result['atm_pe'], result.get('otm_ce'), result.get('otm_pe')
    
    async def fetch_spot_prices_batch(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch spot prices for multiple symbols in ONE API call (batch mode)
        Uses v3 API which supports comma-separated instrument_key parameter
        
        OPTIMIZATION: Instead of 208 API calls, this fetches all LTPs in 1-2 calls
        
        Args:
            symbols: List of symbol names (e.g., ["RELIANCE", "INFY", "TCS"])
        
        Returns:
            Dict mapping symbol -> spot_price (e.g., {"RELIANCE": 1567.5, "INFY": 1560.1})
        """
        results = {}
        
        # Filter to valid symbols only and build instrument keys
        valid_symbols = []
        symbol_to_key = {}
        
        for symbol in symbols:
            if validate_symbol(symbol):
                instrument_key = get_instrument_key(symbol)
                if instrument_key:
                    valid_symbols.append(symbol)
                    symbol_to_key[symbol] = instrument_key
        
        if not valid_symbols:
            logger.warning("⚠️  No valid symbols for batch LTP fetch")
            return results
        
        # Process in batches
        for batch_start in range(0, len(valid_symbols), BATCH_SIZE):
            batch_symbols = valid_symbols[batch_start:batch_start + BATCH_SIZE]
            batch_keys = [symbol_to_key[s] for s in batch_symbols]
            
            # Create comma-separated instrument_key string
            comma_separated_keys = ','.join(batch_keys)
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{self.api_base_url_v3}/market-quote/ltp",  # v3 for LTP
                        params={"instrument_key": comma_separated_keys},
                        headers=self.headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success" and "data" in data:
                            payload = data["data"]
                            
                            # Map response back to symbols
                            # Response keys are like "NSE_EQ:RELIANCE"
                            for key, val in payload.items():
                                if "last_price" in val:
                                    if ":" in key:
                                        resp_symbol = key.split(":")[1]
                                        results[resp_symbol] = float(val["last_price"])
                            
                            logger.info(f"✅ Batch LTP fetch (v3): Got {len(payload)} prices (batch {batch_start//BATCH_SIZE + 1})")
                    else:
                        logger.warning(f"⚠️  Batch LTP API returned {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"⚠️  Batch LTP fetch error: {e}")
        
        return results
    
    async def fetch_spot_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current spot price (LTP) for a single symbol using v3 API
        
        NOTE: For batch operations, use fetch_spot_prices_batch() instead
        
        Args:
            symbol: Base symbol (e.g., "RELIANCE")
        
        Returns:
            Spot price or None if failed
        """
        try:
            if not validate_symbol(symbol):
                logger.warning(f"⚠️  Invalid FNO symbol: {symbol}")
                return None
            
            instrument_key = get_instrument_key(symbol)
            if not instrument_key:
                logger.warning(f"⚠️  No ISIN mapping for {symbol}")
                return None
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base_url_v3}/market-quote/ltp",  # v3 for LTP
                    params={"instrument_key": instrument_key},
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" and "data" in data:
                        for key, val in data["data"].items():
                            if "last_price" in val:
                                return float(val["last_price"])
                
                logger.warning(f"⚠️  No LTP data for {symbol}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️  Error fetching LTP for {symbol}: {e}")
            return None
    
    async def load_and_store_options(self, db: Session) -> int:
        """
        Main method: Load REAL options for all symbols and store ATM contracts
        
        OPTIMIZED PROCESS (v2 - BATCH ALL):
        1. Download master instruments file ONCE (contains ALL FNO options)
        2. Fetch ALL spot prices in ONE batch API call (v3 API)
        3. For each symbol, find ATM contracts from master file (NO API call!)
        4. Store in SubscribedOption table with REAL instrument keys
        
        API CALLS: 
        - Before: 208 (option contracts) + 3 (LTP) = 211 API calls
        - After:  1 (master file) + 3 (LTP) = 4 API calls
        - Reduction: 98% fewer API calls!
        
        Args:
            db: Database session
        
        Returns:
            Number of options loaded
        """
        try:
            logger.info("🔄 Starting options loader at app startup...")
            logger.info("📊 OPTIMIZATION: Using master instruments file (1 download for ALL options)")
            
            # Get all symbols with options
            symbols = db.query(Symbol).filter(Symbol.has_options == True).all()
            logger.info(f"📊 Found {len(symbols)} symbols with options")
            
            # Clear previous subscriptions
            db.query(SubscribedOption).delete()
            db.commit()
            logger.info("🗑️  Cleared previous subscribed options")
            
            self.loaded_count = 0
            self.failed_symbols = []
            
            # STEP 1: Download master instruments file (ALL options in ONE download!)
            logger.info("🚀 STEP 1: Downloading master instruments file...")
            all_options_by_symbol = await self.fetch_all_option_contracts_from_master()
            
            if not all_options_by_symbol:
                logger.error("❌ Failed to load master instruments file, falling back to API calls")
                # Fallback to individual API calls (slow but works)
                return await self._load_options_via_api_fallback(db, symbols)
            
            logger.info(f"✅ Master file loaded: {len(all_options_by_symbol)} symbols with options")
            
            # STEP 2: Fetch ALL spot prices in ONE batch API call (v3)
            symbol_names = [s.symbol for s in symbols]
            logger.info(f"🚀 STEP 2: Fetching {len(symbol_names)} spot prices in BATCH mode (v3 API)...")
            
            spot_prices = await self.fetch_spot_prices_batch(symbol_names)
            logger.info(f"✅ Batch fetch complete: Got {len(spot_prices)} spot prices")
            
            # STEP 3: For each symbol, find ATM options from master file (NO API call!)
            logger.info(f"🚀 STEP 3: Finding ATM options for {len(symbols)} symbols (from cached data)...")
            
            for idx, symbol in enumerate(symbols):
                if (idx + 1) % 50 == 0:
                    logger.info(f"   [Progress] Processed {idx + 1}/{len(symbols)} symbols...")
                
                try:
                    # Get spot price
                    spot_price = spot_prices.get(symbol.symbol)
                    if not spot_price:
                        self.failed_symbols.append(f"{symbol.symbol} (no spot price)")
                        continue
                    
                    # Get option contracts from cached master file (NO API call!)
                    contracts = all_options_by_symbol.get(symbol.symbol, [])
                    if not contracts:
                        self.failed_symbols.append(f"{symbol.symbol} (no contracts in master)")
                        continue
                    
                    # Find ATM and OTM options (4 per symbol)
                    atm_ce, atm_pe, otm_ce, otm_pe = self.find_atm_options(
                        spot_price, contracts
                    )
                    
                    # Store ATM CE
                    if atm_ce:
                        ce_option = SubscribedOption(
                            symbol=symbol.symbol,
                            option_symbol=atm_ce.get('trading_symbol'),
                            option_type="CE",
                            strike_price=atm_ce.get('strike_price'),
                            spot_price_at_subscription=spot_price,
                            is_subscribed=False,
                            instrument_key=atm_ce.get('instrument_key'),
                            is_otm=False,  # ATM
                        )
                        db.add(ce_option)
                        self.loaded_count += 1
                    
                    # Store ATM PE
                    if atm_pe:
                        pe_option = SubscribedOption(
                            symbol=symbol.symbol,
                            option_symbol=atm_pe.get('trading_symbol'),
                            option_type="PE",
                            strike_price=atm_pe.get('strike_price'),
                            spot_price_at_subscription=spot_price,
                            is_subscribed=False,
                            instrument_key=atm_pe.get('instrument_key'),
                            is_otm=False,  # ATM
                        )
                        db.add(pe_option)
                        self.loaded_count += 1
                    
                    # Store OTM CE (first strike ABOVE spot price)
                    if otm_ce:
                        otm_ce_option = SubscribedOption(
                            symbol=symbol.symbol,
                            option_symbol=otm_ce.get('trading_symbol'),
                            option_type="CE",
                            strike_price=otm_ce.get('strike_price'),
                            spot_price_at_subscription=spot_price,
                            is_subscribed=False,
                            instrument_key=otm_ce.get('instrument_key'),
                            is_otm=True,  # OTM
                        )
                        db.add(otm_ce_option)
                        self.loaded_count += 1
                    
                    # Store OTM PE (first strike BELOW spot price)
                    if otm_pe:
                        otm_pe_option = SubscribedOption(
                            symbol=symbol.symbol,
                            option_symbol=otm_pe.get('trading_symbol'),
                            option_type="PE",
                            strike_price=otm_pe.get('strike_price'),
                            spot_price_at_subscription=spot_price,
                            is_subscribed=False,
                            instrument_key=otm_pe.get('instrument_key'),
                            is_otm=True,  # OTM
                        )
                        db.add(otm_pe_option)
                        self.loaded_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️  Error processing {symbol.symbol}: {e}")
                    self.failed_symbols.append(f"{symbol.symbol} ({str(e)[:50]})")
                    continue
            
            # Commit all changes
            db.commit()
            
            logger.info(f"✅ Options loader complete!")
            logger.info(f"   Loaded: {self.loaded_count} options (REAL contracts from master file)")
            logger.info(f"   Failed: {len(self.failed_symbols)} symbols")
            logger.info(f"   API calls: 1 (master file) + 3 (LTP batches) = 4 total")
            
            if self.failed_symbols[:5]:
                logger.info(f"   First failures: {', '.join(self.failed_symbols[:5])}")
            
            # Export to file for review
            await self._export_options_to_file(db)
            
            return self.loaded_count
            
        except Exception as e:
            logger.error(f"❌ Error in options loader: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.rollback()
            raise
    
    async def _export_options_to_file(self, db: Session) -> None:
        """
        Export selected options to JSON file for review
        
        Creates: {settings.log_dir}/{YYYY-MM-DD}/selected_options.json
        Contains all 832 ATM+OTM options with full details (4 per symbol)
        """
        try:
            from pathlib import Path
            
            # Get all subscribed options from DB
            options = db.query(SubscribedOption).order_by(
                SubscribedOption.symbol, 
                SubscribedOption.option_type,
                SubscribedOption.is_otm
            ).all()
            
            # Build export data with detailed ATM/OTM breakdown
            atm_ce = [o for o in options if o.option_type == "CE" and not o.is_otm]
            atm_pe = [o for o in options if o.option_type == "PE" and not o.is_otm]
            otm_ce = [o for o in options if o.option_type == "CE" and o.is_otm]
            otm_pe = [o for o in options if o.option_type == "PE" and o.is_otm]
            
            export_data = {
                "generated_at": ist_now().isoformat(),
                "total_options": len(options),
                "unique_symbols": len(set(o.symbol for o in options)),
                "summary": {
                    "atm_ce_count": len(atm_ce),
                    "atm_pe_count": len(atm_pe),
                    "otm_ce_count": len(otm_ce),
                    "otm_pe_count": len(otm_pe),
                    "total_atm": len(atm_ce) + len(atm_pe),
                    "total_otm": len(otm_ce) + len(otm_pe),
                },
                "options": []
            }
            
            for opt in options:
                export_data["options"].append({
                    "symbol": opt.symbol,
                    "option_symbol": opt.option_symbol,
                    "option_type": opt.option_type,
                    "strike_price": opt.strike_price,
                    "spot_price": opt.spot_price_at_subscription,
                    "instrument_key": opt.instrument_key,
                    "is_otm": opt.is_otm,
                })
            
            # Write to file
            base_log_dir = Path(settings.log_dir)
            
            # Create daily log directory with subdirectories
            date_str = ist_now().strftime("%Y-%m-%d")
            daily_log_dir = base_log_dir / date_str
            system_dir = daily_log_dir / "system"
            system_dir.mkdir(parents=True, exist_ok=True)
            
            # Dated file inside the system folder
            dated_file = system_dir / "selected_options.json"
            
            with open(dated_file, "w") as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"📄 Exported {len(options)} options to {dated_file}")
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to export options to file: {e}")
    
    async def _load_options_via_api_fallback(self, db: Session, symbols: List[Symbol]) -> int:
        """Fallback method: Load options via individual API calls (slower)"""
        logger.warning("⚠️  Using fallback: individual API calls for option contracts")
        
        symbol_names = [s.symbol for s in symbols]
        spot_prices = await self.fetch_spot_prices_batch(symbol_names)
        
        for idx, symbol in enumerate(symbols):
            if (idx + 1) % 20 == 0:
                logger.info(f"   [Progress] Processed {idx + 1}/{len(symbols)} symbols...")
            
            try:
                spot_price = spot_prices.get(symbol.symbol)
                if not spot_price:
                    continue
                
                contracts = await self.fetch_option_contracts(symbol.symbol)
                if not contracts:
                    continue
                
                atm_ce, atm_pe, atm_plus_one_ce, atm_plus_one_pe = self.find_atm_options(
                    spot_price, contracts
                )
                
                for opt in [atm_ce, atm_pe, atm_plus_one_ce, atm_plus_one_pe]:
                    if opt:
                        db.add(SubscribedOption(
                            symbol=symbol.symbol,
                            option_symbol=opt.get('trading_symbol'),
                            option_type=opt.get('instrument_type'),
                            strike_price=opt.get('strike_price'),
                            spot_price_at_subscription=spot_price,
                            is_subscribed=False,
                            instrument_key=opt.get('instrument_key'),
                        ))
                        self.loaded_count += 1
                        
            except Exception as e:
                logger.warning(f"⚠️  Error processing {symbol.symbol}: {e}")
                continue
        
        db.commit()
        return self.loaded_count


# Global instance
options_loader = OptionsLoaderService()


async def load_options_at_startup() -> int:
    """
    Load options at application startup
    Should be called in main.py on_event("startup")
    
    Returns:
        Number of options loaded
    """
    db = SessionLocal()
    try:
        count = await options_loader.load_and_store_options(db)
        
        # Pre-load candles for everything we just subscribed to
        from ..trading.candle_manager import candle_manager
        from ..data.models import SubscribedOption
        
        # Get all active instrument keys
        instruments = db.query(SubscribedOption.instrument_key).all()
        keys = [k[0] for k in instruments if k[0]]
        
        if keys:
            logger.info(f"📚 Pre-loading candles for {len(keys)} instruments...")
            # We do this sequentially to avoid hammering DB, but it's okay during startup
            for key in keys:
                candle_manager.load_candles_from_db(key)
        
        return count
    finally:
        db.close()
