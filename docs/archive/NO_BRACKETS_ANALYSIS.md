# 🚫 INSTRUMENTS WITH NO BRACKETS - Complete Analysis

## 📊 Summary Statistics

| Metric | Count |
|--------|-------|
| Total Instruments Tested | 192 |
| WITH Brackets ✅ | 33 |
| WITHOUT Brackets ❌ | 159 |
| Success Rate | 17.2% (33/192) |
| Failure Rate | 82.8% (159/192) |

---

## 📋 Complete List of 159 Instruments Without Brackets

```
ACC
ADANIPORT
ADANIPOWER
ALLCARGO
AMBUJACEMENT
APLAPOLLO
ASHOK_LEYLAND
ASHOKLEY
ASTRAL
ATUL
AUBANK
BAJAJ_AUTO
BAJAJAGRI
BAJAJFINSV
BIOCON
BOLLYWOOD
BRITANNIA
BSNLSPIRIT
COFORGE
COLPAL
CONCOR
CROMPTON
CUMMINS
DEEPAKFERT
DIVISLAB
DRREDDY
EASEEXPRESS
ECLERX
EVERESTIND
FEDERALBNK
FRETAIL
GMRINFRA
GRASIM
GRINDWELL
GROVY
HARRYSUP
HCLTECH
HDFC
HDFC_BANK
HDFCLIFE
HEROMOTOCO
HINDPETRO
HUL
ICICI
ICICIBANK
ICICIPRULI
IDFC
INDORAMA
INDUSIND
INFY
IOCL
IPCALAB
JINDAL_STEEL
JIOTELECOM
JKCEMENT
JSWSTEEL
JYOTHYLAB
KAMARAJS
KANPRPHARMA
KAVERI_SEED
KOTAK
KPITTECH
LALPATHLAB
LAXMITEXTIL
LEMONTREE
LODHA
LT
LTFOODS
LTTS
LUMARCO
LUPIN
MAHINDRA
MARICO
MARUTI
MEINDUST
MINDTREE
MOBILEINDUS
MOHITIND
NATIONALUM
NDTV
NESTLEIND
NIFTY
NUML
OBEROIHOTEL
ONGC
PIDILITIND
POLYCAB
PRECWIRE
RADIOCITY
RAMCOCEMENT
RELINFRA
SBIN
SEZALINFRA
SHREE_CEMENT
SIYAM
SKFL
SONYTVHOLD
SUGANE
SUMEROTEC
SUNPHARMA
SVCCGROUP
SWARAJ
SWSOLAR
SYMPHONY
SYROS
SYSEXNET
TATAMOTOR
TCI
TECH_MAHIND
TIMKEN
TORNTPHARM
TORNTPOWER
TRENDSETTR
TRIDENT
TRIGCEM
TRIVENI
TYCOON
UNIMECH
UNOMINDA
UPCL
UTKARSHMET
UTPL
VALUELOGIS
VEDANT
VENKEYS
VGUARD
VIDHIING
VIMTALABS
VINATEXTIL
VIPULLTD
VIRAT_IND
VIVONEXT
VLSFINANCE
VNDRAMA
VODAFONE
VOLCHEM
VOLTAS
WALPAR
WATECH
WBSEDL
WEBLFIBER
WEBOLDLLP
WESCO
WESTC
WIPRO
WSTSHIP
XRNT
YARA
YSCTRANSPO
YUSVD
ZEEENTERTAIN
ZENTEC
ZERODHA
ZGONDAL
ZIGZAG
ZIMLAB
ZODJSPOL
ZYDUSHEAL
ZYDUSWELL
```

---

## 🎯 Categorization by Market Cap

### Large Cap Stocks (Unexpected Failures ⚠️)
- **Banking**: ICICIBANK, ICICI, HDFC, SBIN, FEDERALBNK, AUBANK, KOTAK, INDUSIND
- **IT**: INFY, WIPRO, HCLTECH, MINDTREE, LTTS
- **Engineering**: LT, JSWSTEEL, TATAMOTOR, MARUTI, MAHINDRA
- **FMCG**: HUL, SUNPHARMA, DRREDDY, LUPIN, BRITANNIA
- **Others**: ONGC, IOCL, VODAFONE

### Mid Cap Stocks (Expected Failures)
- ASTRAL, POLYCAB, SYMPHONY, TRIDENT, CROMPTON, etc.

### Small Cap Stocks (Expected Failures)
- TRIGCEM, VEDANT, UTPL, WALPAR, XRNT, YARA, etc.

---

## ⚠️ Surprising Failures - Major Stocks That SHOULD Have Brackets

### Banking Sector
```
ICICIBANK  - Should have brackets (major bank)
ICICI      - Should have brackets (holding company)
HDFC       - Should have brackets (mortgage major)
SBIN       - Should have brackets (State Bank of India)
FEDERALBNK - Federal Bank
AUBANK     - Axis-like bank
KOTAK      - Kotak Bank (major)
INDUSIND   - IndusInd Bank
```

### IT Sector
```
INFY       - Infosys (MAJOR IT stock!)
WIPRO      - Wipro (MAJOR IT stock!)
HCLTECH    - HCL Tech
MINDTREE   - Mindtree
LTTS       - L&T Tech Services
```

