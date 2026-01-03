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
from ...data.database import SessionLocal
from ...data.models import MLFeatureLog
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

@router.get("/ml-stats")
async def get_ml_stats() -> Dict[str, Any]:
    """Get statistics on collected ML data"""
    db = SessionLocal()
    try:
        total_samples = db.query(MLFeatureLog).count()
        labeled_samples = db.query(MLFeatureLog).filter(MLFeatureLog.label.isnot(None)).count()
        wins = db.query(MLFeatureLog).filter(MLFeatureLog.label == 1).count()
        losses = db.query(MLFeatureLog).filter(MLFeatureLog.label == 0).count()
        
        # Get samples by signal type
        buy_samples = db.query(MLFeatureLog).filter(MLFeatureLog.signal_type == 'BUY').count()
        sell_samples = db.query(MLFeatureLog).filter(MLFeatureLog.signal_type == 'SELL').count()
        
        return {
            "total_samples": total_samples,
            "labeled_samples": labeled_samples,
            "pending_samples": total_samples - labeled_samples,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / labeled_samples * 100) if labeled_samples > 0 else 0,
            "buy_samples": buy_samples,
            "sell_samples": sell_samples,
            "ready_for_training": labeled_samples >= 100,
            "progress_percent": min(100, (labeled_samples / 100) * 100)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

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
