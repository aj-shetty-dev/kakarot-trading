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
from ...trading.session_manager import session_manager
from ...websocket.service import get_websocket_service
from ...data.database import SessionLocal
from ...data.models import MLFeatureLog, Account, Trade
import httpx

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

def get_account_summary(db: SessionLocal) -> Dict[str, Any]:
    """Get current account summary from DB"""
    from datetime import time, timedelta
    from ...config.constants import TradeStatus
    now = ist_now()
    today = now.date()
    today_start = datetime.combine(today, time.min)
    
    # All statuses that indicate a completed trade
    COMPLETED_STATUSES = [
        TradeStatus.CLOSED, 
        TradeStatus.STOPPED_OUT, 
        TradeStatus.TAKE_PROFIT, 
        TradeStatus.TRAILING_SL
    ]
    
    # Get or create today's account record
    account = db.query(Account).filter(Account.date >= today_start).first()
    if not account:
        # Calculate total P&L from all time up to yesterday
        yesterday_end = today_start
        historical_pnl_query = db.query(Trade).filter(
            Trade.status.in_(COMPLETED_STATUSES),
            Trade.exit_time < yesterday_end
        ).all()
        historical_pnl = sum(t.pnl for t in historical_pnl_query if t.pnl is not None)
        
        # Opening balance for today = Initial Capital + All previous profits
        opening_balance = settings.account_size + historical_pnl
        
        account = Account(
            available_balance=opening_balance,
            date=now
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    
    # Calculate daily P&L from all trades (LIVE and SCALPING)
    # Using filter on COMPLETED_STATUSES to ensure we only count finished trades
    trades = db.query(Trade).filter(
        Trade.created_at >= today_start,
        Trade.status.in_(COMPLETED_STATUSES)
    ).all()
    daily_pnl = sum(t.pnl for t in trades if t.pnl is not None)
    
    # Calculate cumulative P&L for all time to show total equity
    total_pnl_query = db.query(Trade).filter(Trade.status.in_(COMPLETED_STATUSES)).all()
    total_pnl = sum(t.pnl for t in total_pnl_query if t.pnl is not None)
    
    return {
        "balance": account.available_balance,
        "equity": settings.account_size + total_pnl,
        "daily_pnl": daily_pnl,
        "daily_pnl_percent": (daily_pnl / account.available_balance * 100) if account.available_balance > 0 else 0,
        "trades_today": len(trades)
    }

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
    
    db = SessionLocal()
    try:
        account_summary = get_account_summary(db)
    finally:
        db.close()
    
    status = {
        "timestamp": ist_now().isoformat(),
        "session": session_manager.get_status(),
        "account": account_summary,
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
            "daily_loss_limit": settings.daily_loss_limit,
            "daily_profit_target": settings.daily_profit_target,
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
        
        # If token was updated and session is active, restart session in background
        if token_updated:
            background_tasks.add_task(session_manager.restart_active_session)
                
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

@router.post("/emergency-close-position")
async def emergency_close_position(data: Dict[str, Any] = Body(...)):
    """
    Emergency endpoint to manually close a position when WebSocket is down.
    Used when automated monitoring can't trigger SL/TP.
    
    Args:
        data: {
            "symbol": str (required),
            "reason": str (optional, default="emergency")
        }
    
    Returns:
        {"status": "success", "trade_id": str, "message": str}
    """
    try:
        symbol = data.get("symbol")
        reason = data.get("reason", "emergency")
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        db = SessionLocal()
        
        # Find open trade for this symbol
        from ...config.constants import TradeStatus
        from ...data.models import Symbol
        
        # First find the symbol
        sym_obj = db.query(Symbol).filter(Symbol.symbol == symbol).first()
        if not sym_obj:
            db.close()
            raise HTTPException(
                status_code=404,
                detail=f"Symbol {symbol} not found"
            )
        
        # Then find the open trade for this symbol
        trade = db.query(Trade).filter(
            Trade.symbol_id == sym_obj.id,
            Trade.status == TradeStatus.OPEN
        ).first()
        
        if not trade:
            db.close()
            raise HTTPException(
                status_code=404,
                detail=f"No open trade found for {symbol}"
            )
        
        logger.warning(
            f"🚨 [EMERGENCY CLOSE] {symbol} triggered by {reason} "
            f"at ₹{trade.current_price} (Entry: ₹{trade.entry_price})"
        )
        
        # Import trading service
        from ...trading.service import trading_service
        
        # Close the trade immediately
        if reason == "stop_loss":
            status = TradeStatus.STOPPED_OUT
        elif reason == "take_profit":
            status = TradeStatus.TAKE_PROFIT
        else:
            status = TradeStatus.CLOSED
        
        await trading_service.close_trade(trade, status, db)
        
        response = {
            "status": "success",
            "trade_id": trade.id,
            "symbol": symbol,
            "entry_price": trade.entry_price,
            "exit_price": trade.current_price,
            "pnl": trade.pnl if trade.pnl else 0,
            "reason": reason,
            "message": f"Position {symbol} closed successfully"
        }
        
        db.close()
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency close failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")

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
