#!/bin/bash
# Phase 2 Verification - Live Market Data Checker
# No dependencies needed - uses curl to check WebSocket integration

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:8000"

print_banner() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                 🎯 PHASE 2 WEBSOCKET VERIFICATION                             ║"
    echo "║                    Real-Time Market Data Integration Test                     ║"
    echo "╚════════════════════════════════════════════════════════════════════════════════╝"
    echo ""
}

check_health() {
    echo -e "${BLUE}🔍 Checking application health...${NC}"
    
    if ! response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" 2>/dev/null); then
        echo -e "${RED}❌ Cannot connect to $BASE_URL${NC}"
        echo ""
        echo "Make sure the app is running:"
        echo "  cd /Users/shetta20/Projects/upstox/backend"
        echo "  docker-compose up"
        return 1
    fi
    
    if [ "$response" = "200" ]; then
        echo -e "${GREEN}✅ Application is running${NC}"
        return 0
    else
        echo -e "${RED}❌ Application returned status $response${NC}"
        return 1
    fi
}

check_websocket_status() {
    echo ""
    echo -e "${BLUE}📡 Fetching WebSocket status...${NC}"
    echo "─────────────────────────────────────────────────────────────────────────────────"
    
    status=$(curl -s "$BASE_URL/api/v1/websocket/status")
    
    if [ -z "$status" ]; then
        echo -e "${RED}❌ Failed to get WebSocket status${NC}"
        return 1
    fi
    
    is_running=$(echo "$status" | grep -o '"is_running":[^,}]*' | cut -d: -f2)
    is_connected=$(echo "$status" | grep -o '"websocket_connected":[^,}]*' | cut -d: -f2)
    
    echo "Running:          $is_running"
    echo "Connected:        $is_connected"
    
    # Extract subscription stats
    total=$(echo "$status" | grep -o '"total_symbols":[^,}]*' | cut -d: -f2)
    subscribed=$(echo "$status" | grep -o '"subscribed_count":[^,}]*' | cut -d: -f2)
    failed=$(echo "$status" | grep -o '"failed_count":[^,}]*' | cut -d: -f2)
    rate=$(echo "$status" | grep -o '"subscription_rate":"[^"]*"' | cut -d'"' -f4)
    
    echo ""
    echo "📋 Subscriptions:"
    echo "  Total Symbols:    $total"
    echo "  Subscribed:       $subscribed"
    echo "  Failed:           $failed"
    echo "  Success Rate:     $rate"
}

check_latest_ticks() {
    echo ""
    echo -e "${BLUE}📈 Fetching latest market data...${NC}"
    echo "─────────────────────────────────────────────────────────────────────────────────"
    
    ticks=$(curl -s "$BASE_URL/api/v1/websocket/latest-ticks")
    
    if [ -z "$ticks" ]; then
        echo -e "${RED}❌ Failed to get latest ticks${NC}"
        return 1
    fi
    
    symbols_tracked=$(echo "$ticks" | grep -o '"symbols_tracked":[^,}]*' | cut -d: -f2)
    updates=$(echo "$ticks" | grep -o '"price_updates":[^,}]*' | cut -d: -f2)
    
    echo "Symbols Tracked:  $symbols_tracked"
    echo "Price Updates:    $updates"
    
    if [ "$updates" -gt 0 ]; then
        echo -e "\n${GREEN}✅ Data is flowing! Latest prices available.${NC}"
    else
        echo -e "\n${YELLOW}⏳ Waiting for market data to arrive...${NC}"
    fi
}

continuous_monitor() {
    local duration=${1:-30}
    
    echo ""
    echo -e "${BLUE}🔄 CONTINUOUS MONITORING (${duration}s)${NC}"
    echo "─────────────────────────────────────────────────────────────────────────────────"
    
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    local last_updates=0
    
    while [ $(date +%s) -lt $end_time ]; do
        ticks=$(curl -s "$BASE_URL/api/v1/websocket/latest-ticks")
        
        if [ -n "$ticks" ]; then
            updates=$(echo "$ticks" | grep -o '"price_updates":[^,}]*' | cut -d: -f2)
            symbols=$(echo "$ticks" | grep -o '"symbols_tracked":[^,}]*' | cut -d: -f2)
            
            if [ "$updates" != "$last_updates" ]; then
                timestamp=$(date '+%H:%M:%S')
                elapsed=$(($(date +%s) - start_time))
                if [ $elapsed -gt 0 ]; then
                    rate=$((updates / elapsed))
                else
                    rate=0
                fi
                
                printf "[%s] Updates: %8d | Rate: %6d upd/sec | Symbols: %3d\n" \
                    "$timestamp" "$updates" "$rate" "$symbols"
                last_updates=$updates
            fi
        fi
        
        sleep 2
    done
    
    echo ""
    echo -e "${GREEN}✅ Monitoring complete${NC}"
}

show_sample_prices() {
    echo ""
    echo -e "${BLUE}💹 Sample Current Prices (if available)${NC}"
    echo "─────────────────────────────────────────────────────────────────────────────────"
    
    ticks=$(curl -s "$BASE_URL/api/v1/websocket/latest-ticks")
    
    # Try to extract a few symbols (this is simplified - full JSON parsing would need jq)
    if echo "$ticks" | grep -q "latest_ticks"; then
        echo -e "${YELLOW}Note: Full price data requires jq (JSON processor)${NC}"
        echo "Install with: brew install jq"
        echo ""
        echo "Then run:"
        echo "  curl -s http://localhost:8000/api/v1/websocket/latest-ticks | jq '.latest_ticks | to_entries[:5]'"
    else
        echo "No tick data yet. Market may not be open or data not flowing yet."
    fi
}

show_help() {
    echo ""
    echo "Usage: ./verify_phase2.sh [OPTION]"
    echo ""
    echo "Options:"
    echo "  health              Check if app is running"
    echo "  status              Get WebSocket status"
    echo "  ticks               Get latest tick data"
    echo "  monitor [SECONDS]   Monitor live data (default: 30 seconds)"
    echo "  full                Run complete verification (default)"
    echo "  help                Show this help message"
    echo ""
}

main() {
    print_banner
    
    case "${1:-full}" in
        health)
            check_health
            ;;
        status)
            check_health && check_websocket_status
            ;;
        ticks)
            check_health && check_latest_ticks && show_sample_prices
            ;;
        monitor)
            check_health && continuous_monitor "${2:-30}"
            ;;
        full)
            if check_health; then
                check_websocket_status
                check_latest_ticks
                show_sample_prices
            fi
            ;;
        help)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                      ✅ VERIFICATION COMPLETE                                 ║"
    echo "╚════════════════════════════════════════════════════════════════════════════════╝"
    echo ""
}

main "$@"
