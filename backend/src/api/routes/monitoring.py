"""
Monitoring API Endpoints
Provides system status, logs, and metrics for the dashboard
"""

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from typing import Dict, Any, List
import os
import json
import base64
import time
from datetime import datetime
from pathlib import Path

from ...config.settings import settings
from ...config.timezone import ist_now
from ...config.auth_utils import get_token_expiry
from ...config.logging import logger
from ...websocket.service import get_websocket_service
from ...data.database import SessionLocal
import httpx

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/login-url")
async def get_login_url() -> Dict[str, str]:
    """Generate the Upstox login URL for the user"""
    # Default redirect URI if not specified
    redirect_uri = "https://localhost:8000/callback"
    url = (
        f"https://api.upstox.com/v2/login/authorization/dialog"
        f"?response_type=code&client_id={settings.upstox_api_key}"
        f"&redirect_uri={redirect_uri}"
    )
    return {"url": url}

@router.post("/exchange-token")
async def exchange_token(background_tasks: BackgroundTasks, data: Dict[str, str] = Body(...)):
    """Exchange auth code for access token and update settings"""
    auth_code = data.get("code")
    if not auth_code:
        raise HTTPException(status_code=400, detail="Auth code is required")
    
    redirect_uri = data.get("redirect_uri", "https://localhost:8000/callback")
    
    url = "https://api.upstox.com/v2/login/authorization/token"
    payload = {
        "code": auth_code,
        "client_id": settings.upstox_api_key,
        "client_secret": settings.upstox_api_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=payload, headers={"Accept": "application/json"})
            result = response.json()
            
            if response.status_code == 200 and "access_token" in result:
                access_token = result["access_token"]
                
                # Update settings via the existing update_settings logic
                # We call it internally or just replicate the logic
                await update_settings(background_tasks, {"upstox_access_token": access_token})
                
                return {
                    "status": "success", 
                    "message": "Token exchanged and updated successfully. Session restarting...",
                    "expires_in": result.get("expires_in")
                }
            else:
                error_msg = result.get("errors", [{}])[0].get("message", "Unknown error")
                raise HTTPException(status_code=response.status_code, detail=f"Upstox Error: {error_msg}")
                
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    ws_service = get_websocket_service()
    token_info = get_token_expiry(settings.upstox_access_token)
    
    status = {
        "timestamp": ist_now().isoformat(),
        "websocket": {
            "connected": ws_service.ws_client.is_connected if ws_service and ws_service.ws_client else False,
            "running": ws_service.is_running if ws_service else False,
        },
        "environment": {
            "mode": "Data Collection Only",
            "log_level": settings.log_level,
            "upstox_access_token": settings.upstox_access_token[:10] + "..." if settings.upstox_access_token else "None",
            "token_expiry": token_info
        },
        "settings": {
            "market_open_time": settings.market_open_time,
            "market_close_time": settings.market_close_time,
            "auto_start_stop": settings.auto_start_stop
        }
    }
    
    # Add subscription stats if available
    if ws_service and ws_service.subscription_manager:
        status["websocket"]["subscriptions"] = ws_service.subscription_manager.get_subscription_status()
        
    return status

@router.post("/settings")
async def update_settings(background_tasks: BackgroundTasks, new_settings: Dict[str, Any] = Body(...)):
    """Update application settings and persist to config.json and .env"""
    config_path = Path("config.json")
    env_path = Path(".env")
    
    # Load existing config
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
        except:
            pass
            
    # Update with new values
    config_data.update(new_settings)
    
    # Save back to config.json
    try:
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=4)
        
        # Also update .env file for credentials that matter
        env_key_mapping = {
            "upstox_access_token": "UPSTOX_ACCESS_TOKEN",
            "upstox_api_key": "UPSTOX_API_KEY",
            "upstox_api_secret": "UPSTOX_API_SECRET",
            "upstox_client_code": "UPSTOX_CLIENT_CODE",
        }
        
        # Load existing .env if it exists
        env_vars = {}
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        
        # Update .env with new credentials
        for config_key, env_key in env_key_mapping.items():
            if config_key in new_settings:
                env_vars[env_key] = str(new_settings[config_key])
        
        # Write .env file with proper formatting
        with open(env_path, "w") as f:
            for key, value in sorted(env_vars.items()):
                f.write(f"{key}={value}\n")
            
        # Update runtime settings object
        token_updated = False
        telegram_updated = False
        for key, value in new_settings.items():
            if hasattr(settings, key):
                old_val = getattr(settings, key)
                if key == "upstox_access_token" and old_val != value:
                    token_updated = True
                if (key.startswith("telegram_") or key == "enable_notifications") and old_val != value:
                    telegram_updated = True
                setattr(settings, key, value)
        
        # Refresh telegram service if settings changed
        if telegram_updated:
            from ...notifications.telegram import get_telegram_service
            get_telegram_service(settings, refresh=True)
                
        return {"status": "success", "message": "Settings updated and persisted to config.json and .env"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

@router.get("/logs/recent")
async def get_recent_logs(lines: int = 50) -> List[str]:
    """Get the most recent log lines from the trading log"""
    date_str = ist_now().strftime('%Y-%m-%d')
    log_file = os.path.join(settings.log_dir, date_str, "trading.log")
    
    if not os.path.exists(log_file):
        return [f"Log file for {date_str} not found yet."]
        
    try:
        # Efficiently read last N lines
        with open(log_file, "r") as f:
            # For small files, this is fine. For huge files, we'd use seek.
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Error reading logs: {str(e)}"]

@router.get("/connection-health")
async def connection_health():
    """
    Check WebSocket and network health
    
    Returns health status of DNS, WebSocket connection, and cached prices
    """
    try:
        from ...websocket.client import get_websocket_client
        
        ws_client = get_websocket_client()
        now = ist_now()
        
        result = {
            "timestamp": now.isoformat(),
            "websocket": {
                "connected": ws_client.is_connected if ws_client else False,
                "subscribed_symbols": len(ws_client.subscribed_symbols) if ws_client else 0,
                "reconnect_attempts": ws_client.reconnect_attempts if ws_client else 0,
                "network_errors": ws_client.network_error_count if ws_client else 0
            },
            "price_cache": {
                "cached_symbols": len(ws_client.price_cache) if ws_client else 0,
                "last_update": ws_client.last_cache_update_time if ws_client else None,
                "cache_entries": {}
            }
        }
        
        # Add sample cache entries
        if ws_client and ws_client.price_cache:
            for symbol, data in list(ws_client.price_cache.items())[:5]:
                age = time.time() - data["time_unix"]
                result["price_cache"]["cache_entries"][symbol] = {
                    "price": data["price"],
                    "age_seconds": age,
                    "is_stale": age > 30
                }
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking connection health: {e}")
        return {
            "timestamp": ist_now().isoformat(),
            "error": str(e)
        }

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "time": ist_now().isoformat()}
