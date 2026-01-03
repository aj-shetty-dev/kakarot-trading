# Upstox Trading Bot - Operations & Management Guide

> Last Updated: December 18, 2025  
> Project: `/Users/shetta20/Projects/upstox`

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Scheduled Mode (9 AM - 4 PM)](#scheduled-mode-9-am---4-pm)
3. [Continuous Mode](#continuous-mode)
4. [Status & Monitoring](#status--monitoring)
5. [Troubleshooting](#troubleshooting)
6. [File Reference](#file-reference)

---

## 🚀 Quick Start

### Option 1: Scheduled Mode (Recommended for Battery Life)
Runs automatically at 9 AM, stops at 4 PM (Weekdays only)

```bash
# Enable scheduled startup & shutdown
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.stop.plist

# Check if services are loaded
launchctl list | grep upstox
```

### Option 2: Continuous Mode
Runs immediately and stays running (uses more battery)

```bash
# Enable continuous startup (not recommended)
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.plist
```

---

## 📅 Scheduled Mode (9 AM - 4 PM)

This is the **recommended configuration** for NSE trading hours.

### How It Works

| Time | Action | Details |
|------|--------|---------|
| **Daily 12:01 AM (Midnight)** | Wake Timer Set | Sets wake timer for next day at 8:55 AM IST (3:25 AM UTC) |
| **Daily 8:55 AM** | Mac Wakes | Mac automatically wakes from sleep (if sleeping) |
| **Daily 9:00 AM** | Bot Starts | Containers launch, caffeinate activates, data recording begins |
| **Daily 4:00 PM** | Bot Stops | Containers shutdown, caffeinate releases, Mac can sleep |
| **Weekends** | Idle | No automatic startup on Saturday/Sunday |

### Why 8:55 AM Wake Timer?

Since launchd doesn't execute jobs while the Mac is sleeping, we use a wake timer to ensure the Mac is awake before the 9:00 AM bot startup. The 5-minute buffer (8:55 AM) gives the Mac time to fully wake before the scheduled job runs.

### Services

**Wake Timer Service:**
- File: `/Users/shetta20/Library/LaunchAgents/com.upstox.wake-timer.plist`
- Script: `/Users/shetta20/Projects/upstox/set-wake-timer.sh`
- Schedule: Daily at 12:01 AM (midnight)
- Action: Sets wake timer for 8:55 AM IST (3:25 AM UTC)

**Start Service:**
- File: `/Users/shetta20/Library/LaunchAgents/com.upstox.trading-bot.start.plist`
- Script: `/Users/shetta20/Projects/upstox/start-trading-hours.sh`
- Schedule: Monday-Friday at 9:00 AM

**Stop Service:**
- File: `/Users/shetta20/Library/LaunchAgents/com.upstox.trading-bot.stop.plist`
- Script: `/Users/shetta20/Projects/upstox/stop-trading-hours.sh`
- Schedule: Monday-Friday at 4:00 PM

### Logs

```bash
# View today's startup events
tail -f /Users/shetta20/Projects/upstox/logs/startup_$(date +%Y-%m-%d).log

# View all trading hours logs
tail -f /Users/shetta20/Projects/upstox/logs/trading-hours_$(date +%Y-%m-%d).log
```

### Management Commands

```bash
# Enable all services (wake timer + start + stop)
launchctl load ~/Library/LaunchAgents/com.upstox.wake-timer.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.stop.plist

# Disable all services
launchctl unload ~/Library/LaunchAgents/com.upstox.wake-timer.plist
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.stop.plist

# Check if all services are loaded
launchctl list | grep upstox

# Reload (apply changes)
launchctl unload ~/Library/LaunchAgents/com.upstox.wake-timer.plist
launchctl load ~/Library/LaunchAgents/com.upstox.wake-timer.plist
```

### Check Wake Timer Status

```bash
# View scheduled wake timers
pmset -g sched

# Cancel a specific wake timer (if needed)
sudo pmset schedule cancelall

# View wake timer logs
tail -f /Users/shetta20/Projects/upstox/logs/wake-timer_$(date +%Y-%m-%d).log
```

---

## 🔄 Continuous Mode

Starts the bot immediately and keeps it running (24/7).

**⚠️ WARNING:** This drains battery continuously. Use only if necessary.

### Service

- File: `/Users/shetta20/Library/LaunchAgents/com.upstox.trading-bot.plist`
- Script: `/Users/shetta20/Projects/upstox/start-app.sh`
- Schedule: Automatically at Mac startup

### Management

```bash
# Enable (runs at next Mac restart)
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.plist

# Disable
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.plist

# Check status
launchctl list | grep com.upstox.trading-bot

# View logs
tail -f /Users/shetta20/Projects/upstox/logs/startup.log
```

---

## 📊 Status & Monitoring

### Quick Status Check

```bash
./check-status.sh
```

**Output includes:**
1. ✅ Launchd service status
2. ✅ Docker containers status
3. ✅ Caffeinate status (is Mac being kept awake?)
4. ✅ Data recording status (latest log file & size)
5. ✅ Application logs (last 5 entries)

### Manual Commands

```bash
# Check which services are loaded
launchctl list | grep upstox

# View all Docker containers
docker ps -a

# Check if specific containers are running
docker ps | grep upstox_

# View Docker logs
docker logs upstox_trading_bot

# View data recording files
ls -lh /Users/shetta20/Projects/upstox/backend/logs/live_prices*

# Check latest data file
ls -lh /Users/shetta20/Projects/upstox/backend/logs/live_prices_$(date +%Y-%m-%d).*

# Stream latest recordings in real-time
tail -f /Users/shetta20/Projects/upstox/backend/logs/live_prices_2025-12-18.jsonl
```

### Check Caffeinate Status

```bash
# Check if caffeinate is running
pgrep -f "caffeinate.*docker-compose"

# Kill caffeinate manually (if needed)
pkill -f "caffeinate.*docker-compose"
```

---

## 🔧 Troubleshooting

### Service Won't Start

```bash
# 1. Check if the plist file exists and is valid
cat ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist

# 2. Reload the service
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist

# 3. Check for errors
launchctl list | grep upstox
tail -f /Users/shetta20/Projects/upstox/logs/launchd-start.log
tail -f /Users/shetta20/Projects/upstox/logs/launchd-error.log
```

### Docker Containers Not Starting

```bash
# 1. Check if Docker daemon is running
docker info

# 2. If Docker is not running, start it
# Manual: Open Docker Desktop app

# 3. Check logs
tail -f /Users/shetta20/Projects/upstox/logs/trading-hours.log

# 4. Check if containers are stuck
docker ps -a | grep upstox

# 5. Force stop and restart
docker-compose down
docker-compose up -d
```

### Data Not Recording

```bash
# 1. Check if containers are running
./check-status.sh

# 2. Check if token is valid
# The .env file has token that may have expired
cat /Users/shetta20/Projects/upstox/backend/.env | grep UPSTOX_ACCESS_TOKEN

# 3. View container logs
docker logs upstox_trading_bot | tail -50

# 4. Check data recording directory
ls -lh /Users/shetta20/Projects/upstox/backend/logs/

# 5. If no recent files, check WebSocket errors
docker logs upstox_trading_bot 2>&1 | grep -i error
```

### Mac Keeps Going to Sleep

```bash
# 1. Verify caffeinate is running
pgrep -f "caffeinate.*docker-compose"

# 2. If not running during market hours, check logs
tail -f /Users/shetta20/Projects/upstox/logs/trading-hours.log

# 3. Manually activate caffeinate
caffeinate -i docker-compose logs -f

# 4. Check battery status
pmset -g batt
```

### Too Much Battery Drain

```bash
# 1. Use scheduled mode instead of continuous
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.stop.plist

# 2. Verify bot stops at 4 PM
launchctl list | grep upstox

# 3. Check if caffeinate stops after 4 PM
pgrep -f "caffeinate" # Should return nothing after 4 PM
```

---

## 📁 File Reference

### Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| `start-trading-hours.sh` | Starts bot at 9 AM | `/Users/shetta20/Projects/upstox/` |
| `stop-trading-hours.sh` | Stops bot at 4 PM | `/Users/shetta20/Projects/upstox/` |
| `start-app.sh` | Starts bot continuously (24/7) | `/Users/shetta20/Projects/upstox/` |
| `check-status.sh` | Checks bot & system status | `/Users/shetta20/Projects/upstox/` |

### Launchd Configuration Files

| File | Purpose | Schedule |
|------|---------|----------|
| `com.upstox.wake-timer.plist` | Wake timer service | Daily 12:01 AM |
| `com.upstox.trading-bot.start.plist` | Scheduled start service | 9 AM Mon-Fri |
| `com.upstox.trading-bot.stop.plist` | Scheduled stop service | 4 PM Mon-Fri |
| `com.upstox.trading-bot.plist` | Continuous service (24/7) | At Mac startup |

**Location:** `~/Library/LaunchAgents/`

### Logs

| Log | Purpose | Location |
|-----|---------|----------|
| `startup_YYYY-MM-DD.log` | Startup events (continuous mode) | `logs/` |
| `trading-hours_YYYY-MM-DD.log` | Trading hours events (scheduled mode) | `logs/` |

**Location:** `/Users/shetta20/Projects/upstox/logs/`

All logs are dated with `YYYY-MM-DD` so you can easily identify which files were created today.

### Data Recording

| File Type | Purpose | Location |
|-----------|---------|----------|
| `live_prices_YYYY-MM-DD.jsonl` | Live price records (JSON) | `backend/logs/` |
| `live_prices_YYYY-MM-DD.log` | Live price logs | `backend/logs/` |
| `live_prices_YYYY-MM-DD.toon` | Live price data (binary) | `backend/logs/` |

---

## 🎯 Common Workflows

### Start Bot Manually (Right Now)

```bash
cd /Users/shetta20/Projects/upstox
./start-trading-hours.sh
```

### Stop Bot Manually

```bash
cd /Users/shetta20/Projects/upstox
./stop-trading-hours.sh
```

### Switch from Continuous to Scheduled Mode

```bash
# Disable continuous
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.plist

# Enable scheduled
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.stop.plist

# Verify
launchctl list | grep upstox
```

### Check Data for Today

```bash
# View size and modification time
ls -lh ~/Projects/upstox/backend/logs/live_prices_$(date +%Y-%m-%d).*

# Stream live updates
tail -f ~/Projects/upstox/backend/logs/live_prices_$(date +%Y-%m-%d).jsonl

# Count records
wc -l ~/Projects/upstox/backend/logs/live_prices_$(date +%Y-%m-%d).jsonl
```

### Full System Check (Before Trading)

```bash
cd /Users/shetta20/Projects/upstox

# 1. Check status
./check-status.sh

# 2. View recent logs
tail -20 logs/trading-hours.log

# 3. Ensure services are loaded for today
launchctl list | grep upstox

# 4. Check Docker
docker ps | grep upstox_

# 5. If all ✅, ready for trading!
```

---

## 📞 Quick Reference

```bash
# === STATUS ===
./check-status.sh                              # Full status
launchctl list | grep upstox                   # Services status
docker ps                                       # Running containers

# === LOGS ===
tail -f logs/trading-hours_$(date +%Y-%m-%d).log           # Today's trading log
tail -f logs/startup_$(date +%Y-%m-%d).log                 # Today's startup log
tail -f backend/logs/live_prices_$(date +%Y-%m-%d).jsonl   # Today's data stream

# === MANAGEMENT ===
./start-trading-hours.sh                       # Start manually
./stop-trading-hours.sh                        # Stop manually
launchctl load ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist    # Enable start
launchctl unload ~/Library/LaunchAgents/com.upstox.trading-bot.start.plist   # Disable start

# === DOCKER ===
docker-compose up -d                           # Start containers
docker-compose down                            # Stop containers
docker ps -a                                    # Show all containers
docker logs upstox_trading_bot                 # Bot logs

# === DATA ===
ls -lh backend/logs/live_prices*               # List recordings
wc -l backend/logs/live_prices_2025-12-18.jsonl  # Count records
tail -f backend/logs/live_prices_$(date +%Y-%m-%d).jsonl  # Live stream
```

---

## 🔐 Security Notes

- **Token Expiry**: Access token expires daily at 3:30 AM
  - Update in: `/Users/shetta20/Projects/upstox/backend/.env`
  - See: `UPSTOX_ACCESS_TOKEN`

- **Credentials**: Never commit `.env` file to git
  - Already in `.gitignore`

- **Logs**: May contain sensitive trading data
  - Location: `logs/` and `backend/logs/`

---

## ✅ Checklist for Production

- [ ] Token is updated in `.env`
- [ ] Scheduled services are loaded
- [ ] Data recording folder has space (check `du -sh backend/logs/`)
- [ ] Docker Desktop is set to auto-start
- [ ] Check-status.sh shows all ✅
- [ ] Test data recording manually once
- [ ] Review logs before first automatic run

---

**Questions?** Check logs first, then troubleshooting section above.

