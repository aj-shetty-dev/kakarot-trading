#!/usr/bin/env python3
"""
End of Day Report Generator
Generates a summary of all tick data collected during the trading day.

Usage:
    python -m src.reports.end_of_day_report
    
Or from Docker:
    docker exec upstox_trading_bot python -m src.reports.end_of_day_report
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional
from sqlalchemy import func, extract

from ..data.database import SessionLocal
from ..data.models import Tick, Symbol, SubscribedOption, Trade, Signal
from ..config.settings import settings
from ..config.timezone import ist_now
from ..config.constants import TradeStatus
from ..config.logging import logger


def generate_end_of_day_report(output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate end of day report with tick statistics using efficient database aggregation.
    
    Returns:
        Dict with report data
    """
    if output_dir is None:
        today_str = ist_now().strftime('%Y-%m-%d')
        output_dir = os.path.join(settings.log_dir, today_str)
    
    os.makedirs(output_dir, exist_ok=True)
    
    db = SessionLocal()
    
    try:
        today = ist_now().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        logger.info(f"📊 Generating End of Day Report for {today}...")
        
        # 1. Get total tick count
        total_ticks = db.query(func.count(Tick.id)).filter(
            Tick.timestamp >= today_start
        ).scalar() or 0
        
        logger.info(f"📈 Total Ticks Recorded: {total_ticks:,}")
        
        if total_ticks == 0:
            logger.warning("⚠️ No ticks recorded today (market may be closed)")
            report = {"total_ticks": 0, "date": str(today), "generated_at": ist_now().isoformat()}
            report_path = os.path.join(output_dir, "eod_report.json")
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            return report
        
        # 2. Get statistics per symbol using aggregation
        # We want: symbol_id, count, min_price, max_price
        stats_query = db.query(
            Tick.symbol_id,
            func.count(Tick.id).label("tick_count"),
            func.min(Tick.price).label("low"),
            func.max(Tick.price).label("high"),
            func.avg(Tick.oi).label("avg_oi"),
            func.avg(Tick.iv).label("avg_iv")
        ).filter(
            Tick.timestamp >= today_start
        ).group_by(Tick.symbol_id).order_by(func.count(Tick.id).desc()).limit(50).all()
        
        # Get symbol names
        subscribed_options = db.query(SubscribedOption).all()
        symbol_to_option = {}
        for opt in subscribed_options:
            symbol = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
            if symbol:
                symbol_to_option[symbol.id] = opt.option_symbol
        
        option_stats = []
        for s in stats_query:
            option_name = symbol_to_option.get(s.symbol_id, f"Unknown ({str(s.symbol_id)[:8]})")
            
            # Get first and last price for this symbol
            first_price = db.query(Tick.price).filter(
                Tick.symbol_id == s.symbol_id,
                Tick.timestamp >= today_start
            ).order_by(Tick.timestamp.asc()).limit(1).scalar()
            
            last_price = db.query(Tick.price).filter(
                Tick.symbol_id == s.symbol_id,
                Tick.timestamp >= today_start
            ).order_by(Tick.timestamp.desc()).limit(1).scalar()
            
            change = (last_price - first_price) if last_price and first_price else 0
            change_pct = (change / first_price * 100) if first_price else 0
            
            option_stats.append({
                "option": option_name,
                "symbol_id": str(s.symbol_id),
                "tick_count": s.tick_count,
                "first_price": first_price,
                "last_price": last_price,
                "high": s.high,
                "low": s.low,
                "change": change,
                "change_pct": change_pct,
                "avg_oi": float(s.avg_oi or 0),
                "avg_iv": float(s.avg_iv or 0)
            })
        
        # 3. Time distribution (by hour)
        hour_counts_query = db.query(
            extract('hour', Tick.timestamp).label('hour'),
            func.count(Tick.id)
        ).filter(
            Tick.timestamp >= today_start
        ).group_by('hour').all()
        
        hour_counts = {int(h): count for h, count in hour_counts_query}
        
        # 4. Greeks summary
        greeks = db.query(
            func.avg(Tick.delta).label("avg_delta"),
            func.avg(Tick.theta).label("avg_theta"),
            func.avg(Tick.iv).label("avg_iv")
        ).filter(
            Tick.timestamp >= today_start
        ).first()
        
        # 5. Trading Performance (Include LIVE, PAPER, and SCALPING)
        # Include trades created today OR exited today
        today_trades = db.query(Trade).filter(
            (Trade.created_at >= today_start) | (Trade.exit_time >= today_start)
        ).all()
        
        # 6. Account Summary
        # Calculate opening balance: Settings + historical PnL before today
        historical_pnl_query = db.query(Trade).filter(
            Trade.status.in_([TradeStatus.CLOSED, TradeStatus.STOPPED_OUT, TradeStatus.TAKE_PROFIT, TradeStatus.TRAILING_SL]),
            Trade.exit_time < today_start
        ).all()
        historical_pnl = sum(t.pnl or 0 for t in historical_pnl_query)
        opening_balance = settings.account_size + historical_pnl
        
        total_trades = len(today_trades)
        # Include all completed trade statuses
        COMPLETED_STATUSES = [
            TradeStatus.CLOSED, 
            TradeStatus.STOPPED_OUT, 
            TradeStatus.TAKE_PROFIT, 
            TradeStatus.TRAILING_SL
        ]
        closed_trades = [t for t in today_trades if t.status in COMPLETED_STATUSES]
        winning_trades = [t for t in closed_trades if (t.pnl or 0) > 0]
        
        total_pnl = sum(t.pnl or 0 for t in closed_trades)
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
        
        # Calculate current equity
        current_equity = opening_balance + total_pnl
        
        # Breakdown by type
        live_trades = [t for t in today_trades if t.trade_type == "LIVE"]
        paper_trades = [t for t in today_trades if t.trade_type == "PAPER"]
        scalping_trades = [t for t in today_trades if t.trade_type == "SCALPING"]
        
        # Save report to file
        report = {
            "date": str(today),
            "generated_at": ist_now().isoformat(),
            "total_ticks": total_ticks,
            "opening_balance": opening_balance,
            "current_equity": current_equity,
            "unique_options": len(stats_query),
            "trading": {
                "total_trades": total_trades,
                "live_trades": len(live_trades),
                "paper_trades": len(paper_trades),
                "scalping_trades": len(scalping_trades),
                "closed_trades": len(closed_trades),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "trades": [
                    {
                        "id": str(t.id),
                        "type": t.trade_type,
                        "side": t.order_side,
                        "entry": t.entry_price,
                        "exit": t.exit_price,
                        "pnl": t.pnl,
                        "status": t.status
                    } for t in today_trades
                ]
            },
            "hour_distribution": hour_counts,
            "top_options": option_stats,
            "greeks": {
                "avg_delta": float(greeks.avg_delta or 0) if greeks else 0,
                "avg_theta": float(greeks.avg_theta or 0) if greeks else 0,
                "avg_iv": float(greeks.avg_iv or 0) if greeks else 0
            }
        }
        
        report_path = os.path.join(output_dir, "eod_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"✅ EOD Report saved to: {report_path}")
        return report
        
    except Exception as e:
        logger.error(f"❌ Error generating EOD report: {e}")
        return {"error": str(e), "date": str(ist_now().date())}
    finally:
        db.close()


def export_all_ticks_csv(output_path: Optional[str] = None) -> int:
    """
    Export all today's ticks to CSV file.
    
    Returns:
        Number of ticks exported
    """
    if output_path is None:
        today_str = ist_now().strftime('%Y-%m-%d')
        output_path = os.path.join(settings.log_dir, today_str, "all_ticks.csv")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    db = SessionLocal()
    
    try:
        today = ist_now().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        # Get subscribed options for names
        subscribed_options = db.query(SubscribedOption).all()
        symbol_to_name = {}
        for opt in subscribed_options:
            symbol = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
            if symbol:
                symbol_to_name[symbol.id] = opt.option_symbol
        
        # Get all ticks
        ticks = db.query(Tick).filter(
            Tick.timestamp >= today_start
        ).order_by(Tick.timestamp).all()
        
        with open(output_path, 'w') as f:
            # Header
            f.write("timestamp,option_name,price,delta,theta,gamma,vega,iv,oi,volume,bid,ask\n")
            
            for tick in ticks:
                option_name = symbol_to_name.get(tick.symbol_id, "Unknown")
                f.write(f"{tick.timestamp},{option_name},{tick.price},"
                       f"{tick.delta or ''},{tick.theta or ''},{tick.gamma or ''},"
                       f"{tick.vega or ''},{tick.iv or ''},{tick.oi or ''},"
                       f"{tick.volume or ''},{tick.bid or ''},{tick.ask or ''}\n")
        
        logger.info(f"✅ Exported {len(ticks):,} ticks to {output_path}")
        return len(ticks)
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--csv":
        export_all_ticks_csv()
    else:
        generate_end_of_day_report()
