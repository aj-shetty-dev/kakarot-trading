# Upstox WebSocket Connection Guide

## Overview
Upstox provides WebSocket connections for real-time market data and portfolio updates through their Python SDK. The SDK abstracts away the complexity of manual WebSocket connections.

## WebSocket URLs

### Portfolio Stream Feed (Order Updates)
- **WebSocket URL**: `wss://api.upstox.com/v2/feed/portfolio-stream-feed`
- **Authorization**: OAuth2 Bearer token in Authorization header
- **Available Updates**: Order updates, position updates, holding updates, GTT order updates
- **Protocol**: Binary WebSocket with JSON messages

### Market Data Feed (v2)
- **Authorization Endpoint**: `https://api.upstox.com/v2/feed/market-data-feed/authorize`
- **WebSocket URL**: Retrieved from authorization endpoint
- **Authorization**: OAuth2 Bearer token
- **Protocol**: Binary WebSocket

### Market Data Feed (v3)
- **WebSocket URL**: `wss://api.upstox.com/v3/feed/market-data-feed`
- **Authorization**: OAuth2 Bearer token in Authorization header
- **Data Format**: Protobuf (binary encoded)
- **Features**: 
  - Subscribe to instrument keys
  - Supports multiple modes: `ltpc`, `full`, `option_greeks`, `full_d30`
  - Can change modes for subscribed instruments
- **Protocol**: Binary WebSocket with Protobuf messages

## Connection Flow

### 1. Portfolio Stream Feed Connection

```python
import upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Create streamer with optional update types
streamer = upstox_client.PortfolioDataStreamer(
    upstox_client.ApiClient(configuration),
    order_update=True,
    position_update=False,
    holding_update=False,
    gtt_update=False
)

def on_message(message):
    print(f"Received: {message}")

def on_open():
    print("Connection established")

def on_error(error):
    print(f"Error: {error}")

def on_close(code, message):
    print(f"Connection closed: {code} - {message}")

streamer.on("message", on_message)
streamer.on("open", on_open)
streamer.on("error", on_error)
streamer.on("close", on_close)

# Optional: Configure auto-reconnect
streamer.auto_reconnect(True, interval=5, retry_count=10)

streamer.connect()
```

**Internal Connection Details:**
- URL Construction: `wss://api.upstox.com/v2/feed/portfolio-stream-feed?update_types=order,position,holding,gtt_order`
- SSL Options: `cert_reqs: CERT_NONE`, `check_hostname: False`
- Authorization Header: `Authorization: Bearer {access_token}`

### 2. Market Data Stream Feed Connection (v3)

```python
import upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = 'YOUR_ACCESS_TOKEN'

# Create streamer with instrument keys and mode
streamer = upstox_client.MarketDataStreamerV3(
    upstox_client.ApiClient(configuration),
    instrumentKeys=["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank"],
    mode="full"  # Options: ltpc, full, option_greeks, full_d30
)

def on_message(message):
    # Message is protobuf encoded - decode it
    data = streamer.decode_protobuf(message)
    print(f"Market data: {data}")

def on_open():
    print("Market feed connected")

def on_error(error):
    print(f"Error: {error}")

streamer.on("message", on_message)
streamer.on("open", on_open)
streamer.on("error", on_error)

# Subscribe to additional instruments
streamer.subscribe(["NSE_EQ|Infy"], mode="full")

# Change mode for existing subscriptions
streamer.change_mode(["NSE_INDEX|Nifty 50"], newMode="ltpc")

# Unsubscribe from instruments
streamer.unsubscribe(["NSE_EQ|Infy"])

streamer.connect()
```

**Internal Connection Details:**
- WebSocket URL: `wss://api.upstox.com/v3/feed/market-data-feed`
- SSL Options: `cert_reqs: CERT_NONE`, `check_hostname: False`
- Authorization Header: `Authorization: Bearer {access_token}`
- Initial Subscription Message Format (JSON, sent as binary):
  ```json
  {
    "guid": "unique-guid-string",
    "method": "sub",
    "data": {
      "mode": "full",
      "instrumentKeys": ["NSE_INDEX|Nifty 50"]
    }
  }
  ```

