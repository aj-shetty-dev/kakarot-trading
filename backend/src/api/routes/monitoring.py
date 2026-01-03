"""
Monitoring API Endpoints
Provides system status, logs, and metrics for the dashboard
"""

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from typing import Dict, Any, List
import os
import json
import base64
from datetime import datetime
from pathlib import Path

from ...config.settings import settings
from ...config.timezone import ist_now
from ...config.auth_utils import get_token_expiry
from ...trading.session_manager import session_manager
from ...websocket.service import get_websocket_service

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status"""
    ws_service = get_websocket_service()
    token_info = get_token_expiry(settings.upstox_access_token)
    
    status = {
        "timestamp": ist_now().isoformat(),
        "session": session_manager.get_status(),
        "websocket": {
            "connected": ws_service.ws_client.is_connected if ws_service and ws_service.ws_client else False,
            "running": ws_service.is_running if ws_service else False,
        },
        "environment": {
            "mode": "Paper Trading" if settings.paper_trading_mode else "Live Trading",
            "log_level": settings.log_level,
            "upstox_access_token": settings.upstox_access_token[:10] + "..." if settings.upstox_access_token else "None",
            "token_expiry": token_info
        },
        "settings": {
            "paper_trading_mode": settings.paper_trading_mode,
            "account_size": settings.account_size,
            "risk_per_trade": settings.risk_per_trade,
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
    """Update application settings and persist to config.json"""
    config_path = Path("config.json")
    
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
        
        # If token was updated and session is active, restart session in background
        if token_updated:
            background_tasks.add_task(session_manager.restart_active_session)
                
        return {"status": "success", "message": "Settings updated and persisted"}
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

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "time": ist_now().isoformat()}
