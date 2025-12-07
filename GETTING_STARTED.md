# Getting Started Guide

## 🎯 Quick Start (5 minutes)

### 1. Verify Your Setup
```bash
# Check if Docker is running
docker --version
docker-compose --version
```

### 2. Start All Services
```bash
cd /Users/shetta20/Projects/upstox
docker-compose up -d
```

### 3. Check Services Status
```bash
docker-compose ps
```

You should see:
- ✅ `upstox_postgres` - Running on port 5432
- ✅ `upstox_redis` - Running on port 6379  
- ✅ `upstox_trading_bot` - Running on port 8000

### 4. View API Documentation
Open in browser: **http://localhost:8000/docs**

### 5. Check Logs
```bash
# FastAPI app logs
docker-compose logs app

# PostgreSQL logs
docker-compose logs postgres

# Follow logs in real-time
docker-compose logs -f app
```

---

## 📝 Configuration

Your `.env` file is ready with:
- ✅ Upstox API credentials
- ✅ Trading parameters
- ✅ Database connection
- ✅ Logging settings

**All parameters can be changed anytime** - just edit `.env` and restart the container:
```bash
docker-compose down
docker-compose up -d
```

---

## 🗄️ Database Access

### Connect to PostgreSQL
```bash
docker-compose exec postgres psql -U upstox_user -d upstox_trading
```

### Useful SQL commands
```sql
-- See all tables
\dt

-- Check symbols table
SELECT * FROM symbols LIMIT 5;

-- Check signals table
SELECT * FROM signals ORDER BY detected_at DESC LIMIT 5;

-- Exit
\q
```

---

## 🔍 Verify Installation

### Check if tables exist
```bash
docker-compose exec postgres psql -U upstox_user -d upstox_trading -c "\dt"
```

### Check API health
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "development",
  "paper_trading": true
}
```

---

## ⚠️ Common Issues

### Issue: Port already in use
```bash
# If port 5432 is in use by local PostgreSQL
# Change in docker-compose.yml: "5432:5432" to "5433:5432"
# Then: DATABASE_URL=postgresql://upstox_user:upstox_password@localhost:5433/upstox_trading
```

### Issue: Docker not running
```bash
# Start Docker daemon
# macOS: Click Docker icon
# Linux: sudo systemctl start docker
```

### Issue: Module import errors
```bash
# Rebuild Docker image with latest dependencies
docker-compose build --no-cache
docker-compose up -d
```

---

## 📚 Useful Resources

- **API Docs**: http://localhost:8000/docs (interactive)
- **API Schema**: http://localhost:8000/redoc (read-only)
- **Configuration**: `backend/.env`
- **Implementation Plan**: `IMPLEMENTATION_PLAN.md`
- **Phase 1 Summary**: `PHASE_1_COMPLETE.md`

---

## 🚀 Next Phase: WebSocket Integration

Once verified, we'll build:
1. Upstox WebSocket client for real-time data
2. Price tick streaming and storage
3. Greeks calculation (options pricing)
4. Real-time data pipeline

---

## 💡 Pro Tips

1. **Always use Docker** - Keeps your system clean
2. **Keep `.env` secure** - It has your API credentials
3. **Monitor logs** - Use `docker-compose logs -f` while testing
4. **Test endpoints** - Use http://localhost:8000/docs for API testing
5. **Back up database** - PostgreSQL data in `postgres_data/` directory

---

## ❓ Need Help?

1. Check logs: `docker-compose logs app`
2. Verify configuration: `docker-compose exec app cat .env`
3. Test database: `docker-compose exec postgres psql -U upstox_user -d upstox_trading`

---

**Status**: ✅ Phase 1 Complete - Ready for Phase 2!

Ready to start? Run:
```bash
cd /Users/shetta20/Projects/upstox
docker-compose up -d
```

Let me know when services are running! 🎯
