#!/usr/bin/env python3
"""
Phase 2 Live Dashboard
Display real-time market data from WebSocket integration
Uses only standard library (urllib) - no external dependencies
"""

import urllib.request
import json
import time
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class LiveDashboard:
    """Display live market data from Phase 2 WebSocket"""

    BASE_URL = "http://localhost:8000"

    def __init__(self):
        self.last_updates = 0

    def fetch_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON data from API endpoint"""
        try:
            url = f"{self.BASE_URL}{endpoint}"
            with urllib.request.urlopen(url, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
            return None

    def check_health(self) -> bool:
        """Check if app is running"""
        try:
            with urllib.request.urlopen(f"{self.BASE_URL}/health", timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def print_header(self, title: str):
        """Print section header"""
        print(f"\n{'═' * 80}")
        print(f" {title}")
        print(f"{'═' * 80}")

    def print_status(self):
        """Print WebSocket status"""
        self.print_header("📊 WEBSOCKET STATUS")

        status = self.fetch_json("/api/v1/websocket/status")
        if not status:
            print(" ❌ Failed to fetch status")
            return

        running = status.get("is_running", False)
        connected = status.get("websocket_connected", False)
        subs = status.get("subscriptions", {})

        print(f"\n Running:          {self._bool_icon(running)} {running}")
        print(f" Connected:        {self._bool_icon(connected)} {connected}")

        if subs:
            print(f"\n 📋 SUBSCRIPTIONS:")
            print(f"    Total Symbols:    {subs.get('total_symbols', 0)}")
            print(f"    Subscribed:       {subs.get('subscribed_count', 0)}")
            print(f"    Failed:           {subs.get('failed_count', 0)}")
            print(f"    Success Rate:     {subs.get('subscription_rate', 'N/A')}")

        symbols = status.get("subscribed_symbols", [])
        if symbols:
            print(f"\n 🔤 SAMPLE SYMBOLS (first 10):")
            for sym in symbols[:10]:
                print(f"    • {sym}")
            if len(symbols) > 10:
                print(f"    ... and {len(symbols) - 10} more")

    def print_market_data(self):
        """Print current market data"""
        self.print_header("📈 MARKET DATA")

        ticks = self.fetch_json("/api/v1/websocket/latest-ticks")
        if not ticks:
            print(" ❌ Failed to fetch market data")
            return

        symbols_tracked = ticks.get("symbols_tracked", 0)
        updates = ticks.get("price_updates", 0)

        print(f"\n Symbols Tracked:  {symbols_tracked}")
        print(f" Price Updates:    {updates:,}")

        if updates > 0:
            print(f"\n {self._success_icon()} Data is flowing!")
        else:
            print(f"\n ⏳ Waiting for market data...")

    def print_performance(self):
        """Print performance metrics"""
        self.print_header("⚡ PERFORMANCE")

        ticks = self.fetch_json("/api/v1/websocket/latest-ticks")
        if not ticks:
            print(" ❌ Failed to fetch performance data")
            return

        updates = ticks.get("price_updates", 0)
        print(f"\n Price Updates:    {updates:,}")

        if updates > 1000:
            print(f" Throughput:       🟢 Excellent (>1000 updates)")
        elif updates > 100:
            print(f" Throughput:       🟡 Good ({updates} updates)")
        elif updates > 0:
            print(f" Throughput:       🟠 Limited ({updates} updates)")
        else:
            print(f" Throughput:       🔴 No data")

    def continuous_monitor(self, duration_seconds: int = 60):
        """Monitor live updates"""
        self.print_header(f"🔄 LIVE MONITORING ({duration_seconds}s)")

        print("\n Monitoring updates... (Press Ctrl+C to stop)\n")

        start_time = time.time()
        end_time = start_time + duration_seconds

        try:
            while time.time() < end_time:
                ticks = self.fetch_json("/api/v1/websocket/latest-ticks")

                if ticks:
                    updates = ticks.get("price_updates", 0)
                    symbols = ticks.get("symbols_tracked", 0)

                    if updates != self.last_updates:
                        elapsed = time.time() - start_time
                        rate = updates / elapsed if elapsed > 0 else 0

                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(
                            f" [{timestamp}] Updates: {updates:8d} | "
                            f"Rate: {rate:6.1f} up/s | Symbols: {symbols:3d}"
                        )
                        self.last_updates = updates

                time.sleep(2)

        except KeyboardInterrupt:
            print("\n ⏸️  Monitoring stopped")

        print(f"\n ✅ Monitoring complete")

    @staticmethod
    def _bool_icon(value: bool) -> str:
        """Get icon for boolean value"""
        return "✅" if value else "❌"

    @staticmethod
    def _success_icon() -> str:
        """Get success icon"""
        return "✅"

    def run(self):
        """Run dashboard"""
        print("\n╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║                  🎯 PHASE 2 LIVE DASHBOARD                                    ║")
        print("║                   WebSocket Market Data Verification                         ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")

        # Check health
        print(f"\n🔍 Checking application health...", end="", flush=True)
        if not self.check_health():
            print(f"\n❌ Application not running at {self.BASE_URL}")
            print("\nStart with:")
            print("  cd /Users/shetta20/Projects/upstox/backend")
            print("  docker-compose up")
            sys.exit(1)

        print(f" ✅ OK")

        # Display status
        self.print_status()
        self.print_market_data()
        self.print_performance()

        # Ask about monitoring
        print("\n" + "─" * 80)
        response = input("\nMonitor live data for 30 seconds? (y/n): ").lower().strip()

        if response in ["y", "yes"]:
            self.continuous_monitor(30)

        print("\n╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║                      ✅ DASHBOARD COMPLETE                                   ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝\n")


def main():
    """Main entry point"""
    dashboard = LiveDashboard()
    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
