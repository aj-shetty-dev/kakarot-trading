"""
Upstox V3 WebSocket Client - VERBOSE LOGGING VERSION
Handles real-time data streaming from Upstox V3 WebSocket feed

Updated to use UpstoxV3MessageParser for proper V3 message handling.

CRITICAL: V3 requires:
- Subscription messages sent as BINARY (bytes), not text
- Response data comes as binary protobuf
- Decode using MarketDataFeed.proto
"""

import asyncio
import json
import websockets
import aiohttp
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
import logging
import traceback
import time
import random
import socket

from ..config.settings import settings
from ..config.constants import (
    UPSTOX_WEBSOCKET_URL,
    WEBSOCKET_RECONNECT_DELAY,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
    WEBSOCKET_RECONNECT_JITTER,
    CONNECTION_RETRY_TIMEOUT,
    DNS_FALLBACK_SERVERS,
    DNS_TIMEOUT
)
from ..config.logging import websocket_logger as logger
from ..config.timezone import ist_now
from ..notifications.telegram import get_telegram_service
from .data_models import TickData, SubscriptionRequest, UnsubscriptionRequest
from .proto_handler import get_message_parser, UpstoxV3MessageParser


class UpstoxWebSocketClient:
    """
    Upstox V3 WebSocket client for real-time market data
    
    Connects to: wss://api.upstox.com/v3
    Handles: Subscriptions, message parsing, reconnection
    
    V3 Features:
    - Subscription requests must be sent as BINARY bytes (not text)
    - Feed responses are binary protobuf
    - Modes: ltpc (5000 keys), full (2000 keys), option_greeks (3000 keys)
    """

    def __init__(self, access_token: str, client_code: str):
        """
        Initialize WebSocket client
        
        Args:
            access_token: Upstox access token
            client_code: Upstox client code (user ID)
        """
        self.access_token = access_token
        self.client_code = client_code
        self.ws_url = UPSTOX_WEBSOCKET_URL
        self.websocket = None
        self.is_connected = False
        self.subscribed_symbols: set = set()
        self.message_handlers: List[Callable] = []
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = WEBSOCKET_MAX_RECONNECT_ATTEMPTS
        self.last_reconnect_time = 0
        self.base_reconnect_delay = WEBSOCKET_RECONNECT_DELAY
        self.network_error_count = 0
        self.max_network_errors = 10
        
        # V3 Message Parser
        self.message_parser = get_message_parser()
        
        # Telegram Service
        self.telegram = get_telegram_service(settings)
        
        # Price cache for fallback position monitoring
        self.price_cache: Dict[str, Dict[str, Any]] = {}  # {symbol: {price, timestamp}}
        self.last_cache_update_time = 0
        
        # DNS resolution tracking
        self.dns_failure_count = 0
        self.last_dns_failure_time = 0

    async def _resolve_with_fallback(self, hostname: str) -> Optional[str]:
        """
        Attempt DNS resolution with fallback DNS servers.
        
        Args:
            hostname: Hostname to resolve (e.g., 'api.upstox.com')
            
        Returns:
            str: Resolved IP address or None if all attempts fail
        """
        try:
            # Try default DNS first (system DNS)
            logger.info(f"[DNS] Attempting to resolve {hostname} with system DNS...")
            try:
                ip = socket.gethostbyname(hostname)
                logger.info(f"[DNS] ✅ Resolved {hostname} → {ip} (system DNS)")
                return ip
            except socket.gaierror as e:
                logger.warning(f"[DNS] ⚠️ System DNS failed: {e}")
                self.dns_failure_count += 1
                self.last_dns_failure_time = time.time()
            
            # Try fallback DNS servers
            logger.info("[DNS] Attempting fallback DNS servers...")
            try:
                import dns.resolver
                for dns_server in DNS_FALLBACK_SERVERS:
                    try:
                        logger.info(f"[DNS] Trying {dns_server}...")
                        resolver = dns.resolver.Resolver()
                        resolver.nameservers = [dns_server]
                        resolver.timeout = DNS_TIMEOUT
                        result = resolver.resolve(hostname, 'A')
                        ip = str(result[0])
                        logger.info(f"[DNS] ✅ Resolved {hostname} → {ip} (via {dns_server})")
                        self.dns_failure_count = 0  # Reset DNS failure count
                        return ip
                    except Exception as inner_e:
                        logger.warning(f"[DNS] {dns_server} failed: {type(inner_e).__name__}")
                        continue
            except ImportError:
                logger.warning("[DNS] dnspython not available, skipping fallback DNS")
                pass
            
            logger.error("[DNS] ❌ All DNS resolution attempts failed!")
            return None
            
        except Exception as e:
            logger.error(f"[DNS] Unexpected error in DNS resolution: {e}")
            return None
    
    async def _check_dns_health(self) -> bool:
        """
        Check if DNS is working by attempting to resolve api.upstox.com
        
        Returns:
            bool: True if DNS is healthy, False otherwise
        """
        hostname = "api.upstox.com"
        result = await self._resolve_with_fallback(hostname)
        return result is not None

    async def connect(self) -> bool:
        """
        Connect to Upstox V3 WebSocket with proper authentication and error handling.
        First gets authorization, then connects with the authorized redirect URI.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("[VERBOSE] WebSocket Connection Initiated")
        logger.info("=" * 80)
        logger.info(f"[VERBOSE] Access token length: {len(self.access_token)} chars")
        logger.info(f"[VERBOSE] Access token first 20 chars: {self.access_token[:20]}...")
        logger.info(f"[VERBOSE] Client code: {self.client_code}")
        
        try:
            # Step 1: Get authorized WebSocket URL from Upstox API
            logger.info("[VERBOSE] Step 1: Calling Upstox authorize endpoint...")
            logger.info(f"[VERBOSE] Endpoint: https://api.upstox.com/v3/feed/market-data-feed/authorize")
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            ws_uri = None
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://api.upstox.com/v3/feed/market-data-feed/authorize",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            logger.info(f"[VERBOSE] Authorization response status: {resp.status} (Attempt {attempt + 1}/{max_retries})")
                            
                            if resp.status == 200:
                                auth_data = await resp.json()
                                logger.info(f"[VERBOSE] Auth response: {str(auth_data)[:200]}")
                                
                                # Extract WebSocket URL from response
                                ws_uri = auth_data.get("data", {}).get("authorizedRedirectUri")
                                if not ws_uri:
                                    logger.error("[ERROR] No authorized redirect URI in response")
                                    self.network_error_count = 0
                                    return False
                                
                                logger.info(f"[SUCCESS] Got authorized WebSocket URI")
                                logger.info(f"[VERBOSE] WebSocket URI: {ws_uri[:80]}...")
                                break # Success!
                            elif resp.status == 401:
                                logger.error("❌ [CRITICAL] UPSTOX ACCESS TOKEN EXPIRED OR INVALID")
                                logger.error("👉 Please generate a new token and update your .env file.")
                                logger.error("👉 Run 'python3 update_token.py' in the dist folder.")
                                
                                # Send Telegram notification
                                await self.telegram.send_message(
                                    "🚨 <b>CRITICAL: Upstox Access Token Expired!</b>\n"
                                    "The WebSocket connection failed because the token is invalid or expired. "
                                    "Please update your <code>.env</code> file with a new token."
                                )
                                
                                self.network_error_count = 0 # Don't retry indefinitely for auth errors
                                return False
                            elif resp.status == 429:
                                logger.warning(f"⚠️ [WARNING] Rate limited by Upstox API (429). Waiting {retry_delay * 2}s...")
                                await asyncio.sleep(retry_delay * 2)
                                continue
                            else:
                                error_text = await resp.text()
                                logger.error(f"[ERROR] Authorization failed with status {resp.status}")
                                logger.error(f"[VERBOSE] Response: {error_text[:200]}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    continue
                                self.network_error_count += 1
                                return False
                                
                except (aiohttp.ClientConnectorError, aiohttp.ClientSSLError, asyncio.TimeoutError) as ne:
                    logger.error(f"[ERROR] Network error during authorization (Attempt {attempt + 1}): {type(ne).__name__}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2 # Exponential backoff
                        continue
                    logger.error(f"[VERBOSE] {str(ne)}")
                    self.network_error_count += 1
                    return False
            
            if not ws_uri:
                return False
            
            # Step 2: Connect to the authorized WebSocket URI
            logger.info("[VERBOSE] Step 2: Connecting to authorized WebSocket URI...")
            
            try:
                self.websocket = await asyncio.wait_for(
                    websockets.connect(
                        ws_uri,
                        ping_interval=30,
                        ping_timeout=10
                    ),
                    timeout=30
                )
                
                logger.info("[SUCCESS] WebSocket connection established!")
                logger.info(f"[VERBOSE] WebSocket object: {type(self.websocket).__name__}")
                self.network_error_count = 0  # Reset error count on success
                
                # Send Telegram notification
                await self.telegram.send_message("🔌 <b>WebSocket Connected</b>\nLive data feed is active.")
                
            except asyncio.TimeoutError:
                logger.error("[ERROR] WebSocket connection timeout")
                self.network_error_count += 1
                return False
            except websockets.exceptions.InvalidStatusCode as isc:
                logger.error("[ERROR] WebSocket connection rejected by server")
                logger.error(f"[VERBOSE] InvalidStatusCode: {isc}")
                self.network_error_count += 1
                return False
                
        except Exception as e:
            logger.error("[ERROR] WebSocket connection failed")
            logger.error(f"[VERBOSE] Exception type: {type(e).__name__}")
            logger.error(f"[VERBOSE] Exception: {str(e)}")
            logger.error(f"[TRACEBACK]\n{traceback.format_exc()}")
            self.network_error_count += 1
            return False
        
        # Success
        self.is_connected = True
        self.reconnect_attempts = 0
        logger.info("=" * 80)
        logger.info("[SUCCESS] WebSocket fully connected and authenticated!")
        logger.info("=" * 80)
        
        return True

    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket:
            try:
                await self.websocket.close()
                self.is_connected = False
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    async def subscribe(self, symbols: List[str], mode: str = "full") -> bool:
        """
        Subscribe to symbols using Upstox V3 protocol
        Upstox V3 expects subscription in format:
        {
            "guid": "unique-id",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": ["NSE_INDEX|Nifty 50"]
            }
        }
        
        Args:
            symbols: List of symbols (e.g., ["NSE_INDEX|Nifty 50"])
            mode: Subscription mode - "full", "ltpc", or "option_greeks"
        
        Returns:
            bool: True if subscription successful
        """
        if not self.is_connected:
            logger.error("Not connected. Cannot subscribe.")
            return False

        try:
            # Convert symbols to Upstox V3 format if needed
            instrument_keys = [self._symbol_to_token(symbol) for symbol in symbols]
            
            subscription_request = {
                "guid": f"sub-{'-'.join(symbols[:2])}-{len(symbols)}",
                "method": "sub",
                "data": {
                    "mode": mode,
                    "instrumentKeys": instrument_keys
                }
            }
            
            logger.info(f"[VERBOSE] Subscribing to {len(symbols)} symbols in '{mode}' mode")
            logger.debug(f"[VERBOSE] Symbols: {symbols}")
            logger.debug(f"[VERBOSE] Instrument Keys: {instrument_keys}")
            
            # CRITICAL FIX: V3 requires subscription messages as BINARY, not text
            # Convert JSON to bytes before sending
            message_bytes = json.dumps(subscription_request).encode('utf-8')
            await self.websocket.send(message_bytes)
            
            self.subscribed_symbols.update(symbols)
            logger.info(f"[SUCCESS] Subscription request sent for {len(symbols)} symbols (binary)")
            
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Subscription error: {e}")
            logger.error(f"[TRACEBACK]\n{traceback.format_exc()}")
            return False

    async def unsubscribe(self, symbols: List[str]) -> bool:
        """
        Unsubscribe from symbols using Upstox V3 protocol
        Expects format:
        {
            "guid": "unique-id",
            "method": "unsub",
            "data": {
                "instrumentKeys": ["NSE_INDEX|Nifty 50"]
            }
        }
        
        Args:
            symbols: List of symbols to unsubscribe
        
        Returns:
            bool: True if unsubscription successful
        """
        if not self.is_connected:
            logger.error("Not connected. Cannot unsubscribe.")
            return False

        try:
            # Convert symbols to Upstox V3 format if needed
            instrument_keys = [self._symbol_to_token(symbol) for symbol in symbols]
            
            unsubscription_request = {
                "guid": f"unsub-{'-'.join(symbols[:2])}-{len(symbols)}",
                "method": "unsub",
                "data": {
                    "instrumentKeys": instrument_keys
                }
            }
            
            logger.info(f"[VERBOSE] Unsubscribing from {len(symbols)} symbols")
            
            # CRITICAL FIX: V3 requires messages as BINARY, not text
            message_bytes = json.dumps(unsubscription_request).encode('utf-8')
            await self.websocket.send(message_bytes)
            
            for symbol in symbols:
                self.subscribed_symbols.discard(symbol)
            
            logger.info(f"[SUCCESS] Unsubscription request sent for {len(symbols)} symbols (binary)")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Unsubscription error: {e}")
            logger.error(f"[TRACEBACK]\n{traceback.format_exc()}")
            return False

    async def listen(self) -> None:
        """
        Listen for incoming messages from WebSocket with automatic reconnection.
        Runs in background, processes all messages and handles network failures.
        """
        try:
            while self.is_connected and self.websocket:
                try:
                    message = await self.websocket.recv()
                    
                    await self._handle_message(message)
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("[WARNING] WebSocket connection closed")
                    self.is_connected = False
                    await self.telegram.send_message("⚠️ <b>WebSocket Disconnected</b>\nAttempting to reconnect...")
                    await self._attempt_reconnect()
                    
                except (websockets.exceptions.WebSocketException, OSError) as we:
                    logger.warning(f"[WARNING] WebSocket error ({type(we).__name__}): {str(we)}")
                    self.is_connected = False
                    self.network_error_count += 1
                    await self.telegram.send_message(f"⚠️ <b>WebSocket Error:</b> <code>{type(we).__name__}</code>\nAttempting to reconnect...")
                    await self._attempt_reconnect()
                    
                except asyncio.TimeoutError:
                    logger.warning("[WARNING] WebSocket receive timeout, attempting reconnect")
                    self.is_connected = False
                    self.network_error_count += 1
                    await self.telegram.send_message("⚠️ <b>WebSocket Timeout:</b> No data received. Attempting to reconnect...")
                    await self._attempt_reconnect()
                    
                except Exception as e:
                    logger.error(f"[ERROR] Unexpected error in listen loop: {type(e).__name__} - {e}")
                    self.network_error_count += 1
                    if self.network_error_count > self.max_network_errors:
                        logger.error("[CRITICAL] Too many network errors, stopping listen loop")
                        await self.telegram.send_message("🚨 <b>CRITICAL: WebSocket Stopped!</b>\nToo many network errors. Manual intervention required.")
                        self.is_connected = False
                        break
                    
        except Exception as e:
            logger.error(f"[ERROR] Fatal error in listen: {e}")
            await self.telegram.send_message(f"🚨 <b>CRITICAL: WebSocket Fatal Error!</b>\nError: <code>{str(e)}</code>")
            self.is_connected = False

    async def _handle_message(self, message: bytes) -> None:
        """
        Handle incoming WebSocket message from Upstox V3
        Uses UpstoxV3MessageParser for proper V3 message handling.
        
        V3 Message Types:
        - market_info: First message with market status
        - live_feed: Tick data (nested under feeds -> instrument_key)
        - control: Subscription/unsubscription responses
        
        Args:
            message: Raw message bytes from WebSocket
        """
        try:
            # Log message received
            if isinstance(message, bytes):
                logger.info(f"[WEBSOCKET] Message received: {len(message)} bytes")
            
            # Use V3 message parser
            parsed = self.message_parser.parse_message(message)
            
            if not parsed:
                logger.debug(f"[VERBOSE] Could not parse message ({len(message) if isinstance(message, bytes) else 'unknown'} bytes)")
                return
            
            msg_type = parsed.get("type")
            logger.info(f"[MESSAGE HANDLER] Type: {msg_type}")
            
            # Handle market_info (first message on connect)
            if msg_type == "market_info":
                is_open = parsed.get("is_market_open", False)
                segment_status = parsed.get("segment_status", {})
                logger.info(f"[MARKET INFO] NSE_FO market open: {is_open}")
                logger.info(f"[MARKET INFO] Segment status: {segment_status}")
                return
            
            # Handle control messages (subscription responses)
            elif msg_type == "control":
                method = parsed.get("method")
                status = parsed.get("status")
                logger.info(f"[CONTROL] Method: {method}, Status: {status}")
                if status != "success":
                    logger.warning(f"[WARNING] Control message issue: {parsed}")
                return
            
            # Handle live_feed (tick data)
            elif msg_type == "live_feed":
                ticks = parsed.get("ticks", [])
                logger.info(f"[LIVE FEED] Received {len(ticks)} ticks")
                
                if not ticks:
                    return
                
                logger.debug(f"[FEED] Received {len(ticks)} ticks")
                
                for tick_data in ticks:
                    # Convert to TickData model
                    tick = self._parse_v3_tick(tick_data)
                    
                    if tick:
                        # Cache the price for fallback position monitoring
                        self._cache_price(tick.symbol, tick.last_price, tick.timestamp)
                        
                        for handler in self.message_handlers:
                            try:
                                await handler(tick)
                            except Exception as e:
                                logger.error(f"[ERROR] Error in message handler: {e}")
            else:
                logger.debug(f"[VERBOSE] Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"[ERROR] Error handling message: {e}")
            logger.debug(f"[TRACEBACK]\n{traceback.format_exc()}")

    def _parse_v3_tick(self, data: Dict[str, Any]) -> Optional[TickData]:
        """
        Parse V3 tick data (from UpstoxV3MessageParser) into TickData model
        
        V3 tick structure (from parser):
        {
            "instrument_key": "NSE_FO|60965",
            "ltp": 37.5,
            "ltt": 1725875999894,
            "ltq": 500,
            "cp": 30.9,
            "bid": 37.45,
            "ask": 37.55,
            "delta": 0.5,
            "theta": -0.02,
            ...
        }
        
        Args:
            data: Tick dict from V3 message parser
        
        Returns:
            TickData or None if parsing fails
        """
        try:
            instrument_key = data.get("instrument_key", "")
            
            tick = TickData(
                symbol=instrument_key,  # V3 uses instrument_key as identifier
                token=instrument_key,
                last_price=float(data.get("ltp", 0)),
                open_price=float(data.get("day_open", 0)),
                high_price=float(data.get("day_high", 0)),
                low_price=float(data.get("day_low", 0)),
                close_price=float(data.get("cp", 0)),  # Close/previous close
                volume=int(data.get("volume", 0)),
                oi=int(data.get("oi", 0)),
                bid=float(data.get("bid", 0)),
                ask=float(data.get("ask", 0)),
                bid_volume=int(data.get("bid_qty", 0)),
                ask_volume=int(data.get("ask_qty", 0)),
                iv=float(data.get("iv", 0)),
                delta=float(data.get("delta", 0)),
                gamma=float(data.get("gamma", 0)),
                theta=float(data.get("theta", 0)),
                vega=float(data.get("vega", 0)),
                timestamp=ist_now()
            )
            return tick
            
        except Exception as e:
            logger.error(f"Error parsing V3 tick: {e}")
            return None

    def _parse_tick(self, data: Dict[str, Any]) -> Optional[TickData]:
        """
        Parse incoming data into TickData model (legacy method)
        
        Args:
            data: Raw data from WebSocket
        
        Returns:
            TickData or None if parsing fails
        """
        try:
            tick = TickData(
                symbol=data.get("symbol", ""),
                token=data.get("tk"),
                last_price=float(data.get("ltp", 0)),
                open_price=float(data.get("o", 0)),
                high_price=float(data.get("h", 0)),
                low_price=float(data.get("l", 0)),
                close_price=float(data.get("c", 0)),
                volume=int(data.get("v", 0)),
                oi=int(data.get("oi", 0)),
                bid=float(data.get("bid", 0)),
                ask=float(data.get("ask", 0)),
                bid_volume=int(data.get("bidv", 0)),
                ask_volume=int(data.get("askv", 0)),
                iv=float(data.get("iv", 0)),
                delta=float(data.get("delta", 0)),
                gamma=float(data.get("gamma", 0)),
                theta=float(data.get("theta", 0)),
                vega=float(data.get("vega", 0)),
                timestamp=ist_now()
            )
            return tick
            
        except Exception as e:
            logger.error(f"Error parsing tick: {e}")
            return None

    def register_handler(self, handler: Callable) -> None:
        """
        Register a message handler callback
        
        Args:
            handler: Async function to call on each message
        """
        self.message_handlers.append(handler)
        logger.info(f"Registered message handler: {handler.__name__}")
    
    def _cache_price(self, symbol: str, price: float, timestamp: datetime) -> None:
        """
        Cache price for fallback position monitoring when WebSocket is down.
        
        Args:
            symbol: Symbol/instrument key
            price: Current price
            timestamp: Time of price update
        """
        self.price_cache[symbol] = {
            "price": price,
            "timestamp": timestamp,
            "time_unix": time.time()
        }
        self.last_cache_update_time = time.time()
    
    def get_cached_price(self, symbol: str) -> Optional[float]:
        """
        Get cached price for a symbol if available and not stale.
        
        Args:
            symbol: Symbol/instrument key
            
        Returns:
            float: Price if available and fresh, None otherwise
        """
        if symbol not in self.price_cache:
            return None
        
        cache_entry = self.price_cache[symbol]
        age = time.time() - cache_entry["time_unix"]
        
        # Check if cache is still fresh (within timeout)
        if age > PRICE_CACHE_TIMEOUT:
            logger.debug(f"[CACHE] Price for {symbol} is stale ({age:.0f}s old)")
            return None
        
        return cache_entry["price"]
    
    def get_price_freshness(self, symbol: str) -> Optional[float]:
        """
        Get how fresh the cached price is in seconds.
        
        Args:
            symbol: Symbol/instrument key
            
        Returns:
            float: Age of price in seconds, None if not cached
        """
        if symbol not in self.price_cache:
            return None
        
        return time.time() - self.price_cache[symbol]["time_unix"]

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to WebSocket with exponential backoff and jitter."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"[CRITICAL] Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            if self.network_error_count > self.max_network_errors:
                logger.error("[CRITICAL] Network error limit exceeded. Manual intervention may be required.")
            return

        self.reconnect_attempts += 1
        
        # Check DNS health first (non-blocking check)
        if self.reconnect_attempts % 3 == 0:  # Check DNS every 3 attempts
            logger.info("[DNS] Checking DNS health...")
            dns_ok = await self._check_dns_health()
            if not dns_ok:
                logger.warning("[DNS] ⚠️ DNS is still failing, reconnection unlikely to succeed")
                await self.telegram.send_message(
                    "⚠️ <b>DNS Resolution Issue Detected</b>\n"
                    "Network appears to have DNS failures. System will continue retrying. "
                    "If this persists, please check your internet connection."
                )
        
        # Exponential backoff with cap: base_delay * (2 ^ attempt_number)
        exponential_delay = self.base_reconnect_delay * (2 ** min(self.reconnect_attempts - 1, 5))
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER * exponential_delay)
        # Cap max delay at 5 minutes
        max_delay = 300
        wait_time = min(exponential_delay + jitter, max_delay)
        
        logger.info(f"[VERBOSE] Reconnecting (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        logger.info(f"[VERBOSE] Waiting {wait_time:.1f} seconds before retry (with jitter)...")
        logger.info(f"[VERBOSE] Network errors so far: {self.network_error_count}/{self.max_network_errors}")
        
        try:
            await asyncio.sleep(wait_time)
        except asyncio.CancelledError:
            logger.info("[VERBOSE] Reconnect sleep cancelled")
            return
        
        logger.info(f"[VERBOSE] Attempting reconnection...")
        if await self.connect():
            logger.info("[SUCCESS] Reconnection successful!")
            if self.subscribed_symbols:
                logger.info(f"[VERBOSE] Re-subscribing to {len(self.subscribed_symbols)} symbols...")
                await self.subscribe(list(self.subscribed_symbols))
        else:
            logger.warning("[WARNING] Reconnection attempt failed, will retry")

    @staticmethod
    def _symbol_to_token(symbol: str) -> str:
        """
        Convert symbol to token for Upstox V3 API
        Upstox V3 expects format: NSE_EQ|INFY or NSE_FO|INFY23D15800CE
        
        Args:
            symbol: Symbol name (can be with or without prefix)
        
        Returns:
            Token string in Upstox V3 format
        """
        # Already in correct format
        if "|" in symbol:
            return symbol
        
        # Determine if it's equity or FNO based on symbol characteristics
        # FNO symbols typically end with PE, CE, or have date patterns
        if symbol.endswith(("PE", "CE")) or (len(symbol) > 10 and any(c.isdigit() for c in symbol[-4:])):
            # FNO symbol
            return f"NSE_FO|{symbol}"
        elif symbol.endswith("-EQ"):
            # Equity with explicit -EQ suffix
            return f"NSE_EQ|{symbol.replace('-EQ', '')}"
        else:
            # Default to FNO for trading bot symbols
            return f"NSE_FO|{symbol}"

    def get_subscribed_symbols(self) -> List[str]:
        """Get list of currently subscribed symbols"""
        return list(self.subscribed_symbols)

    def is_symbol_subscribed(self, symbol: str) -> bool:
        """Check if symbol is subscribed"""
        return symbol in self.subscribed_symbols


websocket_client: Optional[UpstoxWebSocketClient] = None


async def initialize_websocket():
    """Initialize global WebSocket client"""
    global websocket_client
    
    try:
        websocket_client = UpstoxWebSocketClient(
            access_token=settings.upstox_access_token,
            client_code=settings.upstox_client_code
        )
        
        if await websocket_client.connect():
            logger.info("SUCCESS WebSocket client initialized and connected")
            return websocket_client
        else:
            logger.error("Failed to connect WebSocket client")
            return None
            
    except Exception as e:
        logger.error(f"Error initializing WebSocket: {e}")
        return None


async def shutdown_websocket():
    """Shutdown global WebSocket client"""
    global websocket_client
    
    if websocket_client:
        await websocket_client.disconnect()
        websocket_client = None
        logger.info("WebSocket client shutdown")


def get_websocket_client() -> Optional[UpstoxWebSocketClient]:
    """Get the global WebSocket client instance"""
    return websocket_client