## Manual WebSocket Connection (Without SDK)

If you want to connect manually using `websockets` library:

```python
import asyncio
import ssl
import websockets
import json

async def connect_market_feed():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    access_token = 'YOUR_ACCESS_TOKEN'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    uri = 'wss://api.upstox.com/v3/feed/market-data-feed'
    
    async with websockets.connect(uri, ssl=ssl_context, extra_headers=headers) as websocket:
        # Subscribe to instruments
        subscription = {
            "guid": "unique-guid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": ["NSE_INDEX|Nifty 50"]
            }
        }
        
        await websocket.send(json.dumps(subscription).encode('utf-8'))
        
        # Receive messages
        while True:
            message = await websocket.recv()
            print(f"Received: {message}")

asyncio.run(connect_market_feed())
```

## Authentication Flow

1. **Get Authorization Token**:
   - Obtain OAuth2 access token from Upstox auth endpoint
   - Token format: Standard Bearer token

2. **Connect to WebSocket**:
   - Include token in `Authorization` header: `Authorization: Bearer {token}`
   - Token must be valid at connection time
   - Token refresh may be needed for long-running connections

3. **Available Authorization Methods**:
   - OAuth2 Bearer Token (standard method)
   - Configured in SDK via `configuration.access_token = 'TOKEN'`

## WebSocket Events

Both streamers emit these events:
- **open**: Successfully connected to WebSocket
- **close**: Connection closed (includes code and message)
- **message**: New data received
- **error**: Connection error occurred
- **reconnecting**: Auto-reconnect attempt in progress
- **autoReconnectStopped**: Auto-reconnect disabled after retries exhausted

## Data Modes (Market Data v3)

| Mode | Description |
|------|-------------|
| `ltpc` | Last traded price and change |
| `full` | Complete market data |
| `option_greeks` | Options with Greeks |
| `full_d30` | Full data with 30-day history |

## Query Parameters

### Portfolio Stream Feed
- `update_types`: Comma-separated list of update types
  - `order`: Order updates
  - `position`: Position updates
  - `holding`: Holding updates
  - `gtt_order`: GTT order updates

## Message Protocol Details

### Portfolio Feed Messages
- Format: JSON
- Encoding: UTF-8 text over WebSocket
- Contains: Order updates, position changes, holding changes

### Market Data v3 Messages
- Format: Protobuf binary
- Must decode using Protobuf schema: `MarketDataFeedV3_pb2`
- Contains: LTP, OHLC, volume, Greeks, etc.

## Common Issues & Solutions

### Connection Refused
- Check SSL certificate verification is disabled (default in SDK)
- Verify access token is valid and not expired
- Ensure firewall allows WebSocket connections

### Authorization Failures
- Verify access token format and validity
- Check token expiration
- Ensure OAuth2 token hasn't been revoked

### Message Decoding Errors
- For v3: Ensure protobuf schema files are up-to-date
- Check binary data format matches expected protocol

### Auto-Reconnect Configuration
```python
streamer.auto_reconnect(
    enable=True,           # Enable/disable
    interval=5,            # Seconds between attempts
    retry_count=10         # Maximum retry attempts
)
```

## Rate Limiting
- WebSocket connections are subject to Upstox API rate limits
- Generally more generous than REST API limits
- Recommended to implement backoff in reconnect logic

## Performance Considerations
- Binary Protobuf format (v3) is more efficient than JSON
- Market data v3 recommended for high-frequency applications
- Auto-reconnect can be tuned for your use case
- Consider message buffering for high-volume data

## Related APIs
- `/v2/feed/market-data-feed/authorize`: Get market data feed URI
- `/v2/feed/portfolio-stream-feed/authorize`: Get portfolio stream URI (for manual connections)
- OAuth2 endpoints for token management
