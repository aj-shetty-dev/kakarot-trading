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
from typing import Dict, List, Any

from ..data.database import SessionLocal
from ..data.models import Tick, Symbol, SubscribedOption


def generate_end_of_day_report(output_dir: str = "/app/logs") -> Dict[str, Any]:
    """
    Generate end of day report with tick statistics.
    
    Returns:
        Dict with report data
    """
    db = SessionLocal()
    
    try:
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        print("=" * 60)
        print(f"📊 END OF DAY REPORT - {today}")
        print("=" * 60)
        
        # Get all today's ticks
        today_ticks = db.query(Tick).filter(
            Tick.timestamp >= today_start
        ).all()
        
        total_ticks = len(today_ticks)
        print(f"\n📈 Total Ticks Recorded: {total_ticks:,}")
        
        if total_ticks == 0:
            print("\n⚠️  No ticks recorded today (market may be closed)")
            return {"total_ticks": 0, "date": str(today)}
        
        # Group by symbol
        ticks_by_symbol: Dict[str, List[Tick]] = defaultdict(list)
        for tick in today_ticks:
            ticks_by_symbol[tick.symbol_id].append(tick)
        
        print(f"📊 Unique Options with Data: {len(ticks_by_symbol)}")
        
        # Get symbol details
        subscribed_options = db.query(SubscribedOption).all()
        symbol_to_option = {}
        for opt in subscribed_options:
            symbol = db.query(Symbol).filter(Symbol.symbol == opt.symbol).first()
            if symbol:
                symbol_to_option[symbol.id] = opt
        
        # Calculate statistics per option
        print("\n" + "-" * 60)
        print("TOP 20 OPTIONS BY TICK COUNT:")
        print("-" * 60)
        
        option_stats = []
        for symbol_id, ticks in ticks_by_symbol.items():
            opt = symbol_to_option.get(symbol_id)
            option_name = opt.option_symbol if opt else f"Unknown ({symbol_id})"
            
            prices = [t.price for t in ticks if t.price]
            
            if prices:
                stats = {
                    "option": option_name,
                    "symbol_id": str(symbol_id),
                    "tick_count": len(ticks),
                    "first_price": prices[0],
                    "last_price": prices[-1],
                    "high": max(prices),
                    "low": min(prices),
                    "change": prices[-1] - prices[0],
                    "change_pct": ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] else 0,
                    "avg_oi": sum(t.oi or 0 for t in ticks) / len(ticks),
                    "avg_iv": sum(t.iv or 0 for t in ticks) / len(ticks),
                }
                option_stats.append(stats)
        
        # Sort by tick count
        option_stats.sort(key=lambda x: x["tick_count"], reverse=True)
        
        # Print top 20
        for i, stat in enumerate(option_stats[:20], 1):
            change_symbol = "🟢" if stat["change"] >= 0 else "🔴"
            print(f"{i:2}. {stat['option'][:35]:<35} | "
                  f"Ticks: {stat['tick_count']:>5} | "
                  f"LTP: {stat['last_price']:>8.2f} | "
                  f"{change_symbol} {stat['change']:+.2f} ({stat['change_pct']:+.1f}%)")
        
        # Time distribution
        print("\n" + "-" * 60)
        print("TICK DISTRIBUTION BY HOUR:")
        print("-" * 60)
        
        hour_counts = defaultdict(int)
        for tick in today_ticks:
            hour = tick.timestamp.hour
            hour_counts[hour] += 1
        
        for hour in sorted(hour_counts.keys()):
            count = hour_counts[hour]
            bar = "█" * (count // 1000) if count >= 1000 else "▌" * (count // 500) or "·"
            # Convert to IST (UTC+5:30)
            ist_hour = (hour + 5) % 24
            ist_min = 30
            print(f"  {ist_hour:02d}:{ist_min:02d} IST: {count:>6,} ticks {bar}")
        
        # Summary by option type
        print("\n" + "-" * 60)
        print("SUMMARY BY OPTION TYPE:")
        print("-" * 60)
        
        ce_ticks = 0
        pe_ticks = 0
        for stat in option_stats:
            if "CE" in stat["option"]:
                ce_ticks += stat["tick_count"]
            elif "PE" in stat["option"]:
                pe_ticks += stat["tick_count"]
        
        print(f"  📈 CALL (CE) ticks: {ce_ticks:>10,}")
        print(f"  📉 PUT (PE) ticks:  {pe_ticks:>10,}")
        
        # Greeks summary
        print("\n" + "-" * 60)
        print("GREEKS SUMMARY (Average across all ticks):")
        print("-" * 60)
        
        all_deltas = [t.delta for t in today_ticks if t.delta]
        all_thetas = [t.theta for t in today_ticks if t.theta]
        all_ivs = [t.iv for t in today_ticks if t.iv]
        
        if all_deltas:
            print(f"  Δ Delta (avg):  {sum(all_deltas)/len(all_deltas):>8.4f}")
        if all_thetas:
            print(f"  θ Theta (avg):  {sum(all_thetas)/len(all_thetas):>8.4f}")
        if all_ivs:
            print(f"  IV (avg):       {sum(all_ivs)/len(all_ivs)*100:>7.2f}%")
        
        # Save report to file
        report = {
            "date": str(today),
            "generated_at": datetime.utcnow().isoformat(),
            "total_ticks": total_ticks,
            "unique_options": len(ticks_by_symbol),
            "ce_ticks": ce_ticks,
            "pe_ticks": pe_ticks,
            "hour_distribution": dict(hour_counts),
            "top_options": option_stats[:50],
            "all_options": option_stats
        }
        
        report_path = f"{output_dir}/eod_report_{today}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print("\n" + "=" * 60)
        print(f"✅ Report saved to: {report_path}")
        print("=" * 60)
        
        return report
        
    finally:
        db.close()


def export_all_ticks_csv(output_path: str = "/app/logs/all_ticks.csv") -> int:
    """
    Export all today's ticks to CSV file.
    
    Returns:
        Number of ticks exported
    """
    db = SessionLocal()
    
    try:
        today = datetime.utcnow().date()
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
        
        print(f"✅ Exported {len(ticks):,} ticks to {output_path}")
        return len(ticks)
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--csv":
        export_all_ticks_csv()
    else:
        generate_end_of_day_report()
