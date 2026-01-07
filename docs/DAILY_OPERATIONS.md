# Daily Operations Guide 🚀

This guide provides quick commands for daily tasks such as updating tokens and restarting the system.

## 1. Update Upstox Access Token
The access token expires daily. When you have a new token from the Upstox dashboard:

### Option A: Manual Edit (Recommended)
1. Open the file [backend/.env](../backend/.env).
2. Find the line starting with `upstox_access_token=`.
3. Replace the old token with your new one.
4. Save the file.

### Option B: Terminal Command (Fast)
If you are in the project root, run this command (replace `YOUR_NEW_TOKEN` with the actual token):
```bash
sed -i '' 's/upstox_access_token=.*/upstox_access_token=YOUR_NEW_TOKEN/' backend/.env
```

---

## 2. Stopping the Application
To shut down all services (App, Database, Dashboard, Redis):
```bash
docker-compose down
```

---

## 3. Starting / Restarting the Application
After updating the token or configuration, you must restart the app to apply changes.

### Quick Restart (Just the App)
If the database is already running and you only updated the token:
```bash
docker-compose restart app
```

### Full Start (Fresh)
To ensure everything is rebuilt and fresh:
```bash
./dev.sh
```
*Alternatively:* `docker-compose up -d`

---

## 4. Monitoring the Bot
Once started, you can verify the bot is running by checking the logs:

**Live Logs:**
```bash
tail -f backend/logs/$(date +%Y-%m-%d)/system/app.log
```

**Dashboard:**
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 5. Daily Checklist
1. ✅ Get new Upstox Token.
2. ✅ Update `backend/.env`.
3. ✅ Run `docker-compose restart app`.
4. ✅ Check `app.log` for "SUCCESS WebSocket client initialized".