### Engineering/Industrial
```
LT         - Larsen & Toubro (MAJOR!)
JSWSTEEL   - JSW Steel
TATAMOTOR  - Tata Motors
MARUTI     - Maruti Suzuki
MAHINDRA   - Mahindra & Mahindra
```

### FMCG/Consumer
```
HUL        - Hindustan Unilever (MAJOR!)
SUNPHARMA  - Sun Pharma
DRREDDY    - Dr. Reddy's Labs
LUPIN      - Lupin Ltd
BRITANNIA  - Britannia Industries
```

### PSU/Others
```
ONGC       - Oil & Natural Gas Corp
IOCL       - Indian Oil Corporation
VODAFONE   - Vodafone Idea
```

---

## 💡 Possible Reasons for Failures

### 1. Data Quality Issue 🔴 (Most Likely)
- Option chain data might be incomplete
- Strike prices might not be in database
- Expiry dates might be missing
- Check the options chain import

### 2. Algorithm Issue 🟡 (Possible)
- Algorithm too strict in finding PE above and CE below
- Wrong price data being used
- Wrong expiry date selection

### 3. Market Data Issue 🟡 (Possible)
- Price data might be stale or incorrect
- Strike prices might not match actual prices
- Real market conditions (holidays, etc.)

---

## 🔧 Recommendations

### 1. IMMEDIATE ACTIONS
```
✅ Verify the options chain database
✅ Check if strike data is imported correctly
✅ Validate price data against Upstox API
✅ Check if there are any data loading errors
```

### 2. INVESTIGATION STEPS
```
• Run manual query for INFY bracket selection
• Compare against Upstox WebSocket data
• Check algorithm logic for edge cases
```

### 3. DATA VALIDATION
```
• Query options chain for INFY directly
• See what strikes are available
• Manually verify PE/CE selection logic
```

---

## 📝 Quick Export Formats

### As JSON Array
```json
{
  "no_bracket_symbols": [
    "ACC", "ADANIPORT", "ADANIPOWER", ...
  ],
  "count": 159
}
```

### As CSV
```
ACC,ADANIPORT,ADANIPOWER,ALLCARGO,AMBUJACEMENT,APLAPOLLO,ASHOK_LEYLAND,ASHOKLEY,ASTRAL,ATUL,AUBANK,BAJAJ_AUTO,BAJAJAGRI,BAJAJFINSV,BIOCON,BOLLYWOOD,BRITANNIA,BSNLSPIRIT,COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINS,DEEPAKFERT,DIVISLAB,DRREDDY,EASEEXPRESS,ECLERX,EVERESTIND,FEDERALBNK,FRETAIL,GMRINFRA,GRASIM,GRINDWELL,GROVY,HARRYSUP,HCLTECH,HDFC,HDFC_BANK,HDFCLIFE,HEROMOTOCO,HINDPETRO,HUL,ICICI,ICICIBANK,ICICIPRULI,IDFC,INDORAMA,INDUSIND,INFY,IOCL,IPCALAB,JINDAL_STEEL,JIOTELECOM,JKCEMENT,JSWSTEEL,JYOTHYLAB,KAMARAJS,KANPRPHARMA,KAVERI_SEED,KOTAK,KPITTECH,LALPATHLAB,LAXMITEXTIL,LEMONTREE,LODHA,LT,LTFOODS,LTTS,LUMARCO,LUPIN,MAHINDRA,MARICO,MARUTI,MEINDUST,MINDTREE,MOBILEINDUS,MOHITIND,NATIONALUM,NDTV,NESTLEIND,NIFTY,NUML,OBEROIHOTEL,ONGC,PIDILITIND,POLYCAB,PRECWIRE,RADIOCITY,RAMCOCEMENT,RELINFRA,SBIN,SEZALINFRA,SHREE_CEMENT,SIYAM,SKFL,SONYTVHOLD,SUGANE,SUMEROTEC,SUNPHARMA,SVCCGROUP,SWARAJ,SWSOLAR,SYMPHONY,SYROS,SYSEXNET,TATAMOTOR,TCI,TECH_MAHIND,TIMKEN,TORNTPHARM,TORNTPOWER,TRENDSETTR,TRIDENT,TRIGCEM,TRIVENI,TYCOON,UNIMECH,UNOMINDA,UPCL,UTKARSHMET,UTPL,VALUELOGIS,VEDANT,VENKEYS,VGUARD,VIDHIING,VIMTALABS,VINATEXTIL,VIPULLTD,VIRAT_IND,VIVONEXT,VLSFINANCE,VNDRAMA,VODAFONE,VOLCHEM,VOLTAS,WALPAR,WATECH,WBSEDL,WEBLFIBER,WEBOLDLLP,WESCO,WESTC,WIPRO,WSTSHIP,XRNT,YARA,YSCTRANSPO,YUSVD,ZEEENTERTAIN,ZENTEC,ZERODHA,ZGONDAL,ZIGZAG,ZIMLAB,ZODJSPOL,ZYDUSHEAL,ZYDUSWELL
```

---

## 🔍 Next Investigation

The presence of major stocks like **INFY**, **WIPRO**, **LT**, **HUL**, **ICICIBANK** in the failure list suggests:

1. **Data quality issues** with option chain import
2. **Algorithm restrictions** that are too strict
3. **Price/expiry mismatch** in the database

**Recommended**: Investigate INFY bracket selection to identify root cause.

---

*Generated: 2025-11-29*
*Status: 🔴 Requires Investigation*
