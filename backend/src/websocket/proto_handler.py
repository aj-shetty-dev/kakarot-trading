"""
Protobuf Handler for Upstox V3 WebSocket
Handles encoding/decoding of binary protobuf messages

Uses compiled MarketDataFeed_pb2.py for proper protobuf parsing.
"""

import json
from typing import Dict, Any, Optional, List

from ..config.timezone import ist_timestamp

from ..config.logging import websocket_logger as logger

# Import compiled protobuf module
try:
    from . import MarketDataFeed_pb2 as pb
    PROTOBUF_AVAILABLE = True
    logger.info("✅ Protobuf module loaded successfully")
except ImportError as e:
    PROTOBUF_AVAILABLE = False
    pb = None
    logger.warning(f"⚠️ Protobuf module not available: {e}")


class UpstoxV3MessageParser:
    """
    Parser for Upstox V3 WebSocket messages
    
    V3 uses binary protobuf for data messages.
    Subscription requests are JSON text.
    
    Message Types (from proto):
    - initial_feed (0): Initial feed data
    - live_feed (1): Real-time tick data
    - market_info (2): Market segment status
    """
    
    # Market status mappings
    MARKET_STATUS = {
        0: "PRE_OPEN_START",
        1: "PRE_OPEN_END", 
        2: "NORMAL_OPEN",
        3: "NORMAL_CLOSE",
        4: "CLOSING_START",
        5: "CLOSING_END"
    }
    
    # Request mode mappings
    REQUEST_MODE = {
        0: "ltpc",
        1: "full_d5",
        2: "option_greeks",
        3: "full_d30"
    }
    
    # Type enum mappings
    TYPE_MAP = {
        0: "initial_feed",
        1: "live_feed",
        2: "market_info"
    }
    
    def __init__(self):
        """Initialize message parser"""
        self.last_market_info = None
        self.tick_count = 0
        self.protobuf_available = PROTOBUF_AVAILABLE
        
        if not PROTOBUF_AVAILABLE:
            logger.warning("⚠️ Running without protobuf support - binary messages will fail")
    
    def create_subscription_request(
        self, 
        instrument_keys: List[str], 
        mode: str = "full",
        guid: Optional[str] = None
    ) -> bytes:
        """
        Create a subscription request message
        
        Upstox V3 accepts JSON text for subscription requests.
        Format:
        {
            "guid": "unique-id",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": ["NSE_FO|60965", ...]
            }
        }
        
        Args:
            instrument_keys: List of instrument keys (e.g., ["NSE_FO|60965"])
            mode: Subscription mode - "ltpc", "full", "option_greeks", "full_d30"
            guid: Optional unique identifier
        
        Returns:
            bytes: Encoded message ready to send
        """
        if not guid:
            guid = f"sub-{len(instrument_keys)}-{ist_timestamp()}"
        
        request = {
            "guid": guid,
            "method": "sub",
            "data": {
                "mode": mode,
                "instrumentKeys": instrument_keys
            }
        }
        
        # V3 accepts JSON text for subscriptions
        return json.dumps(request).encode('utf-8')
    
    def create_unsubscription_request(
        self,
        instrument_keys: List[str],
        guid: Optional[str] = None
    ) -> bytes:
        """
        Create an unsubscription request message
        
        Args:
            instrument_keys: List of instrument keys to unsubscribe
            guid: Optional unique identifier
        
        Returns:
            bytes: Encoded message ready to send
        """
        if not guid:
            guid = f"unsub-{len(instrument_keys)}-{ist_timestamp()}"
        
        request = {
            "guid": guid,
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }
        
        return json.dumps(request).encode('utf-8')
    
    def parse_message(self, message: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse incoming WebSocket message
        
        V3 sends:
        1. JSON text messages for control responses (subscription confirmations)
        2. Binary protobuf for market data (live_feed, market_info)
        
        Args:
            message: Raw message bytes from WebSocket
        
        Returns:
            Parsed message dict or None if parsing fails
        """
        try:
            # Try to decode as JSON first (control messages)
            if isinstance(message, bytes):
                try:
                    text = message.decode('utf-8')
                    data = json.loads(text)
                    return self._parse_control_message(data)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # Not JSON - try binary protobuf
                    pass
            else:
                # String message (shouldn't happen for V3)
                try:
                    data = json.loads(message)
                    return self._parse_control_message(data)
                except json.JSONDecodeError:
                    pass
            
            # Parse as binary protobuf
            return self._parse_protobuf(message)
                
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return None
    
    def _parse_protobuf(self, message: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse binary protobuf message
        
        Args:
            message: Raw binary protobuf data
        
        Returns:
            Parsed dict or None
        """
        if not PROTOBUF_AVAILABLE:
            logger.warning("Cannot parse protobuf - module not available")
            return None
        
        try:
            # Parse FeedResponse
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(message)
            
            # Get message type
            msg_type = self.TYPE_MAP.get(feed_response.type, "unknown")
            
            # Log all message types (not just debug)
            logger.info(f"[PROTOBUF] Message type: {msg_type} (raw type: {feed_response.type})")
            
            if msg_type == "market_info":
                return self._parse_market_info_proto(feed_response)
            elif msg_type in ["live_feed", "initial_feed"]:
                logger.info(f"[PROTOBUF] Parsing {msg_type} message")
                return self._parse_live_feed_proto(feed_response)
            else:
                logger.debug(f"Unknown protobuf message type: {feed_response.type}")
                return {
                    "type": msg_type,
                    "raw": str(feed_response)[:200]
                }
                
        except Exception as e:
            logger.error(f"Error parsing protobuf: {e}")
            logger.debug(f"Message bytes (first 100): {message[:100].hex() if message else 'empty'}")
            return None
    
    def _parse_market_info_proto(self, feed_response) -> Dict[str, Any]:
        """
        Parse market_info protobuf message
        
        Contains market status for each segment (NSE_EQ, NSE_FO, etc.)
        """
        segment_status = {}
        
        if feed_response.marketInfo:
            for segment, status in feed_response.marketInfo.segmentStatus.items():
                segment_status[segment] = self.MARKET_STATUS.get(status, "UNKNOWN")
        
        self.last_market_info = {
            "type": "market_info",
            "timestamp": feed_response.currentTs,
            "segment_status": segment_status
        }
        
        # Determine if market is open
        is_market_open = segment_status.get("NSE_FO") == "NORMAL_OPEN"
        
        logger.info(f"[MARKET INFO] NSE_FO status: {segment_status.get('NSE_FO', 'unknown')}")
        
        return {
            "type": "market_info",
            "timestamp": feed_response.currentTs,
            "segment_status": segment_status,
            "is_market_open": is_market_open
        }
    
    def _parse_live_feed_proto(self, feed_response) -> Dict[str, Any]:
        """
        Parse live_feed protobuf message
        
        Contains tick data for subscribed instruments
        """
        current_ts = feed_response.currentTs
        parsed_ticks = []
        
        for instrument_key, feed in feed_response.feeds.items():
            tick = self._extract_tick_from_feed(instrument_key, feed, current_ts)
            if tick:
                parsed_ticks.append(tick)
                self.tick_count += 1
        
        if parsed_ticks:
            logger.debug(f"[FEED] Parsed {len(parsed_ticks)} ticks, total: {self.tick_count}")
        
        return {
            "type": "live_feed",
            "timestamp": current_ts,
            "ticks": parsed_ticks,
            "tick_count": len(parsed_ticks)
        }
    
    def _extract_tick_from_feed(
        self, 
        instrument_key: str, 
        feed, 
        timestamp: int
    ) -> Optional[Dict[str, Any]]:
        """
        Extract tick data from a Feed protobuf message
        
        Feed has oneof: ltpc, fullFeed, firstLevelWithGreeks
        """
        tick = {
            "instrument_key": instrument_key,
            "timestamp": timestamp
        }
        
        try:
            # Determine which feed type is present
            feed_type = feed.WhichOneof("FeedUnion")
            
            if feed_type == "ltpc":
                # LTPC mode - simple LTP data
                ltpc = feed.ltpc
                tick.update({
                    "ltp": ltpc.ltp,
                    "ltt": ltpc.ltt,
                    "ltq": ltpc.ltq,
                    "cp": ltpc.cp
                })
                
            elif feed_type == "fullFeed":
                # Full mode (full_d5)
                full_feed = feed.fullFeed
                
                # Determine if market or index feed
                ff_type = full_feed.WhichOneof("FullFeedUnion")
                
                if ff_type == "marketFF":
                    market_ff = full_feed.marketFF
                    
                    # LTPC data
                    if market_ff.ltpc:
                        tick.update({
                            "ltp": market_ff.ltpc.ltp,
                            "ltt": market_ff.ltpc.ltt,
                            "ltq": market_ff.ltpc.ltq,
                            "cp": market_ff.ltpc.cp
                        })
                    
                    # Market depth (bid/ask)
                    if market_ff.marketLevel and market_ff.marketLevel.bidAskQuote:
                        depth = market_ff.marketLevel.bidAskQuote
                        if depth:
                            best_bid_ask = depth[0]
                            tick.update({
                                "bid": best_bid_ask.bidP,
                                "bid_qty": best_bid_ask.bidQ,
                                "ask": best_bid_ask.askP,
                                "ask_qty": best_bid_ask.askQ
                            })
                            # Store full depth (D5)
                            tick["depth"] = [
                                {
                                    "bidP": q.bidP, "bidQ": q.bidQ,
                                    "askP": q.askP, "askQ": q.askQ
                                } for q in depth
                            ]
                    
                    # Option Greeks
                    if market_ff.optionGreeks:
                        greeks = market_ff.optionGreeks
                        tick.update({
                            "delta": greeks.delta,
                            "theta": greeks.theta,
                            "gamma": greeks.gamma,
                            "vega": greeks.vega,
                            "rho": greeks.rho
                        })
                    
                    # Additional fields
                    tick.update({
                        "atp": market_ff.atp,
                        "volume": market_ff.vtt,
                        "oi": market_ff.oi,
                        "iv": market_ff.iv,
                        "tbq": market_ff.tbq,
                        "tsq": market_ff.tsq
                    })
                    
                    # OHLC data
                    if market_ff.marketOHLC and market_ff.marketOHLC.ohlc:
                        for ohlc in market_ff.marketOHLC.ohlc:
                            if ohlc.interval == "1d":
                                tick.update({
                                    "day_open": ohlc.open,
                                    "day_high": ohlc.high,
                                    "day_low": ohlc.low,
                                    "day_close": ohlc.close
                                })
                                break
                                
                elif ff_type == "indexFF":
                    index_ff = full_feed.indexFF
                    
                    # Index LTPC
                    if index_ff.ltpc:
                        tick.update({
                            "ltp": index_ff.ltpc.ltp,
                            "ltt": index_ff.ltpc.ltt,
                            "ltq": index_ff.ltpc.ltq,
                            "cp": index_ff.ltpc.cp
                        })
                    
                    # Index OHLC
                    if index_ff.marketOHLC and index_ff.marketOHLC.ohlc:
                        for ohlc in index_ff.marketOHLC.ohlc:
                            if ohlc.interval == "1d":
                                tick.update({
                                    "day_open": ohlc.open,
                                    "day_high": ohlc.high,
                                    "day_low": ohlc.low,
                                    "day_close": ohlc.close
                                })
                                break
                                
            elif feed_type == "firstLevelWithGreeks":
                # Option Greeks mode
                flwg = feed.firstLevelWithGreeks
                
                # LTPC
                if flwg.ltpc:
                    tick.update({
                        "ltp": flwg.ltpc.ltp,
                        "ltt": flwg.ltpc.ltt,
                        "ltq": flwg.ltpc.ltq,
                        "cp": flwg.ltpc.cp
                    })
                
                # First depth level
                if flwg.firstDepth:
                    tick.update({
                        "bid": flwg.firstDepth.bidP,
                        "bid_qty": flwg.firstDepth.bidQ,
                        "ask": flwg.firstDepth.askP,
                        "ask_qty": flwg.firstDepth.askQ
                    })
                
                # Greeks
                if flwg.optionGreeks:
                    tick.update({
                        "delta": flwg.optionGreeks.delta,
                        "theta": flwg.optionGreeks.theta,
                        "gamma": flwg.optionGreeks.gamma,
                        "vega": flwg.optionGreeks.vega,
                        "rho": flwg.optionGreeks.rho
                    })
                
                # Additional fields
                tick.update({
                    "volume": flwg.vtt,
                    "oi": flwg.oi,
                    "iv": flwg.iv
                })
            
            return tick if tick.get("ltp") else None
            
        except Exception as e:
            logger.error(f"Error extracting tick from feed: {e}")
            return None
    
    def _parse_control_message(self, data: Dict) -> Dict[str, Any]:
        """
        Parse JSON control messages (subscription responses)
        
        Example:
        {
            "guid": "sub-...",
            "method": "sub",
            "status": "success"
        }
        """
        return {
            "type": "control",
            "guid": data.get("guid"),
            "method": data.get("method"),
            "status": data.get("status"),
            "data": data
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get parser statistics"""
        return {
            "ticks_parsed": self.tick_count,
            "protobuf_available": self.protobuf_available,
            "market_open": self.last_market_info.get("is_market_open") if self.last_market_info else None
        }


# Global parser instance
message_parser: Optional[UpstoxV3MessageParser] = None


def get_message_parser() -> UpstoxV3MessageParser:
    """Get or create global message parser"""
    global message_parser
    if not message_parser:
        message_parser = UpstoxV3MessageParser()
    return message_parser
