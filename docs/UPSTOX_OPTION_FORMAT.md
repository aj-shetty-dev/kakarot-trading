# Upstox V3 Option Symbol Format

## 🎯 The Correct Format

**Upstox V3 API expects options in this format:**

```
{SYMBOL}{YEAR}{MONTH_CODE}{STRIKE}{OPTION_TYPE}
```

### Example for RELIANCE:
```
RELIANCE25D2500CE
├─ RELIANCE    = Base symbol
├─ 25          = Year (2025)
├─ D           = Month code (December)
├─ 2500        = Strike price
└─ CE          = Call option (CE) or Put option (PE)
```

---

## 📅 Month Codes (Upstox Convention)

| Month | Code | Example |
|-------|------|---------|
| January | F | RELIANCE25F2500CE |
| February | G | RELIANCE25G2500CE |
| March | H | RELIANCE25H2500CE |
| April | J | RELIANCE25J2500CE |
| May | K | RELIANCE25K2500CE |
| June | M | RELIANCE25M2500CE |
| July | N | RELIANCE25N2500CE |
| August | Q | RELIANCE25Q2500CE |
| September | U | RELIANCE25U2500CE |
| October | V | RELIANCE25V2500CE |
| November | X | RELIANCE25X2500CE |
| December | Z | RELIANCE25Z2500CE |

> **Note:** These month codes follow commodity trading conventions (not alphabetical).

---

## 🔄 WebSocket API Format

When sending to Upstox V3 WebSocket API (`wss://api.upstox.com/v3`), the format becomes:

```
NSE_FO|{SYMBOL}{YEAR}{MONTH_CODE}{STRIKE}{OPTION_TYPE}
```

### Examples:
```
NSE_FO|RELIANCE25D2500CE    (Call option)
NSE_FO|RELIANCE25D2600PE    (Put option)
NSE_FO|INFY25D3000CE        (Call option)
NSE_FO|INFY25D3100PE        (Put option)
NSE_FO|TCS25D3100CE         (Call option)
```

---

## 🛠️ Implementation in Our App

### Database Storage
We store the **simple format** (without NSE_FO prefix):
```sql
-- Table: subscribed_options
symbol          | option_symbol         | strike_price | option_type
RELIANCE        | RELIANCE25D2500CE     | 2500         | CE
RELIANCE        | RELIANCE25D2600PE     | 2600         | PE
INFY            | INFY25D3000CE         | 3000         | CE
INFY            | INFY25D3100PE         | 3100         | PE
```

### WebSocket Subscription
When subscribing, we automatically convert using `_symbol_to_token()`:
```python
# In client.py
def _symbol_to_token(symbol: str) -> str:
    if symbol.endswith(("PE", "CE")):
        return f"NSE_FO|{symbol}"
    # Returns: NSE_FO|RELIANCE25D2500CE
```

---

## 📊 Current Implementation (After Fix)

### Sample Symbols (First 10 out of 416)

```
📋 OPTION CONTRACTS:

1. 360ONE25D1600CE      (360ONE, Dec 2025, Strike 1600, Call)
2. 360ONE25D1700PE      (360ONE, Dec 2025, Strike 1700, Put)
3. ABB25D2100CE         (ABB, Dec 2025, Strike 2100, Call)
4. ABB25D2200PE         (ABB, Dec 2025, Strike 2200, Put)
5. ABCAPITAL25D3700CE   (ABCAPITAL, Dec 2025, Strike 3700, Call)
6. ABCAPITAL25D3800PE   (ABCAPITAL, Dec 2025, Strike 3800, Put)
7. ADANIENSOL25D4500CE  (ADANIENSOL, Dec 2025, Strike 4500, Call)
8. ADANIENSOL25D4600PE  (ADANIENSOL, Dec 2025, Strike 4600, Put)
9. ADANIENT25D1100CE    (ADANIENT, Dec 2025, Strike 1100, Call)
10. ADANIENT25D1200PE   (ADANIENT, Dec 2025, Strike 1200, Put)

... 406 more option contracts ...

415. ZYDUSLIFE25D5500CE (ZYDUSLIFE, Dec 2025, Strike 5500, Call)
416. ZYDUSLIFE25D5600PE (ZYDUSLIFE, Dec 2025, Strike 5600, Put)
```

