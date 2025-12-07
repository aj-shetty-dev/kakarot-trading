"""
FNO (Futures & Options) symbol management
Uses official NSE list of 208 equity FNO stocks
"""

from typing import List
from ..config.logging import logger


async def get_fno_symbols() -> List[str]:
    """
    Get the official NSE FNO stocks list - 208 instruments
    
    This is the source of truth for all FNO trading symbols.
    Source: NSE F&O permitted list
    
    Returns:
        List[str]: List of 208 FNO trading symbols
    """
    symbols = [
        "360ONE", "ABB", "APLAPOLLO", "AUBANK", "ADANIENSOL", "ADANIENT", "ADANIGREEN",
        "ADANIPORTS", "ABCAPITAL", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APOLLOHOSP",
        "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA", "DMART", "AXISBANK", "BSE",
        "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BANDHANBNK", "BANKBARODA", "BANKINDIA",
        "BDL", "BEL", "BHARATFORG", "BHEL", "BPCL", "BHARTIARTL", "BIOCON", "BLUESTARCO",
        "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK", "CDSL", "CHOLAFIN", "CIPLA",
        "COALINDIA", "COFORGE", "COLPAL", "CAMS", "CONCOR", "CROMPTON", "CUMMINSIND",
        "CYIENT", "DLF", "DABUR", "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON",
        "DRREDDY", "ETERNAL", "EICHERMOT", "EXIDEIND", "NYKAA", "FORTIS", "GAIL",
        "GMRAIRPORT", "GLENMARK", "GODREJCP", "GODREJPROP", "GRASIM", "HCLTECH",
        "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HFCL", "HAVELLS", "HEROMOTOCO", "HINDALCO",
        "HAL", "HINDPETRO", "HINDUNILVR", "HINDZINC", "POWERINDIA", "HUDCO", "ICICIBANK",
        "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "IIFL", "ITC", "INDIANB", "IEX",
        "IOC", "IRCTC", "IRFC", "IREDA", "INDUSTOWER", "INDUSINDBK", "NAUKRI",
        "INFY", "INOXWIND", "INDIGO", "JINDALSTEL", "JSWENERGY", "JSWSTEEL", "JIOFIN",
        "JUBLFOOD", "KEI", "KPITTECH", "KALYANKJIL", "KAYNES", "KFINTECH", "KOTAKBANK",
        "LTF", "LICHSGFIN", "LTIM", "LT", "LAURUSLABS", "LICI", "LODHA",
        "LUPIN", "M&M", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", "MFSL",
        "MAXHEALTH", "MAZDOCK", "MPHASIS", "MCX", "MUTHOOTFIN", "NBCC", "NCC",
        "NHPC", "NMDC", "NTPC", "NATIONALUM", "NESTLEIND", "NUVAMA", "OBEROIRLTY",
        "ONGC", "OIL", "PAYTM", "OFSS", "POLICYBZR", "PGEL", "PIIND",
        "PNBHOUSING", "PAGEIND", "PATANJALI", "PERSISTENT", "PETRONET", "PIDILITIND",
        "PPLPHARMA", "POLYCAB", "PFC", "POWERGRID", "PRESTIGE", "PNB", "RBLBANK",
        "RECLTD", "RVNL", "RELIANCE", "SBICARD", "SBILIFE", "SHREECEM", "SRF",
        "SAMMAANCAP", "MOTHERSON", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS",
        "SBIN", "SAIL", "SUNPHARMA", "SUPREMEIND", "SUZLON", "SYNGENE", "TATACONSUM",
        "TITAGARH", "TVSMOTOR", "TCS", "TATAELXSI", "TMPV", "TATAPOWER", "TATASTEEL",
        "TATATECH", "TECHM", "FEDERALBNK", "INDHOTEL", "PHOENIXLTD", "TITAN", "TORNTPHARM",
        "TORNTPOWER", "TRENT", "TIINDIA", "UNOMINDA", "UPL", "ULTRACEMCO", "UNIONBANK",
        "UNITDSPR", "VBL", "VEDL", "IDEA", "VOLTAS", "WIPRO", "YESBANK", "ZYDUSLIFE"
    ]
    
    logger.info(f"✅ Using official NSE FNO list: {len(symbols)} symbols")
    return symbols
