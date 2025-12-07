"""
Verification endpoints for testing subscription and data flow
"""

from fastapi import APIRouter
from sqlalchemy.orm import Session
import asyncio
import httpx

from ...config.logging import logger
from ...data.database import SessionLocal
from ...data.models import SubscribedOption, Tick, Symbol
from ...config.settings import settings
from ...websocket.handlers import get_aggregated_handler

router = APIRouter(prefix="/api/v1/verify", tags=["verification"])


@router.get("/subscriptions")
async def verify_subscriptions():
    """
    Verify subscription configuration
    Returns details about subscribed options
    """
    db = SessionLocal()
    try:
        # Get subscription stats
        total_options = db.query(SubscribedOption).count()
        unique_symbols = db.query(SubscribedOption.symbol).distinct().count()
        
        # Sample some options
        sample_options = db.query(SubscribedOption).limit(5).all()
        sample_list = [
            {
                "symbol": opt.symbol,
                "option_symbol": opt.option_symbol,
                "strike_price": opt.strike_price
            }
            for opt in sample_options
        ]
        
        return {
            "status": "success",
            "total_options_subscribed": total_options,
            "unique_base_symbols": unique_symbols,
            "expected_total": 416,
            "expected_symbols": 208,
            "match": total_options == 416 and unique_symbols == 208,
            "sample_options": sample_list
        }
    except Exception as e:
        logger.error(f"Error verifying subscriptions: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@router.get("/fetch-sample-ltps")
async def fetch_sample_ltps():
    """
    Fetch LTP for sample of subscribed options from Upstox API
    This verifies that the option symbols are valid and the API works
    """
    db = SessionLocal()
    try:
        # Get random 10 sample options
        sample_options = db.query(SubscribedOption).limit(10).all()
        
        if not sample_options:
            return {"error": "No options found in database"}
        
        results = []
        
        access_token = settings.upstox_access_token
        if not access_token:
            return {"error": "No access token configured"}
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        async with httpx.AsyncClient() as client:
            for opt in sample_options:
                # Build the proper symbol for API (e.g., NFO_OPT|RELIANCE25X2500CE)
                api_symbol = f"NFO_OPT|{opt.option_symbol}"
                
                try:
                    params = {
                        "mode": "LTP",
                        "symbol": api_symbol
                    }
                    
                    response = await client.get(
                        "https://api.upstox.com/v2/market-quote/ltp",
                        params=params,
                        headers=headers,
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        ltp = data.get("data", {}).get(api_symbol, {}).get("ltp", None)
                        results.append({
                            "option_symbol": opt.option_symbol,
                            "status": "✅ success",
                            "ltp": ltp,
                            "http_status": 200
                        })
                    else:
                        results.append({
                            "option_symbol": opt.option_symbol,
                            "status": "❌ failed",
                            "http_status": response.status_code,
                            "error": response.text[:100]
                        })
                
                except Exception as e:
                    results.append({
                        "option_symbol": opt.option_symbol,
                        "status": "❌ error",
                        "error": str(e)
                    })
        
        # Count successes
        successful = sum(1 for r in results if r["status"] == "✅ success")
        
        return {
            "status": "completed",
            "total_sampled": len(sample_options),
            "successful": successful,
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error fetching sample LTPs: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@router.get("/tick-data-stats")
async def get_tick_stats():
    """
    Get statistics about tick data in database
    """
    db = SessionLocal()
    try:
        total_ticks = db.query(Tick).count()
        
        # Get ticks per option symbol
        tick_symbols = db.query(
            SubscribedOption.option_symbol,
            Symbol.symbol
        ).filter(
            Tick.symbol_id == Symbol.id
        ).distinct().count()
        
        if total_ticks > 0:
            # Get latest tick timestamp
            from sqlalchemy import func
            latest_tick = db.query(func.max(Tick.timestamp)).scalar()
            oldest_tick = db.query(func.min(Tick.timestamp)).scalar()
        else:
            latest_tick = None
            oldest_tick = None
        
        # Check if we're receiving real-time data
        aggregated_handler = get_aggregated_handler()
        realtime_symbols = 0
        if aggregated_handler:
            realtime_symbols = len(aggregated_handler.ticks_by_symbol)
        
        return {
            "status": "ok",
            "total_ticks_in_db": total_ticks,
            "unique_symbols_with_ticks": tick_symbols,
            "latest_tick_time": latest_tick.isoformat() if latest_tick else None,
            "oldest_tick_time": oldest_tick.isoformat() if oldest_tick else None,
            "realtime_symbols_receiving_data": realtime_symbols,
            "market_status": "closed" if total_ticks == 0 else "likely_receiving_data",
            "note": "If realtime_symbols_receiving_data > 0, WebSocket is receiving live ticks"
        }
    
    except Exception as e:
        logger.error(f"Error getting tick stats: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@router.post("/insert-test-ticks")
async def insert_test_ticks():
    """
    Insert test tick data for all subscribed options
    This simulates market data when market is closed
    Useful for testing the end-to-end pipeline
    """
    db = SessionLocal()
    try:
        from datetime import datetime
        import random
        
        subscribed_options = db.query(SubscribedOption).all()
        
        if not subscribed_options:
            return {"error": "No subscribed options found"}
        
        ticks_inserted = 0
        
        for opt in subscribed_options:
            # Find the symbol
            symbol = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
            
            if not symbol:
                continue
            
            # Generate realistic mock data
            base_price = opt.strike_price + random.uniform(-100, 100)
            ltp = max(0, base_price + random.uniform(-5, 5))
            
            tick = Tick(
                symbol_id=symbol.id,
                price=ltp,
                open_price=base_price,
                high_price=base_price + 50,
                low_price=base_price - 50,
                close_price=ltp,
                volume=random.randint(100, 10000),
                oi=random.randint(1000, 100000),
                bid=ltp - random.uniform(0.05, 0.50),
                ask=ltp + random.uniform(0.05, 0.50),
                bid_volume=random.randint(100, 5000),
                ask_volume=random.randint(100, 5000),
                timestamp=datetime.utcnow(),
                iv=random.uniform(0.15, 0.45),
                delta=random.uniform(-1, 1),
                gamma=random.uniform(0, 0.1),
                theta=random.uniform(-0.5, 0.1),
                vega=random.uniform(0, 1)
            )
            
            db.add(tick)
            ticks_inserted += 1
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Inserted {ticks_inserted} test ticks",
            "ticks_created": ticks_inserted,
            "note": "This is test data for development. In production, ticks come from WebSocket."
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error inserting test ticks: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@router.get("/health")
async def verification_health():
    """
    Comprehensive health check for subscription and data flow
    """
    db = SessionLocal()
    try:
        # Check database
        options_count = db.query(SubscribedOption).count()
        symbols_count = db.query(Symbol).filter(Symbol.is_fno == True).count()
        ticks_count = db.query(Tick).count()
        
        # Check aggregated handler (realtime ticks)
        handler = get_aggregated_handler()
        realtime_tracking = len(handler.ticks_by_symbol) if handler else 0
        
        all_healthy = (
            options_count == 416 and
            symbols_count == 208 and
            realtime_tracking > 0 or ticks_count > 0
        )
        
        return {
            "overall_health": "✅ Healthy" if all_healthy else "⚠️ Degraded",
            "checks": {
                "options_subscribed": {
                    "expected": 416,
                    "actual": options_count,
                    "status": "✅ pass" if options_count == 416 else "❌ fail"
                },
                "base_symbols": {
                    "expected": 208,
                    "actual": symbols_count,
                    "status": "✅ pass" if symbols_count == 208 else "❌ fail"
                },
                "websocket_receiving_data": {
                    "realtime_symbols": realtime_tracking,
                    "status": "✅ pass" if realtime_tracking > 0 else "⚠️ market_likely_closed"
                },
                "database_ticks": {
                    "total": ticks_count,
                    "status": "✅ has_data" if ticks_count > 0 else "⚠️ no_data_yet"
                }
            }
        }
    
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