---

## ✅ Data Flow

```
1. Options Loader Service
   ├─ For each symbol (RELIANCE, INFY, TCS, ...)
   ├─ Fetch spot price
   ├─ Calculate ATM strike
   ├─ Calculate ATM+1 strike
   └─ Generate option symbols: {SYMBOL}25D{STRIKE}{CE/PE}

2. Store in Database
   ├─ Table: subscribed_options
   ├─ Columns: symbol, option_symbol, strike_price, option_type
   └─ 416 total records (208 symbols × 2 options each)

3. WebSocket Subscription
   ├─ Query database for all option_symbols
   ├─ Convert to Upstox format: NSE_FO|{option_symbol}
   ├─ Send subscription request to WebSocket API
   └─ Receive real-time ticks

4. Tick Data Processing
   ├─ Receive: NSE_FO|RELIANCE25D2500CE, price: 245.50, Greeks, ...
   ├─ Store in: market_tick table
   ├─ Calculate: Greeks (Delta, Gamma, Theta, Vega)
   └─ Generate: Signals (to be implemented)
```

---

## 🔍 Why Was It Wrong Before?

**Old Format (❌ WRONG):**
```
RELIANCE25X2500CE  ← Using X instead of month code!
RELIANCE25X2600PE
```

**Issues:**
- No month information (ambiguous which expiry)
- Upstox API doesn't recognize this format
- 208 symbols with expiry ambiguity

**New Format (✅ CORRECT):**
```
RELIANCE25D2500CE  ← December 2025 (D = December)
RELIANCE25D2600PE
```

---

## 📝 Reference Implementation

### Code Change (options_loader.py)

```python
# ❌ OLD
option_symbol = f"{symbol.symbol}25X{int(atm_strike)}CE"

# ✅ NEW
expiry_code = "25D"  # December 2025 in Upstox format
option_symbol = f"{symbol.symbol}{expiry_code}{int(atm_strike)}CE"
```

### Example Trace for RELIANCE

```
Input:  symbol = "RELIANCE", spot_price = 2500.50

Step 1: Calculate strikes
  ATM = round(2500.50 / 100) * 100 = 2500
  ATM+1 = 2500 + 100 = 2600

Step 2: Generate option symbols
  expiry_code = "25D"  (December 2025)
  CE_symbol = RELIANCE + 25D + 2500 + CE = RELIANCE25D2500CE
  PE_symbol = RELIANCE + 25D + 2600 + PE = RELIANCE25D2600PE

Step 3: Store in database
  INSERT INTO subscribed_options
    (symbol, option_symbol, strike_price, option_type, ...)
  VALUES
    ('RELIANCE', 'RELIANCE25D2500CE', 2500, 'CE', ...),
    ('RELIANCE', 'RELIANCE25D2600PE', 2600, 'PE', ...)

Step 4: On WebSocket subscription
  SELECT option_symbol FROM subscribed_options
  For each: RELIANCE25D2500CE → NSE_FO|RELIANCE25D2500CE
  
Step 5: Send to API
  subscribe([
    "NSE_FO|RELIANCE25D2500CE",
    "NSE_FO|RELIANCE25D2600PE"
  ])
```

---

## 🎯 Verification

To verify the format is correct, check the database:

```sql
SELECT option_symbol 
FROM subscribed_options 
ORDER BY option_symbol 
LIMIT 10;
```

Expected output:
```
360ONE25D1600CE
360ONE25D1700PE
ABB25D2100CE
ABB25D2200PE
ABCAPITAL25D3700CE
ABCAPITAL25D3800PE
...
```

All symbols should:
- ✅ Contain month code (D for December)
- ✅ Contain year (25 for 2025)
- ✅ Contain strike price (without X separator)
- ✅ End with CE or PE
- ✅ No spaces or special characters

---

## 📌 Summary

| Aspect | Details |
|--------|---------|
| **Database Format** | `RELIANCE25D2500CE` |
| **WebSocket API Format** | `NSE_FO\|RELIANCE25D2500CE` |
| **Total Symbols** | 416 (208 base × 2 options) |
| **Expiry** | December 2025 (code: D) |
| **Strike Increment** | ATM and ATM+100 |
| **Auto-Conversion** | Via `_symbol_to_token()` method |

