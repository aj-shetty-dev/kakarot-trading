import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime
import os

# Page config
st.set_page_config(
    page_title="Upstox Bot Dashboard",
    page_icon="📈",
    layout="wide"
)

# API Base URL (internal docker network or localhost)
API_URL = os.environ.get("API_URL", "http://app:8000/api/v1/monitoring")

def fetch_status():
    try:
        response = requests.get(f"{API_URL}/status", timeout=2)
        return response.json()
    except:
        return None

def fetch_ml_stats():
    try:
        response = requests.get(f"{API_URL}/ml-stats", timeout=2)
        return response.json()
    except:
        return None

def update_settings(payload):
    try:
        response = requests.post(f"{API_URL}/settings", json=payload, timeout=5)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def exchange_token(code):
    try:
        response = requests.post(f"{API_URL}/exchange-token", json={"code": code}, timeout=10)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_login_url():
    try:
        response = requests.get(f"{API_URL}/login-url", timeout=2)
        return response.json().get("url")
    except:
        return None

# Sidebar
st.sidebar.title("🚀 Upstox Bot")
st.sidebar.markdown("---")

# Current Time Display in Sidebar
from datetime import datetime
import pytz
IST = pytz.timezone('Asia/Kolkata')
current_ist = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
st.sidebar.metric("Current Time (IST)", current_ist)

refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 1, 30, 10)

# Main UI
st.title("📈 Trading System Dashboard")

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Status", "🧠 AI Training Data", "⚙️ Settings"])

with tab1:
    # Top Row: Status Cards
    status_data = fetch_status()

    if status_data:
        # Token Expiry Alert (Top Priority)
        token_info = status_data["environment"].get("token_expiry", {})
        if token_info:
            expiry_time = token_info.get("expiry")
            time_left = token_info.get("time_left")
            is_expired = token_info.get("expired", False)
            
            if is_expired:
                st.error(f"🚨 **CRITICAL: UPSTOX TOKEN EXPIRED!** Trading is disabled. Please update the token in the **Settings** tab.")
            elif "h" in time_left and int(time_left.split('h')[0]) < 2:
                st.warning(f"⚠️ **Token Expiring Soon:** {time_left} remaining (Expires at {expiry_time})")

        col1, col2, col3, col4 = st.columns(4)
        
        # 1. Bot Status
        is_active = status_data["session"]["is_active"]
        col1.metric(
            "Bot Status", 
            "🟢 ACTIVE" if is_active else "💤 SLEEPING",
            delta=None
        )
        
        # 2. WebSocket
        ws_connected = status_data["websocket"]["connected"]
        col2.metric(
            "WebSocket", 
            "🔗 CONNECTED" if ws_connected else "❌ DISCONNECTED",
            delta=None
        )
        
        # 3. Market Hours
        col3.metric(
            "Market Hours (IST)", 
            status_data["session"]["market_hours"]
        )
        
        # 4. Mode
        col4.metric(
            "Trading Mode", 
            status_data["environment"]["mode"]
        )

        # Current Time (IST)
        st.info(f"🕒 **Current System Time (IST):** {status_data['timestamp']}")

        # Token Info (Regular)
        if token_info and not is_expired and not ("h" in time_left and int(time_left.split('h')[0]) < 2):
            st.info(f"🔑 **Token Valid:** {time_left} remaining (Expires at {expiry_time})")

        st.markdown("---")

        # Middle Row: Stats & Info
        left_col, right_col = st.columns([1, 1])
        
        with left_col:
            st.subheader("📊 Session Statistics")
            stats = status_data["websocket"].get("subscriptions", {})
            if stats:
                st.write(f"**Total Symbols:** {stats.get('total_symbols', 0)}")
                st.write(f"**Successfully Subscribed:** {stats.get('subscribed_count', 0)}")
                st.write(f"**Failed:** {stats.get('failed_count', 0)}")
                
                progress = stats.get('subscription_rate', '0%').replace('%', '')
                st.progress(float(progress)/100, text=f"Subscription Progress: {progress}%")
            else:
                st.info("No active session data available.")

        with right_col:
            st.subheader("🕒 System Times")
            st.write(f"**System Startup:** {status_data['session']['startup_time']}")
            st.write(f"**Last Session Start:** {status_data['session']['last_start_time'] or 'N/A'}")
            st.write(f"**Last Session Stop:** {status_data['session']['last_stop_time'] or 'N/A'}")
            st.write(f"**Current Time (IST):** {status_data['timestamp']}")

    else:
        st.error("❌ Could not connect to the Trading Bot API. Ensure the backend is running.")
        if st.button("Retry Connection"):
            st.rerun()

