import base64
import json
from datetime import datetime
from typing import Dict, Any, Optional
from .timezone import ist_now, IST_TZ

def get_token_expiry(token: str) -> Dict[str, Any]:
    """
    Decodes Upstox JWT token to get expiry information.
    Returns a dict with expiry time, time left, and expired status.
    """
    if not token or token == "None":
        return {"expiry": "N/A", "time_left": "N/A", "expired": True}
        
    try:
        # JWT is header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return {"expiry": "Invalid Format", "time_left": "N/A", "expired": True}
            
        # Decode payload (second part)
        payload_b64 = parts[1]
        # Add padding if needed
        missing_padding = len(payload_b64) % 4
        if missing_padding:
            payload_b64 += '=' * (4 - missing_padding)
            
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        exp_timestamp = payload.get('exp')
        if not exp_timestamp:
            return {"expiry": "No Exp Claim", "time_left": "N/A", "expired": True}
            
        exp_dt = datetime.fromtimestamp(exp_timestamp, tz=IST_TZ)
        now = ist_now()
        
        time_left = exp_dt - now
        is_expired = time_left.total_seconds() <= 0
        
        if is_expired:
            return {
                "expiry": exp_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "time_left": "EXPIRED",
                "expired": True
            }
            
        # Format time left
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        
        return {
            "expiry": exp_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "time_left": f"{hours}h {minutes}m",
            "expired": False,
            "hours_left": hours
        }
    except Exception as e:
        return {"expiry": f"Error: {str(e)}", "time_left": "N/A", "expired": True}
