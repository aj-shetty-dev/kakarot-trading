#!/usr/bin/env python3
"""
Phase 2 Verification Demo
Test script to verify WebSocket integration is working
Gets real market data and displays current values
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
CHECK_INTERVAL = 5  # seconds


class Phase2Verifier:
    """Verify Phase 2 WebSocket implementation is working"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket_status = None
        self.latest_ticks = None
        self.subscriptions = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def check_health(self) -> bool:
        """Check if app is running"""
        try:
            async with self.session.get(f"{BASE_URL}/health") as resp:
                if resp.status == 200:
                    return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
        return False

    async def get_websocket_status(self) -> Optional[Dict[str, Any]]:
        """Get WebSocket connection status"""
        try:
            async with self.session.get(
                f"{BASE_URL}/api/v1/websocket/status"
            ) as resp:
                if resp.status == 200:
                    self.websocket_status = await resp.json()
                    return self.websocket_status
        except Exception as e:
            print(f"❌ Failed to get WebSocket status: {e}")
        return None

    async def get_subscriptions(self) -> Optional[Dict[str, Any]]:
        """Get subscription details"""
        try:
            async with self.session.get(
                f"{BASE_URL}/api/v1/websocket/subscriptions"
            ) as resp:
                if resp.status == 200:
                    self.subscriptions = await resp.json()
                    return self.subscriptions
        except Exception as e:
            print(f"❌ Failed to get subscriptions: {e}")
        return None

    async def get_latest_ticks(self) -> Optional[Dict[str, Any]]:
        """Get latest tick data"""
        try:
            async with self.session.get(
                f"{BASE_URL}/api/v1/websocket/latest-ticks"
            ) as resp:
                if resp.status == 200:
                    self.latest_ticks = await resp.json()
                    return self.latest_ticks
        except Exception as e:
            print(f"❌ Failed to get latest ticks: {e}")
        return None

    def print_banner(self):
        """Print header banner"""
        print("\n" + "=" * 80)
        print("🎯 PHASE 2 WEBSOCKET VERIFICATION".center(80))
        print("Real-Time Market Data Integration Test".center(80))
        print("=" * 80 + "\n")

    def print_status_check(self):
        """Print status check results"""
        print("\n📊 WEBSOCKET STATUS")
        print("-" * 80)

        if self.websocket_status:
            print(f"  Running:          {self.websocket_status.get('is_running')}")
            print(f"  Connected:        {self.websocket_status.get('websocket_connected')}")

            subs = self.websocket_status.get("subscriptions", {})
            if subs:
                print(f"\n  📋 Subscriptions:")
                print(f"    Total Symbols:    {subs.get('total_symbols')}")
                print(f"    Subscribed:       {subs.get('subscribed_count')}")
                print(f"    Failed:           {subs.get('failed_count')}")
                print(f"    Success Rate:     {subs.get('subscription_rate')}")

            symbols = self.websocket_status.get("subscribed_symbols", [])
            if symbols:
                print(f"\n  🔤 Sample Symbols (first 10):")
                for sym in symbols[:10]:
                    print(f"    • {sym}")
                if len(symbols) > 10:
                    print(f"    ... and {len(symbols) - 10} more")
        else:
            print("  ❌ No status data available")

    def print_ticker_data(self):
        """Print latest ticker data"""
        print("\n\n📈 LATEST MARKET DATA (In-Memory Cache)")
        print("-" * 80)

        if not self.latest_ticks:
            print("  ❌ No tick data available")
            return

        print(f"  Symbols Tracked:  {self.latest_ticks.get('symbols_tracked', 0)}")
        print(f"  Price Updates:    {self.latest_ticks.get('price_updates', 0)}")

        ticks = self.latest_ticks.get("latest_ticks", {})
        if ticks:
            print(f"\n  Current Prices:")
            symbol_list = list(ticks.keys())[:5]  # Show first 5
            for symbol in symbol_list:
                tick = ticks[symbol]
                print(f"\n    {symbol}:")
                print(f"      Price:    ₹{tick.get('price', 0):,.2f}")
                print(f"      Volume:   {tick.get('volume', 0):,}")
                print(f"      Bid/Ask:  {tick.get('bid', 0):,.2f} / {tick.get('ask', 0):,.2f}")
                print(f"      Updated:  {tick.get('timestamp')}")

            if len(ticks) > 5:
                print(f"\n    ... and {len(ticks) - 5} more symbols")
        else:
            print("  No tick data in cache yet (waiting for market data)")

    def print_performance_metrics(self):
        """Print performance metrics"""
        print("\n\n⚡ PERFORMANCE METRICS")
        print("-" * 80)

        if self.latest_ticks:
            updates = self.latest_ticks.get("price_updates", 0)
            print(f"  Price Updates:    {updates:,}")
            if updates > 0:
                print(f"  ✅ Data flowing correctly!")
        else:
            print("  ⏳ Waiting for market data...")

        if self.websocket_status:
            subs = self.websocket_status.get("subscriptions", {})
            if subs:
                rate = subs.get("subscription_rate", "0%")
                print(f"  Subscription Rate: {rate}")

    async def run_verification(self):
        """Run complete verification"""
        self.print_banner()

        # Check if app is running
        print("🔍 Checking application health...")
        if not await self.check_health():
            print("❌ Application not running!")
            print("\nStart the app with:")
            print("  cd /Users/shetta20/Projects/upstox/backend")
            print("  docker-compose up")
            return False

        print("✅ Application is running\n")

        # Get status data
        print("📡 Fetching WebSocket data...")
        await self.get_websocket_status()
        await self.get_subscriptions()
        await self.get_latest_ticks()

        # Print results
        self.print_status_check()
        self.print_ticker_data()
        self.print_performance_metrics()

        return True

    async def continuous_monitor(self, duration_seconds: int = 60):
        """Monitor live data for a duration"""
        print(f"\n\n🔄 CONTINUOUS MONITORING ({duration_seconds}s)")
        print("-" * 80)

        start_time = datetime.now()
        end_time = start_time + asyncio.timedelta(seconds=duration_seconds)

        update_count = 0

        while datetime.now() < end_time:
            await self.get_latest_ticks()

            if self.latest_ticks:
                updates = self.latest_ticks.get("price_updates", 0)
                symbols = self.latest_ticks.get("symbols_tracked", 0)

                if updates != update_count:
                    update_count = updates
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = update_count / elapsed if elapsed > 0 else 0

                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"Updates: {updates:,} | "
                        f"Rate: {rate:.1f} updates/sec | "
                        f"Symbols: {symbols}"
                    )

            await asyncio.sleep(CHECK_INTERVAL)

        print("\n✅ Monitoring complete")


async def main():
    """Main entry point"""
    async with Phase2Verifier() as verifier:
        # Run initial verification
        success = await verifier.run_verification()

        if success:
            # Option to run continuous monitoring
            try:
                print("\n\n" + "=" * 80)
                print("Monitor live data? (Press Ctrl+C to skip)".center(80))
                print("=" * 80)
                await asyncio.sleep(3)
                await verifier.continuous_monitor(duration_seconds=30)
            except KeyboardInterrupt:
                print("\n⏸️  Monitoring skipped")
            except Exception as e:
                print(f"Error during monitoring: {e}")

        print("\n" + "=" * 80)
        print("✅ VERIFICATION COMPLETE".center(80))
        print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Verification interrupted")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