with tab2:
    st.header("🧠 AI Training Data Collection")
    ml_stats = fetch_ml_stats()
    
    if ml_stats:
        # Progress Bar
        progress = ml_stats["progress_percent"] / 100
        st.write(f"### Data Collection Progress: {ml_stats['labeled_samples']} / 100 samples")
        st.progress(progress)
        
        if ml_stats["ready_for_training"]:
            st.success("✅ **Ready for Training!** We have enough data to build the Signal Validation Agent.")
            if st.button("🚀 Start Model Training (Local)"):
                st.info("Training process started in background. Check logs for details.")
        else:
            st.info(f"⏳ **Collecting Data:** Need {100 - ml_stats['labeled_samples']} more labeled samples to start training.")

        # Stats Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Signals", ml_stats["total_samples"])
        col2.metric("Labeled (Win/Loss)", ml_stats["labeled_samples"])
        col3.metric("Win Rate", f"{ml_stats['win_rate']:.1f}%")
        col4.metric("Pending Outcome", ml_stats["pending_samples"])

        # Breakdown
        st.markdown("---")
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("#### 📈 Signal Breakdown")
            st.write(f"**BUY Signals:** {ml_stats['buy_samples']}")
            st.write(f"**SELL Signals:** {ml_stats['sell_samples']}")
            
        with col_b:
            st.markdown("#### 🏆 Outcome Breakdown")
            st.write(f"**Wins:** {ml_stats['wins']}")
            st.write(f"**Losses:** {ml_stats['losses']}")
            
        st.caption("Note: Samples are only 'labeled' once the trade is closed (either TP or SL hit).")
    else:
        st.warning("Could not fetch ML statistics.")

with tab3:
    st.subheader("⚙️ Application Settings")
    
    # Token Expiry Info in Settings
    if status_data:
        token_info = status_data["environment"].get("token_expiry", {})
        if token_info:
            if token_info.get("expired"):
                st.error(f"🚨 **TOKEN EXPIRED:** {token_info.get('expiry')}")
            else:
                st.success(f"✅ **Token Valid until:** {token_info.get('expiry')} ({token_info.get('time_left')} left)")

    st.info("Changes here will be saved to config.json and applied immediately.")
    
    if status_data and "settings" in status_data:
        # --- NEW: Direct Token Update ---
        st.markdown("### ⚡ Daily Token Update")
        st.write("Paste your new **Access Token** here to refresh the connection and restart the bot.")
        
        col_a, col_b = st.columns([1, 3])
        
        login_url = get_login_url()
        if login_url:
            col_a.link_button("1. Get Token", login_url, type="secondary", use_container_width=True, help="Opens Upstox login to help you generate a token.")
        
        with col_b:
            direct_token = st.text_input("2. Paste Access Token", placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", label_visibility="collapsed")
            if st.button("3. Apply Token & Restart Bot", type="primary", use_container_width=True, disabled=not direct_token):
                with st.spinner("Updating token and restarting services..."):
                    payload = {"upstox_access_token": direct_token.strip()}
                    res = update_settings(payload)
                    if res.get("status") == "success":
                        st.success("✅ Token updated! Bot is restarting...")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"Error: {res.get('message')}")
        
        st.markdown("---")
        
        with st.form("settings_form"):
            st.markdown("### ⚙️ System Configuration")
            
            # Show current token status
            current_masked_token = status_data.get("environment", {}).get("upstox_access_token", "None")
            st.write(f"**Active Token:** `{current_masked_token}`")
            
            st.markdown("### 🛡️ Risk Management")
            col1, col2 = st.columns(2)
            
            # Use .get() with defaults to avoid KeyErrors if backend is out of sync
            settings_dict = status_data.get("settings", {})
            paper_mode = col1.toggle("Paper Trading Mode", value=settings_dict.get("paper_trading_mode", True))
            acc_size = col2.number_input("Account Size (₹)", value=float(settings_dict.get("account_size", 100000.0)), step=10000.0)
            
            risk_pct = st.slider("Risk Per Trade (%)", 0.1, 10.0, float(settings_dict.get("risk_per_trade", 0.01) * 100)) / 100
            
            st.markdown("### 🕒 Market Hours")
            col3, col4 = st.columns(2)
            open_time = col3.text_input("Market Open (IST)", value=settings_dict.get("market_open_time", "09:15"))
            close_time = col4.text_input("Market Close (IST)", value=settings_dict.get("market_close_time", "15:25"))
            
            auto_start = st.checkbox("Auto Start/Stop", value=settings_dict.get("auto_start_stop", True))
            
            submitted = st.form_submit_button("Save Settings")
            
            if submitted:
                payload = {
                    "paper_trading_mode": paper_mode,
                    "account_size": acc_size,
                    "risk_per_trade": risk_pct,
                    "market_open_time": open_time,
                    "market_close_time": close_time,
                    "auto_start_stop": auto_start
                }
                
                result = update_settings(payload)
                if result.get("status") == "success":
                    st.success("✅ Settings updated successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Failed to update settings: {result.get('message')}")
    else:
        st.warning("Settings are unavailable because the API is not reachable.")

# Auto-refresh
if refresh_rate > 0:
    time.sleep(refresh_rate)
    st.rerun()
