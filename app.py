import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
import re
import io
import traceback
from difflib import SequenceMatcher


st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# ─────────────────────────────────────────────────────────────
# CUSTOM TOP HEADER & GLOBAL STYLING
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp, .main, [data-testid="stSidebar"] {
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid #eaeaea !important;
        padding-top: 0 !important;
        top: 20px !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }
    header[data-testid="stHeader"] { 
        background: transparent !important;
        box-shadow: none !important;
        z-index: 1000001 !important; 
        top: 24px !important;
    }
    header[data-testid="stHeader"] span { color: #ffffff !important; }
    header[data-testid="stHeader"] svg { fill: #ffffff !important; color: #ffffff !important; }
    header[data-testid="stHeader"] svg rect { fill: transparent !important; }
    .appview-container .main .block-container { padding-top: 300px !important; }
    .poc-header-wrapper {
        position: fixed; top: 0; left: 0; right: 0;
        z-index: 999999; display: flex; flex-direction: column;
    }
    .poc-top-bar { background-color: #BF3C00; height: 24px; width: 100%; }
    .poc-main-bar {
        background-color: #FE5900; height: 60px; width: 100%;
        display: flex; align-items: center; padding: 0 40px 0 75px; 
    }
    .poc-title {
        color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 22px; font-weight: 700; letter-spacing: -0.5px;
    }
    .poc-promo-banner {
        background-color: #ffeb85; height: 36px; width: 100%;
        display: flex; align-items: center; justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 14px; font-weight: 600; color: #000000;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .public-header {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 24px; font-weight: 700; color: #111111;
        margin-top: 80px !important; margin-bottom: 20px;
        display: flex; align-items: center;
    }
    .public-header::before {
        content: ''; display: inline-block; width: 4px; height: 24px;
        background-color: #ff5e00; margin-right: 10px; border-radius: 2px;
    }
    /* [data-testid="stAlert"] { display: none !important; } */ /* DISABLED - was hiding errors */
</style>

<div class="poc-header-wrapper">
    <div class="poc-top-bar"></div>
    <div class="poc-main-bar">
        <div class="poc-title">Recommendation PoC</div>
    </div>
    <div class="poc-promo-banner">
        🟢 Engine v15.1 — Word Doc Cross-Sell Logic (Age Brackets + Gender + Hierarchy)
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"

# Scoring constants
SMART_BOOST      = 15 
ECOSYSTEM_BOOST  = 100000
AVAIL_BOOST      = 2
HISTORY_BOOST    = 100000 
HISTORY_FREQ_MIN = 5
SERIES_BOOST     = 50000

TECH_CATS = {"IT", "Telephony", "TV"}
APPL_CATS = {"MDA", "SDA", "Air Condition", "Personal Care"}
COMPAT_COLS = ["Συμβατό με", "Συμβατή συσκευή"]
CC = "_Compatible"
ANDROID_OEMS = {"SAMSUNG", "XIAOMI", "HUAWEI", "MOTOROLA", "HONOR", "POCO", "REALME", "ONEPLUS", "NOTHING", "OPPO", "VIVO", "TCL", "NOKIA", "ASUS", "GOOGLE"}

# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS CONFIGURATION (Based on actual data)
# ─────────────────────────────────────────────────────────────
KIDS_BOOKS_LEVEL2 = {"Greek Kids Books", "International Kids Books"}

# Age Bracket Definitions
AGE_BRACKETS = {
    "BRACKET_1": {
        "trigger": ["0+ μηνών", "0+ ετών", "3+ μηνών", "5+ μηνών"],
        "allowed": ["0+ μηνών", "0+ ετών", "3+ μηνών", "5+ μηνών", "6+ μηνών"]
    },
    "BRACKET_2": {
        "trigger": ["6+ μηνών", "9+ μηνών"],
        "allowed": ["6+ μηνών", "9+ μηνών", "12+ μηνών", "1+ ετών"]
    },
    "BRACKET_3": {
        "trigger": ["12+ μηνών", "1+ ετών", "1.5+ ετών"],
        "allowed": ["9+ μηνών", "12+ μηνών", "1+ ετών", "1.5+ ετών", "24+ μηνών", "2+ ετών"]
    },
    "BRACKET_4": {
        "trigger": ["24+ μηνών", "2+ ετών"],
        "allowed": ["1.5+ ετών", "24+ μηνών", "2+ ετών", "3+ ετών"]
    },
    "BRACKET_5": {
        "trigger": ["3+ ετών", "4+ ετών", "5+ ετών", "6+ ετών", "3-6 ετών"],
        "allowed": ["3+ ετών", "4+ ετών", "5+ ετών", "6+ ετών", "7+ ετών", "8+ ετών", "3-6 ετών"]
    },
    "BRACKET_6": {
        "trigger": ["7+ ετών", "8+ ετών", "9+ ετών", "10+ ετών", "11+ ετών", "12+ ετών", "6 - 9", "9 - 12"],
        "allowed": ["6+ ετών", "7+ ετών", "8+ ετών", "9+ ετών", "10+ ετών", "11+ ετών", "12+ ετών", "13+ ετών", "6 - 9", "9 - 12"]
    },
    "BRACKET_7": {
        "trigger": ["13+ ετών", "14+ ετών", "15+ ετών", "16+ ετών", "17+ ετών", "18+ ετών"],
        "allowed": ["10+ ετών", "11+ ετών", "12+ ετών", "13+ ετών", "14+ ετών", "15+ ετών", "16+ ετών", "17+ ετών", "18+ ετών"]
    }
}

# 🟢 ACTUAL TOY HIERARCHIES FROM YOUR DATA
TOY_HIERARCHIES_ACTUAL = {
    "plush": ["ΛΟΥΤΡΙΝΑ", "ΛΟΥΤΡΙΝΑ ΜΠΡΕΛΟΚ"],
    "dolls": ["ΚΟΥΚΛΕΣ"],
    "action_figures": ["ACTION FIGURES", "ΣΥΛΛΕΚΤΙΚΕΣ ΦΙΓΟΥΡΕΣ", "FUNKO POP!"],
    "board_puzzles": ["ΟΙΚΟΓΕΝΕΙΑΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΠΑΙΔΙΚΑ PUZZLES", "CARD GAMES", "ΠΑΙΔΙΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΕΝΗΛΙΚΩΝ 1000+", "ΕΝΗΛΙΚΩΝ ΕΩΣ 999"],
    "building": ["ΚΑΤΑΣΚΕΥΕΣ", "ΜΙΚΡΟΚΟΣΜΟΣ"],
    "toddler": ["ΒΡΕΦΙΚΑ ΠΑΙΧΝΙΔΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ", "ΦΙΓΟΥΡΕΣ & PLAYSET", "Ζωάκια"],
    "vehicles": ["ΔΙΑΦΟΡΑ ΑΥΤΟΚΙΝΗΤΑ", "ΑΥΤΟΚΙΝΗΤΑ"],
    "creative": ["ΖΩΓΡΑΦΙΚΗ", "ΠΛΑΣΤΕΛΙΝΕΣ", "ΧΕΙΡΟΤΕΧΝΙΕΣ"],
    # 🟢 NEW: 8+ specific categories
    "collectable_cards": ["Collectable Cards"],  # Pokemon, FIFA, etc.
    "knowledge_games": ["ΓΝΩΣΕΩΝ"],  # Knowledge/trivia games
    "adult_board": ["ΕΠΙΤΡΑΠΕΖΙΑ ΕΝΗΛΙΚΩΝ"],  # Strategy games for 8+
    "beauty_fashion": ["ΟΜΟΡΦΙΑΣ", "ΔΡΑΣΤΗΡΙΟΤΗΤΕΣ ΓΙΑ ΚΟΡΙΤΣΙΑ"],  # For older girls
    "lamps_decor": ["LAMPS"],  # Room decor for tweens
}

# 🟢 ACTUAL STATIONERY HIERARCHIES FROM YOUR DATA
STATIONERY_HIERARCHIES_ACTUAL = {
    "notebooks": ["ΣΗΜΕΙΩΜΑΤΑΡΙΑ", "ΤΕΤΡΑΔΙΑ"],
    "water_bottles": ["ΘΕΡΜΟΣ - ΠΑΓΟΥΡΙΑ", "ΠΑΓΟΥΡΙΑ", "ΘΕΡΜΟΣ"],
    "arts_crafts": ["ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ", "ΜΠΛΟΚ-ΧΑΡΤΙΑ", "ΚΑΣΕΤΙΝΕΣ", "ΜΑΡΚΑΔΟΡΟΙ", "ΜΑΡΚΑΔΟΡΟΙ ΣΧΕΔΙΟΥ-ΕΙΔΙΚΩΝ ΧΡΗΣΕΩΝ", "ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ"],
    "reading": ["READING ACCESSORIES"],
    "writing": ["ΜΟΛΥΒΙΑ", "ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ", "ΣΤΥΛΟ GEL"],
    "keychains": ["ΜΠΡΕΛΟΚ", "ΜΑΓΝΗΤΑΚΙΑ"],
    "cups": ["ΚΟΥΠΕΣ &  ΠΟΤΗΡΙΑ", "ΚΟΥΠΕΣ & ΠΟΤΗΡΙΑ"],
    # 🟢 NEW: Additional lifestyle for 8+
    "bags": ["ΤΣΑΝΤΑΚΙΑ - ΠΟΡΤΟΦΟΛΙΑ", "ΤΣΑΝΤΕΣ LIFESTYLE", "SHOPPING BAGS"],
    "food_containers": ["ΦΑΓΗΤΟΔΟΧΕΙΑ", "ΤΣΑΝΤΕΣ ΦΑΓΗΤΟΥ"],
    "stickers": ["ΑΥΤΟΚΟΛΛΗΤΑ-STICKERS"],
    "gift_gadgets": ["GIFT GADGETS"],
}

# 🟢 BOOKS SLOT MATRIX (Similar to Smartphones structure)
BOOKS_SLOT_MATRIX = [
    {"slot": 1, "role": "Series Book 1", "type": "SERIES", "max": 1},
    {"slot": 2, "role": "Series Book 2", "type": "SERIES", "max": 1},
    {"slot": 3, "role": "Series Book 3", "type": "SERIES", "max": 1},
    {"slot": 4, "role": "Cross-Sell: Toy (IP Match)", "type": "CROSSSELL_TOY", "max": 1},
    {"slot": 5, "role": "Cross-Sell: Creative/Arts", "type": "CROSSSELL_CREATIVE", "max": 1},
    {"slot": 6, "role": "Cross-Sell: Puzzle/Game", "type": "CROSSSELL_PUZZLE", "max": 1},
    {"slot": 7, "role": "Cross-Sell: Lifestyle", "type": "CROSSSELL_LIFESTYLE", "max": 1},
    {"slot": 8, "role": "Category Discovery 1", "type": "DISCOVERY", "max": 1},
    {"slot": 9, "role": "Category Discovery 2", "type": "DISCOVERY", "max": 1},
    {"slot": 10, "role": "Category Discovery 3", "type": "DISCOVERY", "max": 1},
]

# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def get_age_bracket(age_str: str) -> str:
    age = str(age_str).strip()
    for bracket_name, bracket_data in AGE_BRACKETS.items():
        if age in bracket_data["trigger"]:
            return bracket_name
    return "BRACKET_5"

def get_allowed_ages(trigger_age: str) -> list:
    bracket = get_age_bracket(trigger_age)
    return AGE_BRACKETS.get(bracket, AGE_BRACKETS["BRACKET_5"])["allowed"]

def age_to_numeric(age_str: str) -> float:
    age = str(age_str).strip().lower()
    if "μηνών" in age:
        match = re.search(r'(\d+)', age)
        if match: return float(match.group(1)) / 12
    if "ετών" in age:
        match = re.search(r'(\d+\.?\d*)', age)
        if match: return float(match.group(1))
    # Handle ranges like "3-6 ετών"
    if "-" in age:
        match = re.search(r'(\d+)', age)
        if match: return float(match.group(1))
    return 5.0

def is_valid_series(series_val) -> bool:
    """Check if series value is valid (not empty, nan, '0', or 'N/A')"""
    if series_val is None:
        return False
    if pd.isna(series_val):  # Handle pandas NaN
        return False
    s = str(series_val).strip()
    # Invalid values
    if s.lower() in ['', '0', 'nan', 'n/a', 'none']:
        return False
    return True

def normalize_ip_name(name: str) -> str:
    """Normalize IP name for matching"""
    return str(name).strip().lower().replace('-', ' ').replace('_', ' ')

def get_rotated_selection(df: pd.DataFrame, trigger_material: str, slot_type: str, n: int = 1) -> pd.DataFrame:
    """
    Select items with rotation based on trigger material.
    This ensures different trigger books show different cross-sell items from the same IP pool.
    
    Uses a hash of (trigger_material + slot_type) to create a consistent but varied offset.
    """
    if df.empty:
        return df.head(0)
    
    # Sort by score first
    sorted_df = df.sort_values('Final_Score', ascending=False).reset_index(drop=True)
    
    if len(sorted_df) <= n:
        return sorted_df.head(n)
    
    # Create a rotation offset based on trigger material and slot type
    # This ensures:
    # 1. Same trigger always gets same items (consistent)
    # 2. Different triggers get different items (variety)
    # 3. Different slot types for same trigger get different items
    hash_input = f"{trigger_material}_{slot_type}"
    hash_value = hash(hash_input)
    
    # Get top candidates (top 10 or all if less) - increased from 5 for more variety
    top_candidates = min(10, len(sorted_df))
    candidates = sorted_df.head(top_candidates)
    
    # Rotate selection based on hash
    offset = abs(hash_value) % top_candidates
    
    # Select n items starting from offset, wrapping around
    selected_indices = [(offset + i) % top_candidates for i in range(min(n, top_candidates))]
    
    return candidates.iloc[selected_indices]


def ip_matches(series_name: str, brand: str, heroes: str) -> bool:
    """Check if book series matches toy brand or heroes"""
    if not is_valid_series(series_name):
        return False
    series_norm = normalize_ip_name(series_name)
    brand_norm = normalize_ip_name(brand)
    heroes_norm = normalize_ip_name(heroes)
    
    # Direct match
    if series_norm in brand_norm or brand_norm in series_norm:
        return True
    if series_norm in heroes_norm or heroes_norm in series_norm:
        return True
    
    # Common mappings
    mappings = {
        'harry potter': ['harry potter'],
        'peppa pig': ['peppa pig', 'peppa'],
        'bluey': ['bluey'],
        'spiderman': ['spiderman', 'spider-man', 'spider man', 'spidey'],
        'frozen': ['frozen', 'elsa', 'anna'],
        'disney': ['disney', 'mickey', 'minnie'],
        'barbie': ['barbie'],
        'marvel': ['marvel', 'avengers', 'hulk', 'iron man', 'captain america'],
        'μικροί κύριοι': ['μικροί κύριοι', 'mr. men', 'little miss'],
    }
    
    for key, variants in mappings.items():
        if any(v in series_norm for v in variants):
            if any(v in brand_norm or v in heroes_norm for v in variants):
                return True
    
    return False

def detect_logic_key(role: str) -> str:
    r = role.lower()
    if "perfect fit" in r or "back cover" in r or "primary case" in r: return "PRIMARY_CASE"
    if "alternative" in r or "alt case" in r or "book cover" in r or "wallet" in r: return "ALT_CASE"
    if "screen" in r or "shield" in r:
        if "camera" not in r: return "SCREEN_GLASS"
    if "camera" in r: return "CAMERA_GLASS"
    if "power source" in r or "wall" in r or "charger" in r:
        if "car" not in r: return "WALL_CHARGER"
    if "backup power" in r or "powerbank" in r: return "POWERBANK"
    if "wearable" in r or "smartwatch" in r: return "SMARTWATCH"
    if "audio" in r or "earbud" in r or "handsfree" in r: return "EARBUDS"
    if "commute" in r or "holder" in r: return "HOLDER"
    if "lifestyle" in r or "misc" in r or "cross" in r: return "CROSS_SELL"
    return "UNKNOWN"

def extract_base_port(raw):
    s = str(raw).strip().lower()
    if not s or s == 'nan': return ''
    if 'type-c' in s or 'type c' in s or 'usb-c' in s or 'usb c' in s: return 'Type-C'
    if 'lightning' in s: return 'Lightning'
    if 'micro usb' in s or 'micro-usb' in s: return 'Micro USB'
    if 'usb' in s: return 'USB'
    return str(raw).strip()

COLOR_MAP = {
    'black titanium': ['μαύρο', 'black'],
    'natural titanium': ['μπεζ', 'natural'],
    'white titanium': ['λευκό', 'white'],
    'blue titanium': ['μπλε', 'blue'],
    'space black': ['μαύρο', 'black'],
    'silver': ['ασημί', 'silver', 'γκρι'],
    'gold': ['χρυσό', 'gold', 'μπεζ'],
    'starlight': ['λευκό', 'μπεζ'],
    'midnight': ['μαύρο', 'black'],
    'white': ['λευκό', 'white', 'άσπρο'],
    'black': ['μαύρο', 'black'],
    'blue': ['μπλε', 'blue', 'γαλάζιο'],
    'red': ['κόκκινο', 'red'],
    'green': ['πράσινο', 'green'],
    'pink': ['ροζ', 'pink'],
    'purple': ['μωβ', 'purple'],
    'gray': ['γκρι', 'gray', 'grey'],
    'silver shadow': ['ασημί', 'silver', 'γκρι'],
    'titanium': ['γκρι', 'ασημί'],
}

def get_case_colors(c):
    k = c.strip().lower()
    for mk, mv in COLOR_MAP.items():
        if mk in k or k in mk: return mv
    return [k, 'διάφανο']

def parse_euro_price(v):
    s = str(v).replace('€','').strip()
    if ',' in s and '.' in s: s = s.replace('.','')
    s = s.replace(',','.')
    try: return float(s)
    except: return 0.0

def price_ok(tp, np, l1):
    if np <= 0 or tp <= 0: return True
    if l1 in {"Books","Stationery","Toys","Music & Films","Gaming"}: return np <= tp*1.5
    elif tp <= 30: return np <= tp*1.5
    else: return np <= max(tp*0.40, 45)

def title_sim(a, b): return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100
def safe(v): return html_lib.escape(str(v))

# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
# DATA LOADING - From local file in repo
# ─────────────────────────────────────────────────────────────
EXCEL_FILE = "Recommendations GitHub.xlsx"  # File in same folder as app.py

@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_all_data():
    """Load ALL sheets from Excel file in repo"""
    excel_file = pd.ExcelFile(EXCEL_FILE, engine='openpyxl')
    available_sheets = excel_file.sheet_names
    
    # Load Products
    if 'Products' in available_sheets:
        dp = pd.read_excel(excel_file, sheet_name='Products')
        dp.columns = dp.columns.str.strip()
    else:
        dp = pd.DataFrame()
    
    # Load History
    if 'History' in available_sheets:
        dh = pd.read_excel(excel_file, sheet_name='History')
        dh.columns = dh.columns.str.strip()
    else:
        dh = pd.DataFrame()
    
    # Load Slot_Matrix
    if 'Slot_Matrix' in available_sheets:
        ds = pd.read_excel(excel_file, sheet_name='Slot_Matrix')
        ds.columns = ds.columns.str.strip()
    else:
        ds = pd.DataFrame()
    
    # Load Books
    if 'Books' in available_sheets:
        db = pd.read_excel(excel_file, sheet_name='Books')
        db.columns = db.columns.str.strip()
    else:
        db = pd.DataFrame()
    
    # Add compat columns to Products
    if not dp.empty:
        parts = [dp[c].fillna('').astype(str).str.strip() for c in COMPAT_COLS if c in dp.columns]
        if parts:
            dp[CC] = parts[0]
            for p in parts[1:]:
                empty = dp[CC]==''
                dp.loc[empty, CC] = p[empty]
                dp.loc[~empty, CC] = dp.loc[~empty, CC] + ';' + p[~empty]
            dp[CC] = dp[CC].str.strip(';').str.replace(';;',';')
        else:
            dp[CC] = ''
    
    if not db.empty and CC not in db.columns:
        db[CC] = ''
    
    return dp, dh, ds, db, available_sheets

# Load all data from Excel file
try:
    df_products, df_history, df_slots, df_books, sheets_loaded = load_all_data()
    compat_cols_found = [c for c in COMPAT_COLS if c in df_products.columns]
except FileNotFoundError:
    st.error(f"🚨 File not found: `{EXCEL_FILE}`. Please add it to your GitHub repo.")
    st.stop()
except ImportError:
    st.error("🚨 openpyxl not installed. Add 'openpyxl' to requirements.txt")
    st.stop()
except Exception as e:
    st.error(f"🚨 Error loading data: {e}")
    st.code(traceback.format_exc())
    st.stop()

# 🟢 SIDEBAR STYLING - Public.gr Style
st.sidebar.markdown("""
<style>
    /* Light gray background like Public.gr menu */
    [data-testid="stSidebar"] > div:first-child {
        background-color: #f5f5f5 !important;
        padding-top: 0 !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #f5f5f5 !important;
    }
    
    /* Hide the default sidebar collapse button completely */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
    
    /* Sidebar header bar - orange like Public */
    .sidebar-header {
        background-color: #ff5e00;
        color: white;
        padding: 18px 20px;
        margin: 0 -1rem 15px -1rem;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 18px;
        font-weight: 700;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    /* X close button in header */
    .sidebar-close-btn {
        background: transparent;
        border: none;
        color: white;
        font-size: 22px;
        font-weight: 300;
        cursor: pointer;
        padding: 5px 10px;
        line-height: 1;
        border-radius: 4px;
        transition: background 0.15s ease;
    }
    
    .sidebar-close-btn:hover {
        background: rgba(255,255,255,0.2);
    }
    
    /* Style the cluster buttons to look like Public.gr tiles */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
        background: #ffffff !important;
        border: 1px solid #eaeaea !important;
        border-radius: 12px !important;
        padding: 15px 8px !important;
        min-height: 100px !important;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #333 !important;
        transition: all 0.15s ease !important;
        white-space: pre-line !important;
        line-height: 1.3 !important;
        box-shadow: none !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {
        border-color: #ff5e00 !important;
        background: #ffffff !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
        transform: translateY(-1px);
    }
    
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:focus {
        border-color: #ff5e00 !important;
        border-width: 2px !important;
        background: #fff !important;
        box-shadow: 0 4px 12px rgba(255, 94, 0, 0.15) !important;
    }
    
    /* Section divider */
    .section-divider {
        border: none;
        border-top: 1px solid #e0e0e0;
        margin: 20px 0 15px 0;
    }
    
    /* Section headers */
    .sidebar-section {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 11px;
        font-weight: 700;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 15px 0 10px 0;
    }
    
    /* Style selectboxes */
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: #ffffff !important;
        border-radius: 8px !important;
        border-color: #ddd !important;
        font-size: 13px !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox > div > div:hover {
        border-color: #ff5e00 !important;
    }
    
    /* Style text input */
    [data-testid="stSidebar"] .stTextInput > div > div {
        background: #ffffff !important;
        border-radius: 8px !important;
        font-size: 13px !important;
    }
    
    [data-testid="stSidebar"] .stTextInput > div > div:focus-within {
        border-color: #ff5e00 !important;
    }
    
    /* Refresh button at bottom */
    .refresh-btn {
        background: #ffffff !important;
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        color: #666 !important;
        font-size: 12px !important;
        padding: 10px !important;
        width: 100%;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    
    .refresh-btn:hover {
        background: #f9f9f9 !important;
        border-color: #ccc !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar header - orange bar like Public.gr with X close button
st.sidebar.markdown('''
<div class="sidebar-header">
    <span>Κατηγορίες</span>
    <button class="sidebar-close-btn" onclick="window.parent.document.querySelector('[data-testid=\\'stSidebarCollapsedControl\\'] button').click();" title="Κλείσιμο">✕</button>
</div>
''', unsafe_allow_html=True)

# Use session state for cluster selection
if 'active_cluster' not in st.session_state:
    st.session_state.active_cluster = "Smartphones"

active_cluster = st.session_state.active_cluster

# Dynamic CSS for active state border AND SVG icons
smartphones_border = "2px solid #ff5e00" if active_cluster == "Smartphones" else "1px solid #eaeaea"
books_border = "2px solid #ff5e00" if active_cluster == "Kids Books" else "1px solid #eaeaea"

st.sidebar.markdown(f"""
<style>
    /* Tile button base styling */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {{
        background: #ffffff !important;
        border-radius: 12px !important;
        min-height: 95px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #333 !important;
        white-space: pre-line !important;
        line-height: 1.3 !important;
        padding-top: 45px !important;
    }}
    
    /* Smartphones button */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child button {{
        border: {smartphones_border} !important;
    }}
    
    /* Kids Books button */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child button {{
        border: {books_border} !important;
    }}
    
    /* Hover effect */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {{
        border-color: #ff5e00 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    }}
    
    /* Hide the emoji text, show only the label */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button p {{
        font-size: 11px !important;
        margin-top: 5px !important;
    }}
</style>
""", unsafe_allow_html=True)

# Create tile buttons with text labels (icons added via HTML below)
col1, col2 = st.sidebar.columns(2)

with col1:
    if st.button("Τηλεφωνία,\nTablets &\nWearables", key="btn_smartphones", use_container_width=True):
        st.session_state.active_cluster = "Smartphones"
        st.rerun()

with col2:
    if st.button("Παιδικά\nΒιβλία", key="btn_kids_books", use_container_width=True):
        st.session_state.active_cluster = "Kids Books"
        st.rerun()

# Inject SVG icons on top of buttons using absolute positioning
st.sidebar.markdown("""
<style>
    /* Position icons above button text */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child button::before {
        content: '';
        display: block;
        width: 28px;
        height: 28px;
        margin: 0 auto 8px auto;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='2' width='14' height='20' rx='2' ry='2'%3E%3C/rect%3E%3Cline x1='12' y1='18' x2='12.01' y2='18'%3E%3C/line%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        position: absolute;
        top: 15px;
        left: 50%;
        transform: translateX(-50%);
    }
    
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child button::before {
        content: '';
        display: block;
        width: 28px;
        height: 28px;
        margin: 0 auto 8px auto;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'%3E%3C/path%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'%3E%3C/path%3E%3C/svg%3E");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        position: absolute;
        top: 15px;
        left: 50%;
        transform: translateX(-50%);
    }
    
    /* Make buttons relative for absolute positioning of icons */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
        position: relative !important;
    }
</style>
""", unsafe_allow_html=True)

# Divider
st.sidebar.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# TRIGGER SELECTION
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    if df_products.empty:
        st.error("🚨 Products data not loaded! Please upload the Recommendations.xlsx file.")
        st.stop()
    
    # Check if required columns exist
    required_cols = ['Level 2', 'Hierarchy', 'Title']
    missing_cols = [c for c in required_cols if c not in df_products.columns]
    if missing_cols:
        st.error(f"🚨 Missing columns in Products: {missing_cols}")
        st.write("Available columns:", list(df_products.columns))
        st.stop()
    
    phones = df_products[(df_products['Level 2']=='Mobiles')&(df_products['Hierarchy']=='Smartphones')]
    if phones.empty:
        phones = df_products[df_products['Level 2']=='Mobiles']
    if phones.empty:
        st.error("🚨 No phones found in Products data!")
        st.stop()
    
    st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Smartphone</p>', unsafe_allow_html=True)
    sel = st.sidebar.selectbox("", phones['Title'].unique(), label_visibility="collapsed")
    trigger = phones[phones['Title']==sel].iloc[0] if sel else None

elif active_cluster == "Kids Books":
    if df_books.empty:
        st.error("🚨 Books sheet not found!")
        st.stop()
    
    kids_books = df_books[
        (df_books['Level 1'] == 'Books') & 
        (df_books['Level 2'].isin(KIDS_BOOKS_LEVEL2))
    ]
    
    if kids_books.empty:
        kids_books = df_books[df_books['Level 1'] == 'Books']
    
    if kids_books.empty:
        st.error("🚨 No kids books found!")
        st.stop()
    
    # Series filter - show most popular series (by book count)
    if 'Σειρά βιβλίου' in kids_books.columns:
        series_col = kids_books['Σειρά βιβλίου'].fillna('').astype(str)
        series_col = series_col[(series_col != '0') & (series_col != '') & (series_col.str.lower() != 'nan') & (series_col.str.lower() != 'n/a')]
        
        if len(series_col) > 0:
            # Get series sorted by popularity (most books first)
            series_counts = series_col.value_counts()
            
            # Take top 200 most popular series
            top_series = series_counts.head(200)
            
            # Create ordered list of (display_name, actual_name) tuples
            series_items = [(f"{name} ({count})", name) for name, count in top_series.items()]
            
            st.sidebar.markdown('<p class="sidebar-section">Φιλτράρισμα ανά Σειρά</p>', unsafe_allow_html=True)
            
            # Add search box for series
            series_search = st.sidebar.text_input("🔍 Αναζήτηση σειράς:", placeholder="π.χ. Harry Potter", label_visibility="collapsed")
            
            if series_search:
                # Filter ALL series by search term (not just top 200)
                matching = [(f"{name} ({count})", name) for name, count in series_counts.items() 
                           if series_search.lower() in name.lower()][:100]
                series_options = ['Όλες οι σειρές'] + [m[0] for m in matching]
                series_display = {m[0]: m[1] for m in matching}
            else:
                # Show top 200 by popularity
                series_options = ['Όλες οι σειρές'] + [item[0] for item in series_items]
                series_display = {item[0]: item[1] for item in series_items}
            
            selected_series_display = st.sidebar.selectbox(
                "", 
                series_options,
                label_visibility="collapsed"
            )
            
            if selected_series_display != 'Όλες οι σειρές':
                # Get actual series name (without count)
                actual_series = series_display.get(selected_series_display, selected_series_display)
                kids_books = kids_books[kids_books['Σειρά βιβλίου'] == actual_series]
    
    # 🟢 MODE TOGGLE: Two recommendation strategies
    st.sidebar.markdown('<p class="sidebar-section">Λογική Προτάσεων</p>', unsafe_allow_html=True)
    books_mode = st.sidebar.radio(
        "",
        options=["Option A: Series First", "Option B: Next in Series"],
        index=0,
        label_visibility="collapsed",
        help="Option A: Up to 10 series books, then cross-sell. Option B: Max 6 'next' books + 4 cross-sell"
    )
    
    # Store mode in session state
    st.session_state.books_mode = "A" if "Option A" in books_mode else "B"
    
    st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Βιβλίο</p>', unsafe_allow_html=True)
    sel = st.sidebar.selectbox("", kids_books['Title'].unique(), label_visibility="collapsed")
    
    # When selecting a book, prefer the row that has a valid series
    if sel:
        matching_books = kids_books[kids_books['Title'] == sel].copy()
        
        if len(matching_books) > 1 and 'Σειρά βιβλίου' in matching_books.columns:
            # Sort to put rows with valid series first
            matching_books['_has_series'] = matching_books['Σειρά βιβλίου'].apply(
                lambda x: 0 if (pd.isna(x) or str(x).strip().lower() in ['', '0', 'nan']) else 1
            )
            matching_books = matching_books.sort_values('_has_series', ascending=False)
        
        trigger = matching_books.iloc[0]
    else:
        trigger = None

if trigger is None:
    st.warning("Please select an item from the sidebar.")
    st.stop()

# ─────────────────────────────────────────────────────────────
# DISPLAY HEADER
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    st.markdown('<div class="public-header">Επιλογές για εσένα</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Συμβατά αξεσουάρ για το <b>{sel}</b></p>", unsafe_allow_html=True)
else:
    st.markdown('<div class="public-header">Διάλεξε κι άλλα!</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Προτάσεις με βάση το <b>{sel}</b></p>", unsafe_allow_html=True)

# Sidebar Card
card_title = safe(str(trigger.get('Title', sel)))
card_sku = safe(str(trigger.get('Material', 'N/A')))
card_img = safe(str(trigger.get('Thumbnails', '')).strip())
if not card_img or card_img == 'nan':
    card_img = "https://via.placeholder.com/150?text=No+Image"
card_avail = safe(str(trigger.get('AVAILABILITY', 'Άμεσα Διαθέσιμο')))
avail_theme = "avail-blue" if card_avail in ["Κατόπιν Παραγγελίας", "Αναμένεται Σύντομα", "Διαθέσιμο με παραγγελία"] else "avail-green"

try:
    t_price = parse_euro_price(trigger.get('LIST PRICE', 0))
except:
    t_price = 0.0
p_int = f"{int(t_price)}"
p_dec = f"{t_price:.2f}".split('.')[1]

sidebar_card_html = f"""
<!DOCTYPE html><html><head><style>
body {{ margin:0; padding:0; background:transparent; font-family:-apple-system,BlinkMacSystemFont,sans-serif; }}
.sb-card {{ border:1px solid #eaeaea; border-radius:12px; overflow:hidden; background:#fff; margin-top:5px; }}
.sb-img-container {{ padding:20px; text-align:center; background:#fff; }}
.sb-img {{ max-width:100%; max-height:220px; object-fit:contain; }}
.sb-details {{ background:#f8f9fa; padding:15px; border-top:1px solid #eaeaea; }}
.sb-title {{ font-size:14px; font-weight:700; color:#222; margin-bottom:6px; line-height:1.3; }}
.sb-sku {{ font-size:10px; color:#666; margin-bottom:10px; }}
.sb-avail-badge {{ display:inline-flex; align-items:center; gap:6px; font-size:12px; padding:4px 8px; border-radius:6px; font-weight:700; margin-bottom:15px; }}
.avail-green {{ background-color:#e5f3f0; color:#00897b; }}
.avail-blue {{ background-color:#e6f0f6; color:#2385aa; }}
.sb-bottom-row {{ display:flex; justify-content:space-between; align-items:center; border-top:1px solid #eaeaea; padding-top:15px; }}
.sb-price-wrap {{ color:#ff5e00; font-weight:800; font-size:24px; display:flex; align-items:flex-start; line-height:1; }}
.sb-price-dec {{ font-size:13px; font-weight:700; margin-top:2px; }}
.sb-btn {{ background:#ff5e00; color:#fff; border:none; border-radius:8px; padding:10px 16px; font-size:14px; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:6px; }}
</style></head><body>
<div class="sb-card">
    <div class="sb-img-container"><img class="sb-img" src="{card_img}" alt="Product"></div>
    <div class="sb-details">
        <div class="sb-title">{card_title}</div>
        <div class="sb-sku">ΚΩΔΙΚΟΣ: {card_sku}</div>
        <div class="sb-avail-badge {avail_theme}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
            {card_avail}
        </div>
        <div class="sb-bottom-row">
            <div class="sb-price-wrap">{p_int}<span class="sb-price-dec">,{p_dec}€</span></div>
            <button class="sb-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle>
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                </svg>
                Προσθήκη
            </button>
        </div>
    </div>
</div>
</body></html>
"""

with st.sidebar:
    components.html(sidebar_card_html, height=500, scrolling=False)
    
    # Footer with clear cache
    st.markdown("---")
    if st.button("🔄 Ανανέωση Δεδομένων", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS ENGINE (DUAL MODE)
# ─────────────────────────────────────────────────────────────
def run_books_engine(trigger, df_all, df_history, mode='A'):
    """
    Kids Books Recommendation Engine with TWO MODES:
    
    Mode A (Management): Series First
    - Priority 1: Fill up to 10 slots with series books
    - Priority 2: Cross-sell (up to 4 slots if series < 10)
    - Priority 3: Category Discovery (remaining slots)
    
    Mode B (Next in Series):
    - Priority 1: Up to 6 books using "next in series" logic
    - Priority 2: Cross-sell (4 slots always)
    - If fewer than 6 books remaining, show "start from beginning" books
    """
    diag = []
    slot_notes = {}
    all_recs = []
    used_materials = set()
    used_titles = set()  # Track titles to prevent showing same book
    
    # 🟢 HARRY POTTER PREDEFINED ORDER
    # Map title keywords to reading order (1-7 for main series, 8+ for spinoffs)
    HARRY_POTTER_ORDER = {
        # Greek titles
        'φιλοσοφική λίθος': 1, 'philosopher': 1, "sorcerer's stone": 1,
        'μυστικό δωμάτιο': 2, 'chamber of secrets': 2, 'κάμαρα': 2,
        'αιχμάλωτος': 3, 'αζκαμπάν': 3, 'prisoner of azkaban': 3,
        'κύπελλο φωτιάς': 4, 'goblet of fire': 4, 'κύπελλο της φωτιάς': 4,
        'τάγμα του φοίνικα': 5, 'order of the phoenix': 5, 'φοίνικα': 5,
        'ημίαιμος πρίγκιψ': 6, 'half-blood prince': 6, 'ημίαιμος': 6,
        'κλήροι του θανάτου': 7, 'deathly hallows': 7, 'θανάτου': 7,
        # Spinoffs (order 8+)
        'καταραμένο παιδί': 8, 'cursed child': 8,
        'φανταστικά ζώα': 9, 'fantastic beasts': 9,
        'quidditch': 10, 'κουίντιτς': 10,
        'beedle': 11, 'μπιντλ': 11,
    }
    
    def get_hp_order(title):
        """Get Harry Potter reading order from title"""
        title_lower = str(title).lower()
        for keyword, order in HARRY_POTTER_ORDER.items():
            if keyword in title_lower:
                return order
        return 99  # Unknown
    
    def is_harry_potter_series(series_name):
        """Check if this is the Harry Potter series"""
        series_lower = str(series_name).lower()
        return 'harry potter' in series_lower or 'χάρι πότερ' in series_lower or 'χαρι ποτερ' in series_lower
    
    # 🟢 HELPER: Detect if a book is a box set
    def is_box_set(title):
        """Check if title indicates a box set/collection"""
        title_lower = str(title).lower()
        box_keywords = ['box set', 'boxset', 'box-set', 'κασετίνα', 'συλλογή', 'collection', 
                        'βαλιτσάκι', 'σετ βιβλίων', 'book set', 'complete series', 'books 1-']
        return any(kw in title_lower for kw in box_keywords)
    
    # 🟢 HELPER: Check if box set is complete (contains all books)
    def is_complete_box_set(title):
        """Check if box set appears to be a complete collection"""
        title_lower = str(title).lower()
        complete_keywords = ['complete', 'ολοκληρωμένη', 'πλήρης', 'all books', 'όλα τα βιβλία', 
                            'full collection', '1-7', '1-8', 'complete collection']
        return any(kw in title_lower for kw in complete_keywords)
    
    # 🟢 HELPER: Extract canonical book identifier from title (improved)
    def get_canonical_book_name(title, orig_title=''):
        """
        Extract the core book name to detect same book in different editions.
        Returns normalized title for comparison.
        """
        import pandas as pd
        import re
        
        title_lower = str(title).lower().strip() if title and str(title) != 'nan' else ''
        
        # Handle NaN properly - check with pandas
        orig_lower = ''
        if orig_title is not None and not pd.isna(orig_title):
            orig_str = str(orig_title).lower().strip()
            if orig_str and orig_str != 'nan':
                orig_lower = orig_str
        
        # Use original title if available, otherwise use title
        canonical = orig_lower if orig_lower else title_lower
        
        # If still empty, return empty string
        if not canonical or canonical == 'nan':
            return title_lower if title_lower and title_lower != 'nan' else ''
        
        # Common series prefixes to strip
        prefixes = [
            'ο χάρι πότερ και ', 'ο χαρι ποτερ και ', 'harry potter and the ', 'harry potter and ',
            'fantastic beasts: ', 'φανταστικά ζώα: ', 'φανταστικά ζώα και ',
            'diary of a wimpy kid: ', 'diary of a wimpy kid ',
            'dog man: ', 'dog man ', 'captain underpants: ', 'captain underpants ',
        ]
        
        for prefix in prefixes:
            if canonical.startswith(prefix):
                canonical = canonical[len(prefix):]
                break
        
        # 🟢 UNIVERSAL EDITION STRIPPING
        # Keywords that indicate an edition variant
        edition_keywords = [
            'edition', 'έκδοση', 'illustrated', 'εικονογραφημένο', 'εικονογραφημένη',
            'collector', 'συλλεκτική', 'deluxe', 'anniversary', 'special', 'gift',
            'paperback', 'hardcover', 'hardback', 'softcover', 'minalima',
            'gryffindor', 'slytherin', 'hufflepuff', 'ravenclaw', 'rehearsal',
        ]
        
        # 1. FIRST: Strip parenthetical editions "(Something Edition)"
        paren_match = re.search(r'\s*\([^)]*(?:' + '|'.join(edition_keywords) + r')[^)]*\)\s*$', canonical)
        if paren_match:
            canonical = canonical[:paren_match.start()]
        
        # 2. THEN: Check for " - Something" or ": Something" patterns
        # Only strip if the ENTIRE suffix part is edition-related (not meaningful content)
        for delimiter in [' - ', ': ', ' – ', ' — ']:
            if delimiter in canonical:
                parts = canonical.split(delimiter)
                if len(parts) >= 2:
                    suffix_part = parts[-1].lower().strip()
                    # Only strip if suffix is SHORT and contains edition keyword
                    # This prevents stripping "parts one and two" but strips "gryffindor edition"
                    words = suffix_part.split()
                    if len(words) <= 4 and any(kw in suffix_part for kw in edition_keywords):
                        canonical = delimiter.join(parts[:-1])
        
        # 3. Strip audiobook/CD suffixes (so CD version matches regular book)
        audiobook_suffixes = [' cd', ' audiobook', ' audio book', ' mp3', ' audio']
        for suffix in audiobook_suffixes:
            if canonical.endswith(suffix):
                canonical = canonical[:-len(suffix)]
                break
        
        # 4. Normalize apostrophes (curly → straight)
        canonical = canonical.replace("'", "'").replace("'", "'").replace("`", "'")
        
        return canonical.strip()
    
    # Trigger attributes - with robust extraction
    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    
    # 🟢 FIX: More robust series extraction
    t_series_raw = trigger.get('Σειρά βιβλίου', None)
    if t_series_raw is None:
        # Try alternate column names
        for col in trigger.index:
            if 'σειρά' in col.lower() or 'series' in col.lower():
                t_series_raw = trigger.get(col, None)
                break
    t_series = str(t_series_raw).strip() if t_series_raw is not None and not pd.isna(t_series_raw) else ''
    
    t_age = str(trigger.get('Ηλικία', '')).strip()
    t_rec_age = str(trigger.get('Προτεινόμενη Ηλικία', '')).strip()
    t_cover = str(trigger.get('Εξώφυλλο', '')).strip()
    t_dims = str(trigger.get('Διαστάσεις', '')).strip()
    t_illus = str(trigger.get('Λεπτομέρειες εικονογράφησης', '')).strip()
    t_pub_series = str(trigger.get('Εκδοτική Σειρά', '')).strip()
    t_orig_title = str(trigger.get('Τίτλος πρωτοτύπου', '')).strip()
    t_hierarchy = str(trigger.get('Hierarchy', '')).strip()
    t_level2 = str(trigger.get('Level 2', '')).strip()
    t_brand = str(trigger.get('Brand', '')).strip()
    t_price = parse_euro_price(trigger.get('LIST PRICE', 0))
    
    effective_age = t_age if t_age and t_age != 'nan' and t_age != '0' else t_rec_age
    allowed_ages = get_allowed_ages(effective_age)
    has_series = is_valid_series(t_series)
    
    # 🟢 BOX SET DETECTION
    trigger_is_box_set = is_box_set(tt)
    trigger_is_complete_box = trigger_is_box_set and is_complete_box_set(tt)
    
    # 🟢 CANONICAL BOOK NAME: To detect same book in different editions
    trigger_canonical = get_canonical_book_name(tt, t_orig_title)
    used_titles.add(trigger_canonical)  # Never recommend the same book as trigger
    
    box_status = "complete box set" if trigger_is_complete_box else ("partial box set" if trigger_is_box_set else "individual book")
    diag.append(("0. Trigger", "", f"Series: '{t_series}' (valid: {has_series}), Age: '{effective_age}', Type: {box_status}"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 1: SERIES ENGINE (Slots 1-7, or skip for complete box sets)
    # ══════════════════════════════════════════════════════════
    series_notes = ["=== PRIORITY 1: SERIES ENGINE ==="]
    series_count = 0
    
    # 🟢 BOX SET RULE: Complete box sets should NOT show series books (only cross-sell)
    if trigger_is_complete_box:
        series_notes.append("⚠ Complete box set detected - skipping series books, only showing cross-sell")
        diag.append(("1. Series Engine", 0, "Skipped (complete box set)"))
    elif has_series:
        # Get all books from same series
        books_only = df_all[df_all['Level 1'] == 'Books'].copy()
        
        # 🟢 FIX: Find series column name dynamically
        series_col = 'Σειρά βιβλίου'
        if series_col not in books_only.columns:
            for col in books_only.columns:
                if 'σειρά' in col.lower() or 'series' in col.lower():
                    series_col = col
                    break
        
        if series_col in books_only.columns:
            series_books = books_only[
                books_only[series_col].fillna('').astype(str).str.strip() == t_series
            ].copy()
        else:
            series_books = pd.DataFrame()
            series_notes.append(f"⚠ Series column not found!")
        
        series_notes.append(f"Found {len(series_books)} books in series '{t_series}'")
        
        # Exclude trigger itself
        series_books = series_books[series_books['Material'] != tm]
        series_notes.append(f"After excluding trigger: {len(series_books)}")
        
        # 🟢 SAME BOOK DETECTION (improved): Use canonical name to detect same book
        # This catches both original title matches AND title pattern matches
        before = len(series_books)
        series_books['_canonical'] = series_books.apply(
            lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', '')), axis=1
        )
        
        series_books = series_books[series_books['_canonical'] != trigger_canonical]
        series_notes.append(f"Excluded same book (canonical): {before}→{len(series_books)}")
        
        # 🟢 BOX SET RULE: Individual books should NOT show box sets
        if not trigger_is_box_set and not series_books.empty:
            before = len(series_books)
            series_books = series_books[~series_books['Title'].apply(is_box_set)]
            series_notes.append(f"Excluded box sets: {before}→{len(series_books)}")
        
        # 🟢 LANGUAGE FILTER (HARD): Must match language - English with English, Greek with Greek
        if t_level2:
            before = len(series_books)
            series_books = series_books[series_books['Level 2'] == t_level2]
            series_notes.append(f"Language filter ({t_level2}): {before}→{len(series_books)}")
        
        # 🟢 NOVELTY LANGUAGE FILTER: Exclude Latin/Ancient Greek/Irish etc. novelty editions
        # These are special editions, not regular English/Greek books
        def is_novelty_language(title):
            title_lower = str(title).lower()
            novelty_langs = [
                '(ancient greek)', '(latin)', '(irish)', '(scots)', '(welsh)', 
                '(gaelic)', '(αρχαία ελληνικά)', '(λατινικά)',
            ]
            return any(lang in title_lower for lang in novelty_langs)
        
        if not series_books.empty:
            before = len(series_books)
            series_books = series_books[~series_books['Title'].apply(is_novelty_language)]
            if before != len(series_books):
                series_notes.append(f"Excluded novelty languages: {before}→{len(series_books)}")
        
        # 🟢 AUDIOBOOK/CD FILTER: Exclude audiobooks from book recommendations
        def is_audiobook(title):
            title_lower = str(title).lower()
            audiobook_keywords = [' cd', ' audiobook', ' audio book', ' mp3', 'ηχητικό', 'ακουστικό']
            return any(kw in title_lower for kw in audiobook_keywords)
        
        if not series_books.empty:
            before = len(series_books)
            series_books = series_books[~series_books['Title'].apply(is_audiobook)]
            if before != len(series_books):
                series_notes.append(f"Excluded audiobooks/CDs: {before}→{len(series_books)}")
        
        # 🟢 EDITION LINE EXTRACTION: Detect edition style from title
        def get_edition_line(title):
            """Extract edition line from title (e.g., 'Gryffindor Edition' → 'gryffindor')"""
            title_lower = str(title).lower()
            
            # House editions
            for house in ['gryffindor', 'slytherin', 'hufflepuff', 'ravenclaw']:
                if house in title_lower:
                    return 'house_' + house
            
            # Other edition patterns
            edition_patterns = [
                ('minalima', 'minalima'),
                ('illustrated', 'illustrated'),
                ('20th anniversary', 'anniversary_20'),
                ('25th anniversary', 'anniversary_25'),
                ('anniversary', 'anniversary'),
                ('deluxe', 'deluxe'),
                ('collector', 'collector'),
                ('special', 'special'),
                ('gift', 'gift'),
            ]
            
            for pattern, line in edition_patterns:
                if pattern in title_lower:
                    return line
            
            return 'standard'  # No special edition detected
        
        trigger_edition_line = get_edition_line(tt)
        series_notes.append(f"Trigger edition line: {trigger_edition_line}")
        t_pub_date = str(trigger.get('Ημερ/νία έκδοσης', '')).strip()
        series_notes.append(f"Trigger attrs: Cover={t_cover}, Dims={t_dims}, PubDate={t_pub_date}, Price={t_price}")
        
        # 🟢 FORMAT PREFERENCE: Score books by format match (NOT a hard filter)
        # Books with matching format get higher scores, but ALL series books are kept
        FORMAT_MATCH_BOOST = 1000  # Boost for matching format
        EDITION_LINE_BOOST = 5000  # Strong boost for same edition line (Gryffindor with Gryffindor, etc.)
        
        if not series_books.empty:
            series_books['Format_Score'] = 0
            
            # 0. EDITION LINE matching (strongest signal!)
            series_books['_edition_line'] = series_books['Title'].apply(get_edition_line)
            edition_match = series_books['_edition_line'] == trigger_edition_line
            series_books.loc[edition_match, 'Format_Score'] += EDITION_LINE_BOOST
            match_count = edition_match.sum()
            series_notes.append(f"Edition line match ({trigger_edition_line}): {match_count} books boosted")
            
            # 1. Cover type bonus
            if t_cover and t_cover != 'nan' and t_cover != '0' and 'Εξώφυλλο' in series_books.columns:
                series_books.loc[
                    series_books['Εξώφυλλο'].fillna('').astype(str).str.strip() == t_cover, 
                    'Format_Score'
                ] += FORMAT_MATCH_BOOST
                match_count = (series_books['Εξώφυλλο'].fillna('').astype(str).str.strip() == t_cover).sum()
                series_notes.append(f"Cover match ({t_cover}): {match_count} books boosted")
            
            # 2. Dimensions bonus
            if t_dims and t_dims != 'nan' and t_dims != 'NaN' and 'Διαστάσεις' in series_books.columns:
                series_books.loc[
                    series_books['Διαστάσεις'].fillna('').astype(str).str.strip() == t_dims,
                    'Format_Score'
                ] += FORMAT_MATCH_BOOST
                match_count = (series_books['Διαστάσεις'].fillna('').astype(str).str.strip() == t_dims).sum()
                series_notes.append(f"Dimensions match: {match_count} books boosted")
            
            # 3. Publishing series bonus
            if t_pub_series and t_pub_series != 'nan' and t_pub_series != '0' and 'Εκδοτική Σειρά' in series_books.columns:
                series_books.loc[
                    series_books['Εκδοτική Σειρά'].fillna('').astype(str).str.strip() == t_pub_series,
                    'Format_Score'
                ] += FORMAT_MATCH_BOOST
            
            # 4. Illustration details bonus
            if t_illus and t_illus != 'nan' and t_illus != '0' and 'Λεπτομέρειες εικονογράφησης' in series_books.columns:
                series_books.loc[
                    series_books['Λεπτομέρειες εικονογράφησης'].fillna('').astype(str).str.strip() == t_illus,
                    'Format_Score'
                ] += FORMAT_MATCH_BOOST
        
        # Score and sort series books
        if not series_books.empty:
            series_books['Final_Score'] = SERIES_BOOST + series_books['Format_Score']
            if 'AVAILABILITY' in series_books.columns:
                series_books.loc[series_books['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
            
            # 🔍 DEBUG: Show top candidates with their attributes
            debug_cols = ['Title', 'Εξώφυλλο', 'Διαστάσεις', 'Εκδοτική Σειρά', 'Ημερ/νία έκδοσης', 'LIST PRICE', 'Format_Score']
            debug_cols = [c for c in debug_cols if c in series_books.columns]
            top_candidates = series_books.nlargest(8, 'Format_Score')[debug_cols]
            series_notes.append(f"Top candidates by format score:")
            for _, row in top_candidates.iterrows():
                pub_date = row.get('Ημερ/νία έκδοσης', 'N/A')
                series_notes.append(f"  - {row['Title'][:40]}... | Cover: {row.get('Εξώφυλλο', 'N/A')} | Dims: {row.get('Διαστάσεις', 'N/A')} | PubDate: {pub_date} | Score: {row.get('Format_Score', 0)}")
            
            # Also show some lower-scored books for comparison
            other_candidates = series_books.nsmallest(5, 'Format_Score')[debug_cols]
            series_notes.append(f"Other candidates (lower scores):")
            for _, row in other_candidates.iterrows():
                pub_date = row.get('Ημερ/νία έκδοσης', 'N/A')
                series_notes.append(f"  - {row['Title'][:40]}... | Cover: {row.get('Εξώφυλλο', 'N/A')} | Dims: {row.get('Διαστάσεις', 'N/A')} | PubDate: {pub_date} | Score: {row.get('Format_Score', 0)}")
            
            # 🔍 DEBUG: Check for duplicate canonicals (same book appearing twice)
            canonical_counts = series_books['_canonical'].value_counts()
            duplicates = canonical_counts[canonical_counts > 1]
            if len(duplicates) > 0:
                series_notes.append(f"⚠ Duplicate canonicals: {dict(duplicates.head(5))}")
            
            series_notes.append(f"Total series pool: {len(series_books)} books")
            series_notes.append(f"MODE: {'A (Series First)' if mode == 'A' else 'B (Next in Series)'}")
            
            # 🟢 PARTIAL BOX SET HANDLING (same for both modes)
            if trigger_is_box_set and not trigger_is_complete_box:
                box_sets_in_series = series_books[series_books['Title'].apply(is_box_set)]
                if not box_sets_in_series.empty:
                    for _, row in box_sets_in_series.head(2).iterrows():
                        if row['Material'] not in used_materials:
                            row_copy = row.copy()
                            row_copy['Assigned_Slot'] = series_count + 1
                            row_copy['Slot_Role'] = 'Other Box Set'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(row['Material'])
                            used_titles.add(get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', '')))
                            series_count += 1
                    series_notes.append(f"✓ Added other box sets: {series_count}")
            else:
                # ════════════════════════════════════════════════════════
                # MODE A: SERIES FIRST (Management's preference)
                # Fill up to 10 slots with series books
                # For HP: Use reading order, then spinoffs
                # ════════════════════════════════════════════════════════
                if mode == 'A':
                    max_series = 10
                    
                    # 🟢 HARRY POTTER: Use reading order for Mode A too
                    if is_harry_potter_series(t_series):
                        trigger_order = get_hp_order(tt)
                        series_notes.append(f"Harry Potter (Mode A): trigger is book #{trigger_order}")
                        
                        series_books['_hp_order'] = series_books['Title'].apply(get_hp_order)
                        
                        # Sort by HP order first, then by format score
                        # Books after trigger come first, then books before (wrap around)
                        books_after = series_books[series_books['_hp_order'] > trigger_order].copy()
                        books_after = books_after.sort_values(['_hp_order', 'Final_Score'], ascending=[True, False])
                        
                        books_before = series_books[series_books['_hp_order'] < trigger_order].copy()
                        books_before = books_before.sort_values(['_hp_order', 'Final_Score'], ascending=[True, False])
                        
                        # Combined: after first, then before (reading order)
                        combined = pd.concat([books_after, books_before])
                        
                        for _, row in combined.iterrows():
                            if series_count >= max_series:
                                break
                            row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                            
                            if row['Material'] not in used_materials and row_canonical not in used_titles:
                                row_copy = row.copy()
                                row_copy['Assigned_Slot'] = series_count + 1
                                row_copy['Slot_Role'] = 'Series Book'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(row['Material'])
                                used_titles.add(row_canonical)
                                series_count += 1
                        
                        series_notes.append(f"✓ Mode A (HP): Added {series_count} books in reading order")
                    else:
                        # Non-HP series: Sort by format match + availability
                        series_books = series_books.sort_values('Final_Score', ascending=False)
                        
                        for _, row in series_books.iterrows():
                            if series_count >= max_series:
                                break
                            row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                            
                            if row['Material'] not in used_materials and row_canonical not in used_titles:
                                row_copy = row.copy()
                                row_copy['Assigned_Slot'] = series_count + 1
                                row_copy['Slot_Role'] = 'Series Book'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(row['Material'])
                                used_titles.add(row_canonical)
                                series_count += 1
                        
                        series_notes.append(f"✓ Mode A: Added {series_count} unique series books")
                
                # ════════════════════════════════════════════════════════
                # MODE B: NEXT IN SERIES (User's preference)
                # Max 6 series books using reading order:
                # Book 1 → 2,3,4,5,6,7 | Book 5 → 6,7,1,2,3,4
                # ════════════════════════════════════════════════════════
                else:  # mode == 'B'
                    # 🟢 HARRY POTTER: Use predefined reading order
                    if is_harry_potter_series(t_series):
                        trigger_order = get_hp_order(tt)
                        series_notes.append(f"Harry Potter: trigger is book #{trigger_order}")
                        
                        series_books['_hp_order'] = series_books['Title'].apply(get_hp_order)
                        
                        # 🟢 ONLY MAIN 7 BOOKS in series slots (spinoffs go to discovery)
                        main_7_books = series_books[series_books['_hp_order'] <= 7].copy()
                        spinoffs = series_books[series_books['_hp_order'] > 7].copy()
                        
                        series_notes.append(f"Main 7 pool: {len(main_7_books)} editions, Spinoffs: {len(spinoffs)}")
                        
                        # Books AFTER trigger (next in reading order) - ONLY from main 7
                        # Sort by: reading order first, then format score (prefer matching format)
                        books_after = main_7_books[main_7_books['_hp_order'] > trigger_order].copy()
                        books_after = books_after.sort_values(['_hp_order', 'Final_Score'], ascending=[True, False])
                        
                        # Books BEFORE trigger (start from beginning) - ONLY from main 7
                        books_before = main_7_books[main_7_books['_hp_order'] < trigger_order].copy()
                        books_before = books_before.sort_values(['_hp_order', 'Final_Score'], ascending=[True, False])
                        
                        # Count unique canonical titles
                        after_unique = books_after['_canonical'].nunique() if '_canonical' in books_after.columns else len(books_after)
                        before_unique = books_before['_canonical'].nunique() if '_canonical' in books_before.columns else len(books_before)
                        series_notes.append(f"Unique books - After #{trigger_order}: {after_unique}, Before: {before_unique}")
                        
                        # Add "next" books first (those after trigger in reading order)
                        next_added = 0
                        for _, row in books_after.iterrows():
                            if next_added >= 6:
                                break
                            row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                            
                            if row['Material'] not in used_materials and row_canonical not in used_titles:
                                row_copy = row.copy()
                                row_copy['Assigned_Slot'] = series_count + 1
                                row_copy['Slot_Role'] = 'Series Book'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(row['Material'])
                                used_titles.add(row_canonical)
                                series_count += 1
                                next_added += 1
                        
                        # Fill remaining (up to 6 total) with books from beginning
                        if next_added < 6 and not books_before.empty:
                            remaining_slots = 6 - next_added
                            series_notes.append(f"Added {next_added} after, filling {remaining_slots} from beginning")
                            
                            # 🔍 DEBUG: Show what canonicals we're checking
                            debug_canonicals = []
                            for _, row in books_before.iterrows():
                                if series_count >= 6:
                                    break
                                row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                                in_used = row_canonical in used_titles
                                debug_canonicals.append(f"hp{row['_hp_order']}: '{row_canonical}' in_used={in_used}")
                                
                                if row['Material'] not in used_materials and row_canonical not in used_titles:
                                    row_copy = row.copy()
                                    row_copy['Assigned_Slot'] = series_count + 1
                                    row_copy['Slot_Role'] = 'Start from Beginning'
                                    row_copy['Item_Rank'] = 1
                                    all_recs.append(row_copy)
                                    used_materials.add(row['Material'])
                                    used_titles.add(row_canonical)
                                    series_count += 1
                            
                            series_notes.append(f"Before-loop debug: {debug_canonicals[:10]}")
                        
                        series_notes.append(f"✓ Mode B (HP): Added {series_count} main series books")
                    
                    else:
                        # Non-HP series: Sort by format match + availability, cap at 6 unique titles
                        series_books = series_books.sort_values('Final_Score', ascending=False)
                        max_series = 6
                        
                        for _, row in series_books.iterrows():
                            if series_count >= max_series:
                                break
                            row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                            
                            if row['Material'] not in used_materials and row_canonical not in used_titles:
                                row_copy = row.copy()
                                row_copy['Assigned_Slot'] = series_count + 1
                                row_copy['Slot_Role'] = 'Series Book'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(row['Material'])
                                used_titles.add(row_canonical)
                                series_count += 1
                        
                        series_notes.append(f"✓ Mode B: Added {series_count} unique series books (max 6)")
    else:
        series_notes.append("No valid series found on trigger - skipping series engine")
    
    slot_notes[1] = series_notes
    diag.append(("1. Series Engine", series_count, f"Filled {series_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 2: CROSS-SELL (Toys & Stationery)
    # Up to 4 slots after series books
    # ══════════════════════════════════════════════════════════
    crosssell_notes = ["=== PRIORITY 2: CROSS-SELL ==="]
    crosssell_count = 0
    
    # Both modes: fill up to 4 cross-sell slots after series
    max_crosssell = min(4, 10 - series_count)
    crosssell_notes.append(f"Cross-sell: {max_crosssell} slots available (series filled {series_count})")
    
    if max_crosssell > 0:
        # Get Toys and Stationery
        toys = df_all[df_all['Level 1'] == 'Toys'].copy()
        stationery = df_all[df_all['Level 1'] == 'Stationery'].copy()
        
        crosssell_notes.append(f"Toys pool: {len(toys)}, Stationery pool: {len(stationery)}")
        
        # ══════════════════════════════════════════════════════════
        # AGE BRACKET SYSTEM (from Word doc)
        # ══════════════════════════════════════════════════════════
        def get_age_bracket(age_str):
            """Return age bracket number (1-7) based on trigger age"""
            if not age_str:
                return 5  # Default to preschool
            age_lower = str(age_str).lower().strip()
            
            # Bracket 1: Newborn (0-5 months)
            if any(x in age_lower for x in ['0+ μηνών', '0+ ετών', '3+ μηνών', '5+ μηνών']):
                return 1
            # Bracket 2: Sitter/Crawler (6-11 months)
            elif any(x in age_lower for x in ['6+ μηνών', '9+ μηνών']):
                return 2
            # Bracket 3: Early Toddler (1-1.5 years)
            elif any(x in age_lower for x in ['12+ μηνών', '1+ ετών', '1.5+ ετών']):
                return 3
            # Bracket 4: Advanced Toddler (2 years)
            elif any(x in age_lower for x in ['24+ μηνών', '2+ ετών']):
                return 4
            # Bracket 5: Preschool to Early Primary (3-6 years)
            elif any(x in age_lower for x in ['3+ ετών', '4+ ετών', '5+ ετών', '6+ ετών']):
                return 5
            # Bracket 6: Older Kids & Tweens (7-12 years)
            elif any(x in age_lower for x in ['7+ ετών', '8+ ετών', '9+ ετών', '10+ ετών', '11+ ετών', '12+ ετών']):
                return 6
            # Bracket 7: Teens & Collectors (13-18+ years)
            elif any(x in age_lower for x in ['13+ ετών', '14+ ετών', '15+ ετών', '16+ ετών', '17+ ετών', '18+ ετών']):
                return 7
            return 5  # Default
        
        def get_allowed_toy_ages(bracket):
            """Return allowed toy ages based on bracket"""
            if bracket == 1:
                return ['0+ μηνών', '0+ ετών', '3+ μηνών', '5+ μηνών', '6+ μηνών', '']
            elif bracket == 2:
                return ['6+ μηνών', '9+ μηνών', '12+ μηνών', '1+ ετών', '']
            elif bracket == 3:
                return ['9+ μηνών', '12+ μηνών', '1+ ετών', '1.5+ ετών', '24+ μηνών', '2+ ετών', '']
            elif bracket == 4:
                return ['1.5+ ετών', '24+ μηνών', '2+ ετών', '3+ ετών', '']
            elif bracket == 5:
                return ['3+ ετών', '4+ ετών', '5+ ετών', '6+ ετών', '7+ ετών', '8+ ετών', '']
            elif bracket == 6:
                return ['6+ ετών', '7+ ετών', '8+ ετών', '9+ ετών', '10+ ετών', '11+ ετών', '12+ ετών', '13+ ετών', '14+ ετών', '']
            elif bracket == 7:
                return ['10+ ετών', '11+ ετών', '12+ ετών', '13+ ετών', '14+ ετών', '15+ ετών', '16+ ετών', '17+ ετών', '18+ ετών', '']
            return ['']  # Allow all if unknown
        
        age_bracket = get_age_bracket(t_age)
        bracket_allowed_ages = get_allowed_toy_ages(age_bracket)
        crosssell_notes.append(f"Age bracket: {age_bracket} (trigger age: {t_age})")
        
        # ══════════════════════════════════════════════════════════
        # GENDER DETECTION (check Φύλο field first, then keywords)
        # ══════════════════════════════════════════════════════════
        def detect_gender(trigger_row, series_name, title, hierarchy):
            """Detect gender from data fields, hierarchy, or keywords"""
            # 1. Check Φύλο field if available
            gender_field = str(trigger_row.get('Φύλο', '')).lower().strip()
            if gender_field:
                if any(x in gender_field for x in ['κορίτσι', 'girl', 'θηλυκό', 'female']):
                    return 'girl'
                elif any(x in gender_field for x in ['αγόρι', 'boy', 'αρσενικό', 'male']):
                    return 'boy'
            
            # 2. Check hierarchy for gender indicators
            hier_lower = str(hierarchy).lower()
            if any(x in hier_lower for x in ['barbie', 'princess', 'πριγκίπισσα']):
                return 'girl'
            
            # 3. Check series/title keywords
            text = (str(series_name) + ' ' + str(title)).lower()
            girl_keywords = [
                'fairy', 'magic', 'princess', 'rainbow', 'unicorn', 'ballerina',
                'barbie', 'frozen', 'elsa', 'anna', 'mermaid', 'kitty', 'doll',
                'sparkle', 'glitter', 'flower', 'νεράιδα', 'πριγκίπισσα', 'κούκλα',
            ]
            boy_keywords = [
                'quest', 'warrior', 'beast', 'dragon', 'dinosaur', 'dino', 'monster',
                'ninja', 'pirate', 'superhero', 'hero', 'battle', 'fight', 'soldier',
                'robot', 'car', 'truck', 'spider-man', 'batman', 'marvel', 'avengers',
                'star wars', 'minecraft', 'pokemon', 'δεινόσαυρος', 'πειρατής', 'ήρωας',
            ]
            
            if any(kw in text for kw in girl_keywords):
                return 'girl'
            elif any(kw in text for kw in boy_keywords):
                return 'boy'
            return 'neutral'
        
        detected_gender = detect_gender(trigger, t_series, tt, t_hierarchy)
        crosssell_notes.append(f"Detected gender: {detected_gender}")
        
        # ══════════════════════════════════════════════════════════
        # HIERARCHY CATEGORY DETECTION (for cross-sell logic)
        # ══════════════════════════════════════════════════════════
        def get_hierarchy_category(hierarchy):
            """Categorize hierarchy for cross-sell logic"""
            hier_lower = str(hierarchy).lower()
            
            # Arts/Crafts books
            if any(x in hier_lower for x in ['ζωγραφικη', 'χειροτεχνι', 'αυτοκολλητ', 'δραστηριοτητ', 'τεχνη', 'μουσικ']):
                return 'arts'
            # STEM/Knowledge books
            elif any(x in hier_lower for x in ['εφευρεσ', 'πειραμ', 'αστρονομ', 'φυσικ', 'χημ', 'βιολογ', 'επιστημ', 
                                                'τεχνολογ', 'γνωσ', 'εγκυκλοπαιδ', 'περιβαλλον', 'οικολογ', 'ζωα', 
                                                'ιστορ', 'γεωγραφ', 'ατλαντ', 'μυθολογ']):
                return 'stem'
            # Preschool books
            elif any(x in hier_lower for x in ['προσχολικ', 'χρωματα', 'σχηματα', 'αντιθετ', 'αναγνωση', 'γραφη']):
                return 'preschool'
            # Fiction/Literature
            elif any(x in hier_lower for x in ['λογοτεχν', 'παραμυθ', 'μυθ', 'κομικ', 'χιουμορ', 'παιδικ']):
                return 'fiction'
            # Puzzle/Activity books
            elif any(x in hier_lower for x in ['παζλ', 'σπαζοκεφαλ', 'αινιγμ', 'παιχνιδ', 'διαδραστικ']):
                return 'activity'
            return 'general'
        
        hierarchy_category = get_hierarchy_category(t_hierarchy)
        crosssell_notes.append(f"Hierarchy category: {hierarchy_category}")
        
        # ══════════════════════════════════════════════════════════
        # ADULT BRAND EXCLUSION
        # ══════════════════════════════════════════════════════════
        adult_brands = ['moleskine', 'leuchtturm', 'rhodia', 'field notes', 'midori']
        def is_adult_brand(title, brand=''):
            text = (str(title) + ' ' + str(brand)).lower()
            return any(ab in text for ab in adult_brands)
        
        stationery = stationery[~stationery.apply(
            lambda r: is_adult_brand(r.get('Title', ''), r.get('Brand', '')), axis=1
        )]
        crosssell_notes.append(f"Stationery after adult brand filter: {len(stationery)}")
        
        # ══════════════════════════════════════════════════════════
        # AGE FILTER FOR TOYS (using bracket system)
        # ══════════════════════════════════════════════════════════
        if 'Προτεινόμενη Ηλικία' in toys.columns:
            toys = toys[
                toys['Προτεινόμενη Ηλικία'].fillna('').astype(str).str.strip().isin(bracket_allowed_ages) |
                (toys['Προτεινόμενη Ηλικία'].fillna('') == '') |
                (toys['Προτεινόμενη Ηλικία'].fillna('').astype(str) == '0')
            ]
            crosssell_notes.append(f"Toys after age bracket filter: {len(toys)}")
        
        # Initialize scores
        toys['Final_Score'] = 0
        stationery['Final_Score'] = 0
        
        # Availability boost
        if 'AVAILABILITY' in toys.columns:
            toys.loc[toys['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
        if 'AVAILABILITY' in stationery.columns:
            stationery.loc[stationery['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
        
        # IP MATCHING: Boost toys that match book series
        if has_series:
            for idx in toys.index:
                toy_brand = str(toys.loc[idx, 'Brand']) if 'Brand' in toys.columns else ''
                toy_heroes = str(toys.loc[idx, 'Ήρωες Παιχνιδιών']) if 'Ήρωες Παιχνιδιών' in toys.columns else ''
                toy_title = str(toys.loc[idx, 'Title']) if 'Title' in toys.columns else ''
                
                if ip_matches(t_series, toy_brand, toy_heroes) or normalize_ip_name(t_series) in normalize_ip_name(toy_title):
                    toys.loc[idx, 'Final_Score'] += SMART_BOOST * 5
            
            ip_matched = toys[toys['Final_Score'] >= SMART_BOOST * 5]
            crosssell_notes.append(f"IP matched toys for '{t_series}': {len(ip_matched)}")
        
        # ═══════════════════════════════════════════════════════════════
        # CROSS-SELL SLOT 1: IP Toy OR Age-Appropriate Fallback (from Word doc)
        # ═══════════════════════════════════════════════════════════════
        if crosssell_count < max_crosssell:
            item1_notes = ["Item 1: IP Toy / Age-Appropriate Fallback"]
            
            # Priority 1: IP-matched toys
            ip_toys = toys[toys['Final_Score'] >= SMART_BOOST * 5].copy()
            if not ip_toys.empty:
                selected = get_rotated_selection(ip_toys, tm, 'ip_toy', n=1)
                if not selected.empty:
                    best = selected.iloc[0]
                    if best['Material'] not in used_materials:
                        row_copy = best.copy()
                        row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                        row_copy['Slot_Role'] = 'Cross-Sell: IP Toy'
                        row_copy['Item_Rank'] = 1
                        all_recs.append(row_copy)
                        used_materials.add(best['Material'])
                        crosssell_count += 1
                        item1_notes.append(f"✓ IP match (rotated): {best['Title'][:40]}...")
            
            # NO IP FALLBACK (from Word doc - age-bracket based)
            if crosssell_count == 0:
                item1_notes.append("No IP match, using age-bracket fallback")
                
                # Define gender-appropriate toy filter
                def toy_matches_gender(title, brand, gender):
                    """Filter toys by gender appropriateness"""
                    text = (str(title) + ' ' + str(brand)).lower()
                    if gender == 'girl':
                        # Exclude boy-specific
                        boy_only = ['spider-man', 'batman', 'avengers', 'marvel', 'dinosaur', 'dino', 
                                   'monster truck', 'transformers', 'ninja', 'nerf', 'army', 'soldier']
                        return not any(b in text for b in boy_only)
                    elif gender == 'boy':
                        # Exclude girl-specific
                        girl_only = ['barbie', 'princess', 'frozen', 'elsa', 'anna', 'fairy', 
                                    'unicorn', 'my little pony', 'hello kitty', 'ballerina']
                        return not any(g in text for g in girl_only)
                    return True
                
                fallback_found = False
                
                # Bracket 1-4: Toddlers (0-3 years) → Plush first
                if age_bracket <= 4:
                    plush = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL['plush'])].copy()
                    plush = plush[plush.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not plush.empty:
                        selected = get_rotated_selection(plush, tm, 'plush', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Plush'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item1_notes.append(f"✓ Toddler plush: {best['Title'][:40]}...")
                                fallback_found = True
                
                # Bracket 5: Preschool (4-7 years) → Action Figures/Dolls based on gender
                elif age_bracket == 5 and not fallback_found:
                    if detected_gender == 'girl':
                        # Try dolls first
                        dolls = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('dolls', []))].copy()
                        dolls = dolls[dolls.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                        if not dolls.empty:
                            selected = get_rotated_selection(dolls, tm, 'dolls', n=1)
                            if not selected.empty:
                                best = selected.iloc[0]
                                if best['Material'] not in used_materials:
                                    row_copy = best.copy()
                                    row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                    row_copy['Slot_Role'] = 'Cross-Sell: Doll'
                                    row_copy['Item_Rank'] = 1
                                    all_recs.append(row_copy)
                                    used_materials.add(best['Material'])
                                    crosssell_count += 1
                                    item1_notes.append(f"✓ Preschool doll: {best['Title'][:40]}...")
                                    fallback_found = True
                    else:
                        # Try action figures for boys/neutral
                        figures = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('action_figures', []))].copy()
                        figures = figures[figures.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                        if not figures.empty:
                            selected = get_rotated_selection(figures, tm, 'figures', n=1)
                            if not selected.empty:
                                best = selected.iloc[0]
                                if best['Material'] not in used_materials:
                                    row_copy = best.copy()
                                    row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                    row_copy['Slot_Role'] = 'Cross-Sell: Action Figure'
                                    row_copy['Item_Rank'] = 1
                                    all_recs.append(row_copy)
                                    used_materials.add(best['Material'])
                                    crosssell_count += 1
                                    item1_notes.append(f"✓ Preschool figure: {best['Title'][:40]}...")
                                    fallback_found = True
                
                # Bracket 6-7: Older kids (8+) → Board games or Collectables
                elif age_bracket >= 6 and not fallback_found:
                    # Try board games
                    games = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('board_puzzles', []))].copy()
                    games = games[games.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not games.empty:
                        selected = get_rotated_selection(games, tm, 'games', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Board Game'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item1_notes.append(f"✓ Older kids game: {best['Title'][:40]}...")
                                fallback_found = True
                
                # Universal fallback: Plush (gender-filtered)
                if not fallback_found:
                    plush = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL['plush'])].copy()
                    plush = plush[plush.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not plush.empty:
                        selected = get_rotated_selection(plush, tm, 'plush_fallback', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Plush'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item1_notes.append(f"✓ Fallback plush: {best['Title'][:40]}...")
            
            crosssell_notes.extend(item1_notes)
        
        # ═══════════════════════════════════════════════════════════════
        # CROSS-SELL SLOT 2: Hierarchy-Based (from Word doc Logic 4)
        # Arts books → Arts supplies, Fiction → Lego, STEM → Educational
        # ═══════════════════════════════════════════════════════════════
        if crosssell_count < max_crosssell:
            item2_notes = ["Item 2: Hierarchy-Based Creative"]
            item2_found = False
            
            # Define gender filter for stationery
            def stationery_matches_gender(title, brand, gender):
                text = (str(title) + ' ' + str(brand)).lower()
                if gender == 'girl':
                    boy_only = ['spider-man', 'batman', 'avengers', 'marvel', 'dinosaur', 'cars', 'minecraft']
                    return not any(b in text for b in boy_only)
                elif gender == 'boy':
                    girl_only = ['barbie', 'princess', 'frozen', 'fairy', 'unicorn', 'hello kitty']
                    return not any(g in text for g in girl_only)
                return True
            
            # Condition A: Arts/Crafts books → Arts supplies
            if hierarchy_category == 'arts' and not item2_found:
                arts_hierarchies = STATIONERY_HIERARCHIES_ACTUAL.get('arts_crafts', [])
                arts = stationery[stationery['Hierarchy'].isin(arts_hierarchies)].copy()
                arts = arts[arts.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not arts.empty:
                    selected = get_rotated_selection(arts, tm, 'arts_direct', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Arts Supplies'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item2_notes.append(f"✓ Arts book → Arts supplies: {best['Title'][:40]}...")
                            item2_found = True
            
            # Condition B: Fiction/Fantasy → Lego/Building Sets
            if hierarchy_category == 'fiction' and not item2_found:
                building = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('building', []))].copy()
                building = building[building.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not building.empty:
                    selected = get_rotated_selection(building, tm, 'building', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Building Set'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item2_notes.append(f"✓ Fiction → Building: {best['Title'][:40]}...")
                            item2_found = True
            
            # Condition C: STEM/Knowledge → Educational toys
            if hierarchy_category == 'stem' and not item2_found:
                educational = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('creative', []))].copy()
                educational = educational[educational.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not educational.empty:
                    selected = get_rotated_selection(educational, tm, 'educational', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Educational'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item2_notes.append(f"✓ STEM → Educational: {best['Title'][:40]}...")
                            item2_found = True
            
            # Condition D: Preschool → Building blocks (ΤΟΥΒΛΑΚΙΑ)
            if hierarchy_category == 'preschool' and not item2_found:
                blocks = toys[toys['Hierarchy'].str.contains('ΤΟΥΒΛΑΚ', case=False, na=False)].copy()
                if not blocks.empty:
                    selected = get_rotated_selection(blocks, tm, 'blocks', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Building Blocks'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item2_notes.append(f"✓ Preschool → Blocks: {best['Title'][:40]}...")
                            item2_found = True
            
            # Universal Fallback: Age-based (from Word doc Condition E)
            if not item2_found:
                if age_bracket <= 6:  # <= 11 years
                    # Try drawing blocks/paper first, then plush
                    paper = stationery[stationery['Hierarchy'].str.contains('ΜΠΛΟΚ|ΧΑΡΤ', case=False, na=False)].copy()
                    paper = paper[paper.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not paper.empty:
                        selected = get_rotated_selection(paper, tm, 'paper', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Drawing Paper'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item2_notes.append(f"✓ Fallback paper: {best['Title'][:40]}...")
                                item2_found = True
                else:  # 12+ years (teens)
                    # Squishmallows or notebooks
                    squish = toys[toys['Title'].str.contains('SQUISHMALLOW|SQUISH', case=False, na=False)].copy()
                    if not squish.empty:
                        selected = get_rotated_selection(squish, tm, 'squish', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Squishmallow'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item2_notes.append(f"✓ Teen Squishmallow: {best['Title'][:40]}...")
                                item2_found = True
            
            crosssell_notes.extend(item2_notes)
        
        # ═══════════════════════════════════════════════════════════════
        # CROSS-SELL SLOT 3: Puzzles/Games OR Reading Accessories (from Word doc Logic 5)
        # ═══════════════════════════════════════════════════════════════
        if crosssell_count < max_crosssell:
            item3_notes = ["Item 3: Puzzle/Games or Reading"]
            item3_found = False
            
            # Condition A: Activity books → Puzzles
            if hierarchy_category == 'activity' and not item3_found:
                puzzles = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('board_puzzles', []))].copy()
                puzzles = puzzles[puzzles.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not puzzles.empty:
                    selected = get_rotated_selection(puzzles, tm, 'puzzles_activity', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Puzzle'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item3_notes.append(f"✓ Activity → Puzzle: {best['Title'][:40]}...")
                            item3_found = True
            
            # Condition B: STEM books → Knowledge games (ΓΝΩΣΕΩΝ)
            if hierarchy_category == 'stem' and not item3_found:
                knowledge = toys[toys['Hierarchy'].str.contains('ΓΝΩΣ', case=False, na=False)].copy()
                if not knowledge.empty:
                    selected = get_rotated_selection(knowledge, tm, 'knowledge', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Knowledge Game'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item3_notes.append(f"✓ STEM → Knowledge: {best['Title'][:40]}...")
                            item3_found = True
            
            # Condition C: Toddlers (≤3 years) → Baby activity toys
            if age_bracket <= 4 and not item3_found:
                baby_toys = toys[toys['Hierarchy'].str.contains('ΒΡΕΦΙΚ|ΔΡΑΣΤΗΡΙΟΤ', case=False, na=False)].copy()
                if not baby_toys.empty:
                    selected = get_rotated_selection(baby_toys, tm, 'baby_activity', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Baby Activity'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item3_notes.append(f"✓ Toddler → Baby toy: {best['Title'][:40]}...")
                            item3_found = True
            
            # Condition D: Fiction/Literature → Reading accessories (bookmarks, lights)
            if hierarchy_category == 'fiction' and not item3_found:
                reading = stationery[stationery['Hierarchy'].str.contains('READING|ΣΕΛΙΔΟΔΕΙΚΤ', case=False, na=False)].copy()
                reading = reading[reading.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not reading.empty:
                    selected = get_rotated_selection(reading, tm, 'reading', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Reading Accessory'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item3_notes.append(f"✓ Fiction → Reading: {best['Title'][:40]}...")
                            item3_found = True
            
            # Universal fallback: Board game/puzzle (gender-filtered)
            if not item3_found:
                puzzles = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL.get('board_puzzles', []))].copy()
                puzzles = puzzles[puzzles.apply(lambda r: toy_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not puzzles.empty:
                    selected = get_rotated_selection(puzzles, tm, 'puzzles_fallback', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Puzzle'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item3_notes.append(f"✓ Fallback puzzle: {best['Title'][:40]}...")
            
            crosssell_notes.extend(item3_notes)
        
        # ═══════════════════════════════════════════════════════════════
        # CROSS-SELL SLOT 4: Lifestyle (from Word doc Logic 6)
        # Age-based: <12 → Water bottles, ≥12 → Notebooks
        # ═══════════════════════════════════════════════════════════════
        if crosssell_count < max_crosssell:
            item4_notes = ["Item 4: Lifestyle (Age-Based)"]
            item4_found = False
            
            # Condition A: STEM → Interactive/3D puzzles
            if hierarchy_category == 'stem' and not item4_found:
                interactive = toys[toys['Hierarchy'].str.contains('ΔΙΑΔΡΑΣΤΙΚ|3D PUZZLE', case=False, na=False)].copy()
                if not interactive.empty:
                    selected = get_rotated_selection(interactive, tm, 'interactive', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Interactive'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item4_notes.append(f"✓ STEM → Interactive: {best['Title'][:40]}...")
                            item4_found = True
            
            # Condition B: Preschool → Wooden toys
            if hierarchy_category == 'preschool' and not item4_found:
                wooden = toys[toys['Hierarchy'].str.contains('ΞΥΛΙΝ', case=False, na=False)].copy()
                if not wooden.empty:
                    selected = get_rotated_selection(wooden, tm, 'wooden', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Wooden Toy'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item4_notes.append(f"✓ Preschool → Wooden: {best['Title'][:40]}...")
                            item4_found = True
            
            # Age-based lifestyle fallback (from Word doc)
            if not item4_found:
                if age_bracket <= 6:  # ≤11 years → Water bottles/Food containers
                    lifestyle = stationery[stationery['Hierarchy'].str.contains('ΠΑΓΟΥΡ|ΦΑΓΗΤΟΔΟΧ', case=False, na=False)].copy()
                    lifestyle = lifestyle[lifestyle.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not lifestyle.empty:
                        selected = get_rotated_selection(lifestyle, tm, 'waterbottle', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Water Bottle'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item4_notes.append(f"✓ Kids → Water bottle: {best['Title'][:40]}...")
                                item4_found = True
                else:  # ≥12 years → Notebooks first, then water bottles
                    notebooks = stationery[stationery['Hierarchy'].str.contains('ΣΗΜΕΙΩΜΑΤ', case=False, na=False)].copy()
                    notebooks = notebooks[notebooks.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                    if not notebooks.empty:
                        selected = get_rotated_selection(notebooks, tm, 'notebook', n=1)
                        if not selected.empty:
                            best = selected.iloc[0]
                            if best['Material'] not in used_materials:
                                row_copy = best.copy()
                                row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                                row_copy['Slot_Role'] = 'Cross-Sell: Notebook'
                                row_copy['Item_Rank'] = 1
                                all_recs.append(row_copy)
                                used_materials.add(best['Material'])
                                crosssell_count += 1
                                item4_notes.append(f"✓ Teen → Notebook: {best['Title'][:40]}...")
                                item4_found = True
            
            # Final fallback: Water bottles (universal)
            if not item4_found:
                lifestyle = stationery[stationery['Hierarchy'].str.contains('ΠΑΓΟΥΡ', case=False, na=False)].copy()
                lifestyle = lifestyle[lifestyle.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not lifestyle.empty:
                    selected = get_rotated_selection(lifestyle, tm, 'waterbottle_fallback', n=1)
                    if not selected.empty:
                        best = selected.iloc[0]
                        if best['Material'] not in used_materials:
                            row_copy = best.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Water Bottle'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(best['Material'])
                            crosssell_count += 1
                            item4_notes.append(f"✓ Fallback water bottle: {best['Title'][:40]}...")
            
            crosssell_notes.extend(item4_notes)
    
    slot_notes[2] = crosssell_notes
    diag.append(("2. Cross-Sell", crosssell_count, f"Filled {crosssell_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 3: CATEGORY DISCOVERY (Fill remaining slots to 10)
    # Both modes fill to 10 total items
    # ══════════════════════════════════════════════════════════
    discovery_notes = ["=== PRIORITY 3: CATEGORY DISCOVERY ==="]
    total_filled = series_count + crosssell_count
    remaining = 10 - total_filled
    discovery_count = 0
    
    discovery_notes.append(f"Filled so far: {total_filled} (series: {series_count}, cross-sell: {crosssell_count}), remaining: {remaining}")
    
    # 🟢 SKIP DISCOVERY FOR COMPLETE BOX SETS - only cross-sell matters
    if trigger_is_complete_box:
        discovery_notes.append("⚠ Complete box set - skipping discovery, cross-sell only")
    elif remaining > 0:
        books_only = df_all[df_all['Level 1'] == 'Books'].copy()
        
        # 🟢 PRIORITY A: For HP Mode B - Show spinoffs first ("Explore more from the series")
        if mode == 'B' and has_series and is_harry_potter_series(t_series):
            # Find HP spinoffs (books with order > 7)
            series_col = 'Σειρά βιβλίου'
            if series_col in books_only.columns:
                hp_all = books_only[
                    books_only[series_col].fillna('').astype(str).str.strip() == t_series
                ].copy()
                
                # Language filter (HARD) - must match
                if t_level2:
                    hp_all = hp_all[hp_all['Level 2'] == t_level2]
                
                # Calculate HP order
                hp_all['_hp_order'] = hp_all['Title'].apply(get_hp_order)
                
                # Get spinoffs (order > 7) that weren't already shown
                spinoffs = hp_all[hp_all['_hp_order'] > 7].copy()
                spinoffs = spinoffs[~spinoffs['Material'].isin(used_materials)]
                spinoffs = spinoffs[spinoffs['Material'] != tm]
                
                # Also exclude box sets
                if not trigger_is_box_set:
                    spinoffs = spinoffs[~spinoffs['Title'].apply(is_box_set)]
                
                discovery_notes.append(f"HP spinoffs available: {len(spinoffs)}")
                
                if not spinoffs.empty:
                    # Score by availability
                    spinoffs['Final_Score'] = 0
                    if 'AVAILABILITY' in spinoffs.columns:
                        spinoffs.loc[spinoffs['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
                    
                    spinoffs = spinoffs.sort_values('Final_Score', ascending=False)
                    
                    added_spinoffs = 0
                    for _, row in spinoffs.iterrows():
                        if discovery_count >= remaining:
                            break
                        row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                        if row['Material'] not in used_materials and row_canonical not in used_titles:
                            row_copy = row.copy()
                            row_copy['Assigned_Slot'] = total_filled + discovery_count + 1
                            row_copy['Slot_Role'] = 'Explore Series'  # HP spinoffs
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(row['Material'])
                            used_titles.add(row_canonical)
                            discovery_count += 1
                            added_spinoffs += 1
                    
                    discovery_notes.append(f"✓ Added {added_spinoffs} HP spinoffs")
        
        # 🟢 PRIORITY B: Same series, different format/edition
        # (books from same series but with different cover/dimensions)
        remaining_after_spinoffs = remaining - discovery_count
        discovery_notes.append(f"Remaining after spinoffs: {remaining_after_spinoffs}")
        
        if has_series and remaining_after_spinoffs > 0:
            # Find series column
            series_col = 'Σειρά βιβλίου'
            if series_col not in books_only.columns:
                for col in books_only.columns:
                    if 'σειρά' in col.lower() or 'series' in col.lower():
                        series_col = col
                        break
            
            if series_col in books_only.columns:
                # Get same-series books
                same_series = books_only[
                    books_only[series_col].fillna('').astype(str).str.strip() == t_series
                ].copy()
                
                discovery_notes.append(f"Same series pool: {len(same_series)}")
                
                # Exclude already used materials
                same_series = same_series[~same_series['Material'].isin(used_materials)]
                same_series = same_series[same_series['Material'] != tm]
                
                # Language filter (HARD) - must match
                if t_level2:
                    same_series = same_series[same_series['Level 2'] == t_level2]
                
                # 🟢 SAME BOOK DETECTION: Use canonical name
                same_series['_canonical'] = same_series.apply(
                    lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', '')), axis=1
                )
                same_series = same_series[same_series['_canonical'] != trigger_canonical]
                # Also exclude titles already shown in series slots
                same_series = same_series[~same_series['_canonical'].isin(used_titles)]
                
                # 🟢 EXCLUDE BOX SETS for individual books
                if not trigger_is_box_set:
                    same_series = same_series[~same_series['Title'].apply(is_box_set)]
                
                discovery_notes.append(f"Same series after filters: {len(same_series)}")
                
                # Get books with DIFFERENT dimensions/cover (other formats/editions)
                diff_format = same_series.copy()
                
                # Filter for different dimensions OR different cover
                if 'Διαστάσεις' in diff_format.columns and t_dims and t_dims != 'nan':
                    diff_format = diff_format[
                        diff_format['Διαστάσεις'].fillna('').astype(str).str.strip() != t_dims
                    ]
                
                discovery_notes.append(f"Different format/edition: {len(diff_format)}")
                
                if not diff_format.empty:
                    # Score by availability
                    diff_format['Final_Score'] = 0
                    if 'AVAILABILITY' in diff_format.columns:
                        diff_format.loc[diff_format['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
                    
                    diff_format = diff_format.sort_values('Final_Score', ascending=False)
                    
                    added_here = 0
                    for _, row in diff_format.head(remaining_after_spinoffs).iterrows():
                        row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                        if row['Material'] not in used_materials and row_canonical not in used_titles and discovery_count < remaining:
                            row_copy = row.copy()
                            row_copy['Assigned_Slot'] = total_filled + discovery_count + 1
                            row_copy['Slot_Role'] = 'Series Discovery'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(row['Material'])
                            used_titles.add(row_canonical)
                            discovery_count += 1
                            added_here += 1
                    
                    discovery_notes.append(f"✓ Added {added_here} same-series different format")
        
        # 🟢 PRIORITY C: Same category/hierarchy (fallback when no more from series)
        remaining_after_series = remaining - discovery_count
        discovery_notes.append(f"Remaining after series discovery: {remaining_after_series}")
        
        if remaining_after_series > 0:
            discovery_pool = books_only[books_only['Hierarchy'] == t_hierarchy].copy()
            
            discovery_notes.append(f"Same hierarchy ({t_hierarchy}): {len(discovery_pool)}")
            
            # Exclude trigger and already recommended
            discovery_pool = discovery_pool[~discovery_pool['Material'].isin(used_materials)]
            discovery_pool = discovery_pool[discovery_pool['Material'] != tm]
            
            # Language filter
            if t_level2:
                discovery_pool = discovery_pool[discovery_pool['Level 2'] == t_level2]
            
            # 🟢 SAME BOOK DETECTION: Use canonical name
            discovery_pool['_canonical'] = discovery_pool.apply(
                lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', '')), axis=1
            )
            discovery_pool = discovery_pool[discovery_pool['_canonical'] != trigger_canonical]
            # Also exclude titles already shown in series/discovery slots
            discovery_pool = discovery_pool[~discovery_pool['_canonical'].isin(used_titles)]
            
            # 🟢 EXCLUDE BOX SETS for individual books
            if not trigger_is_box_set:
                discovery_pool = discovery_pool[~discovery_pool['Title'].apply(is_box_set)]
            
            # Age filter
            if 'Ηλικία' in discovery_pool.columns and allowed_ages:
                discovery_pool = discovery_pool[
                    discovery_pool['Ηλικία'].fillna('').astype(str).str.strip().isin(allowed_ages) |
                    (discovery_pool['Ηλικία'].fillna('') == '') |
                    (discovery_pool['Ηλικία'].fillna('').astype(str) == '0')
                ]
            
            discovery_notes.append(f"After filters: {len(discovery_pool)}")
            
            # Score and sort - DETERMINISTIC (no rotation)
            discovery_pool['Final_Score'] = 0
            if 'AVAILABILITY' in discovery_pool.columns:
                discovery_pool.loc[discovery_pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
            
            discovery_pool = discovery_pool.sort_values('Final_Score', ascending=False)
            
            for _, row in discovery_pool.head(remaining_after_series).iterrows():
                row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                if row['Material'] not in used_materials and row_canonical not in used_titles:
                    row_copy = row.copy()
                    row_copy['Assigned_Slot'] = total_filled + discovery_count + 1
                    row_copy['Slot_Role'] = 'Category Discovery'
                    row_copy['Item_Rank'] = 1
                    all_recs.append(row_copy)
                    used_materials.add(row['Material'])
                    used_titles.add(row_canonical)
                    discovery_count += 1
            
            discovery_notes.append(f"✓ Added {discovery_count} total discovery books")
    
    slot_notes[3] = discovery_notes
    diag.append(("3. Discovery", discovery_count, f"Filled {discovery_count} slots"))
    diag.append(("TOTAL", series_count + crosssell_count + discovery_count, f"out of 10"))
    
    # Build final dataframe
    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        recs_df = recs_df.sort_values('Assigned_Slot').reset_index(drop=True)
        return recs_df, diag, slot_notes, recs_df
    else:
        return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# SMARTPHONES ENGINE (Original - keeping full logic)
# ─────────────────────────────────────────────────────────────
def run_engine(trigger, df_products, df_history, df_slots):
    diag, slot_diag, slot_notes = [], [], {}

    tm   = trigger['Material']
    tt   = str(trigger.get('Title',''))
    tb   = str(trigger.get('Κατασκευαστής','')).strip().upper()
    tmod = str(trigger.get('Μοντέλο','')).strip()
    tpr  = str(trigger.get('Θύρα USB','')).strip()
    tport= extract_base_port(tpr)
    tcol = str(trigger.get('Χρώμα','')).strip()
    tex  = str(trigger.get('Extra Χαρακτηριστικά','')).lower()
    tos  = str(trigger.get('Λειτουργικό σύστημα','')).lower()
    thier= str(trigger.get('Hierarchy',''))
    tl1  = str(trigger.get('Level 1',''))
    tprice=parse_euro_price(trigger.get('LIST PRICE',0))
    ccols= get_case_colors(tcol)

    strict_tmod = ""
    if tmod:
        strict_tmod = rf"(?<![a-zA-Z0-9]){re.escape(tmod)}(?![a-zA-Z0-9])(?!\s*(Max|Plus|\+|Ultra|Pro))"

    brand_kws = {
        "SAMSUNG": ["samsung", "galaxy"], "APPLE": ["apple", "iphone", "ipad"],
        "XIAOMI": ["xiaomi", "redmi", "poco"], "OPPO": ["oppo"],
        "MOTOROLA": ["motorola", "moto"], "HUAWEI": ["huawei"],
        "HONOR": ["honor"], "REALME": ["realme"], "ONEPLUS": ["oneplus"],
        "VIVO": ["vivo"], "NOTHING": ["nothing", "cmf"]
    }
    rival_kws = []
    for k, v in brand_kws.items():
        if k != tb: rival_kws.extend(v)
    rival_regex = r"\b(" + "|".join(rival_kws) + r")\b" if rival_kws else ""

    c = df_products[df_products['Material']!=tm].copy()
    diag.append(("0. Start", len(c), ""))

    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0

    c = c[c['Title']!=tt]; diag.append(("1. Title dedup", len(c), ""))

    if 'CW Stock Units' in c.columns:
        st_col = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        pct = (st_col>0).sum()/len(c) if len(c)>0 else 0
        if pct >= 0.10:
            c['CW Stock Units']=st_col.fillna(0); c=c[c['CW Stock Units']>0]
            diag.append(("2. Stock filter", len(c), f"Applied ({pct:.0%})"))
        else: diag.append(("2. Stock filter", len(c), f"⚠ SKIPPED ({pct:.0%})"))
    else: diag.append(("2. Stock filter", len(c), "⚠ SKIPPED (no col)"))

    mask = (c['Hierarchy']==thier) & (c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb)
    ns = mask.sum()
    if ns > 0:
        sims = c.loc[mask,'Title'].apply(lambda t: title_sim(tt,str(t)))
        dupes = sims[sims>=70].index; c=c.drop(dupes)
        diag.append(("3. Siblings", len(c), f"Checked {ns}, removed {len(dupes)}"))
    else: diag.append(("3. Siblings", len(c), "No siblings"))

    b4=len(c)
    if tl1 in TECH_CATS: c=c[~c['Level 1'].isin(APPL_CATS)]
    elif tl1 in APPL_CATS: c=c[~c['Level 1'].isin(TECH_CATS)]
    diag.append(("4a. Macro wall", len(c), f"Removed {b4-len(c)}"))

    b4eco = len(c)
    if tb == "APPLE":
        c = c[~c['Κατασκευαστής'].fillna('').str.strip().str.upper().isin(ANDROID_OEMS)]
    elif tb in ANDROID_OEMS:
        c = c[c['Κατασκευαστής'].fillna('').str.strip().str.upper() != "APPLE"]
    diag.append(("4b. Ecosystem wall (manufacturer)", len(c), f"Removed {b4eco-len(c)}"))
    
    # 🟢 NEW: Filter out rival brand hierarchies (e.g., "IPHONE SCREEN PROTECTORS" for Samsung)
    b4hier = len(c)
    if tb == "APPLE":
        # For Apple, exclude hierarchies with Android brand names
        android_hier_keywords = ['samsung', 'xiaomi', 'huawei', 'oppo', 'oneplus', 'realme', 'android']
        hier_pattern = '|'.join(android_hier_keywords)
        c = c[~c['Hierarchy'].fillna('').str.lower().str.contains(hier_pattern, regex=True, na=False)]
    elif tb in ANDROID_OEMS:
        # For Android (Samsung, Xiaomi, etc.), exclude hierarchies with "IPHONE" or "APPLE"
        apple_hier_keywords = ['iphone', 'apple', 'ipad', 'macbook', 'airpods']
        hier_pattern = '|'.join(apple_hier_keywords)
        c = c[~c['Hierarchy'].fillna('').str.lower().str.contains(hier_pattern, regex=True, na=False)]
    diag.append(("4c. Ecosystem wall (hierarchy)", len(c), f"Removed {b4hier-len(c)}"))

    # 🟢 NEW: Filter out 3.5mm jack/aux products for modern phones (most don't have jacks)
    # Modern flagships (2020+) typically don't have headphone jacks
    b4jack = len(c)
    jack_keywords = ['3.5mm', '3,5mm', 'aux', 'jack', 'btmusicreceiver', 'music receiver', 'audio receiver']
    jack_pattern = '|'.join(jack_keywords)
    c = c[~c['Title'].fillna('').str.lower().str.contains(jack_pattern, regex=True, na=False)]
    diag.append(("4d. Jack/Aux filter", len(c), f"Removed {b4jack-len(c)}"))

    tcust = df_history[df_history['Material']==tm]['customerEmail'].unique()
    bw = df_history[(df_history['customerEmail'].isin(tcust))&(df_history['Material']!=tm)]
    fdf = bw['Material'].value_counts().reset_index(); fdf.columns=['NID','Frequency']
    c = c.merge(fdf, left_on='Material', right_on='NID', how='left')
    c['Frequency']=c['Frequency'].fillna(0).astype(int)
    c['History_Score']=c['Frequency'].apply(lambda f: HISTORY_BOOST if f>=HISTORY_FREQ_MIN else 0)
    c['Next_Price']=c['LIST PRICE'].apply(parse_euro_price)

    hm=c['History_Score']>0
    if hm.any():
        ok=c.loc[hm].apply(lambda r: price_ok(tprice,r['Next_Price'],tl1), axis=1)
        c.loc[ok[~ok].index,'History_Score']=0

    c['Avail_Boost']=0; c.loc[c['AVAILABILITY']=='Άμεσα Διαθέσιμο','Avail_Boost']=AVAIL_BOOST
    c['Smart_Boost']=0
    
    if strict_tmod:
        c.loc[c['Μοντέλο'].fillna('').astype(str).str.contains(strict_tmod, case=False, regex=True, na=False), 'Smart_Boost'] += SMART_BOOST
    c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Smart_Boost']+=SMART_BOOST
    
    # 🟢 NEW: Premium phone brand preference (€900+)
    # For expensive phones, strongly prefer same-brand accessories
    PREMIUM_PRICE_THRESHOLD = 900
    PREMIUM_BRAND_BOOST = 200000  # Must be higher than HISTORY_BOOST (100000) to ensure brand wins
    if tprice >= PREMIUM_PRICE_THRESHOLD:
        c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb, 'Smart_Boost'] += PREMIUM_BRAND_BOOST
        diag.append(("Premium brand boost", f"€{tprice:.0f} >= €{PREMIUM_PRICE_THRESHOLD}", f"+{PREMIUM_BRAND_BOOST} for {tb} accessories"))
    
    # 🟢 Year extraction functions (used for EARBUDS and SMARTWATCH slots only)
    def extract_year_from_model(model_str):
        """Extract release year from Samsung/Apple model names"""
        model = str(model_str).lower()
        
        # Direct year in title (e.g., "2024", "2025")
        year_match = re.search(r'\b(202[3-9])\b', model)
        if year_match:
            return int(year_match.group(1))
        
        # Samsung Galaxy S series: S25 → 2025, S24 → 2024, S23 → 2023
        s_match = re.search(r'galaxy\s*s\s*(\d{2})', model)
        if s_match:
            num = int(s_match.group(1))
            if 20 <= num <= 30:
                return 2000 + num
        
        # Samsung Galaxy A series: A56 → 2025, A55 → 2024
        a_match = re.search(r'galaxy\s*a\s*(\d{2})', model)
        if a_match:
            num = int(a_match.group(1))
            if num >= 50:
                return 2019 + (num - 50)
        
        # Samsung Galaxy Z Flip/Fold: Flip7 → 2025, Flip6 → 2024
        z_match = re.search(r'(flip|fold)\s*(\d)', model)
        if z_match:
            num = int(z_match.group(2))
            return 2019 + num
        
        # iPhone: iPhone 17 → 2025, iPhone 16 → 2024
        # Formula: 2008 + num (accurate for iPhone 12+)
        iphone_match = re.search(r'iphone\s*(\d{1,2})', model)
        if iphone_match:
            num = int(iphone_match.group(1))
            if num >= 12:
                return 2008 + num  # iPhone 12=2020, 16=2024, 17=2025
            elif num >= 10:
                return 2017  # iPhone X/10/11 were 2017-2019
        
        return None
    
    def extract_year_from_accessory(title_str, model_str=''):
        """Extract year from accessory title/model"""
        text = f"{title_str} {model_str}".lower()
        
        # Direct year in title
        year_match = re.search(r'\b(202[3-9])\b', text)
        if year_match:
            return int(year_match.group(1))
        
        # Samsung Galaxy Buds: Buds4 → 2025, Buds3 → 2024
        buds_match = re.search(r'buds\s*(\d|fe|pro|live)', text)
        if buds_match:
            v = buds_match.group(1)
            if v == '4': return 2025
            if v == '3': return 2024
            if v == '2': return 2022
            if v == 'fe': return 2023
            if v == 'pro': return 2022
            if v == 'live': return 2020
        
        # Samsung Galaxy Watch: Watch 7 → 2024, Watch 6 → 2023
        watch_match = re.search(r'(galaxy\s*)?watch\s*(\d)', text)
        if watch_match:
            num = int(watch_match.group(2))
            return 2018 + num
        
        # Galaxy Fit: Fit 3 → 2024
        fit_match = re.search(r'(galaxy\s*)?fit\s*(\d)', text)
        if fit_match:
            num = int(fit_match.group(2))
            return 2021 + num
        
        return None
    
    # Get phone release year (used later in slot processing)
    phone_year = extract_year_from_model(tmod) or extract_year_from_model(tt)
    is_premium = tprice >= PREMIUM_PRICE_THRESHOLD
    
    c['Final_Score'] = c['History_Score'] + c['Frequency'] + c['Avail_Boost'] + c['Smart_Boost'] + c['Sales_Tiebreaker']

    b4u5=len(c)
    nhm=c['History_Score']==0
    if nhm.any():
        ok2=c.loc[nhm].apply(lambda r: price_ok(tprice,r['Next_Price'],tl1), axis=1)
        c=c.drop(ok2[~ok2].index)
    diag.append(("5. Price ceiling", len(c), f"Removed {b4u5-len(c)}"))

    all_slot = []
    for _, sr in df_slots.iterrows():
        sn = sr['Slot_Number']
        role = str(sr.get('Slot_Role',''))
        lk = detect_logic_key(role)
        ah = [h.strip() for h in str(sr['Allowed_Hierarchies']).split(",")]
        sc = c[c['Hierarchy'].isin(ah)].copy()
        afh = len(sc)
        notes = [f"Logic: {lk}"]

        # 🟢 MODEL-SPECIFIC SLOTS: These accessories must match the exact phone model
        model_specific_slots = ["PRIMARY_CASE", "SCREEN_GLASS", "CAMERA_GLASS", "ALT_CASE"]
        
        if lk in model_specific_slots:
            if strict_tmod:
                b4 = len(sc)
                cv = sc[CC].fillna('').astype(str).str.lower()
                m = sc[cv.str.contains(strict_tmod, case=False, regex=True, na=False)]
                # Also check Title for model match
                if m.empty:
                    m = sc[sc['Title'].fillna('').astype(str).str.lower().str.contains(strict_tmod, case=False, regex=True, na=False)]
                if rival_regex and not m.empty:
                    m = m[~m[CC].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                    m = m[~m['Title'].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                sc = m  
            else:
                sc = sc.head(0)
            
            # Additional filters for PRIMARY_CASE only
            if lk == "PRIMARY_CASE":
                if not sc.empty:
                    b4=len(sc)
                    f=sc[sc['Τύπος Θήκης'].fillna('').astype(str).str.contains("Back Cover", case=False, na=False)]
                    notes.append(f"Back Cover: {b4}→{len(f)}")
                    sc = f  
                if not sc.empty and tcol:
                    b4=len(sc)
                    # 🟢 IMPROVED: Prefer exact phone color, fallback to transparent
                    # Get colors without transparent first
                    exact_colors = [c for c in ccols if c != 'διάφανο' and c != 'transparent']
                    
                    # Try exact color match first
                    sc_exact = sc[sc['Χρώμα'].fillna('').astype(str).str.strip().str.lower().isin(exact_colors)]
                    
                    if not sc_exact.empty:
                        sc = sc_exact
                        notes.append(f"Color (exact): {b4}→{len(sc)}")
                    else:
                        # Fallback to transparent
                        sc_transparent = sc[sc['Χρώμα'].fillna('').astype(str).str.strip().str.lower().isin(['διάφανο', 'transparent', 'clear'])]
                        if not sc_transparent.empty:
                            sc = sc_transparent
                            notes.append(f"Color (transparent fallback): {b4}→{len(sc)}")
                        else:
                            # Keep all if no color match
                            notes.append(f"Color: no match, keeping all {b4}")

        # 🟢 CROSS_SELL BRAND FILTERING: Brand-specific accessories (SmartTag, AirTag)
        # Samsung SmartTag should only show for Samsung phones, AirTag for Apple phones
        if lk == "CROSS_SELL" and not sc.empty:
            b4_brand = len(sc)
            
            # Define brand-specific keywords
            samsung_only_keywords = ['smarttag', 'galaxy smart']
            apple_only_keywords = ['airtag']
            
            # Filter out wrong-brand tracker accessories
            def is_compatible_accessory(row):
                title_lower = str(row.get('Title', '')).lower()
                acc_brand = str(row.get('Κατασκευαστής', '')).upper()
                
                # Samsung-only accessories (SmartTag)
                if any(kw in title_lower for kw in samsung_only_keywords):
                    return tb == "SAMSUNG"  # Only show for Samsung phones
                
                # Apple-only accessories (AirTag)
                if any(kw in title_lower for kw in apple_only_keywords):
                    return tb == "APPLE"  # Only show for Apple phones
                
                # All other accessories are compatible
                return True
            
            sc = sc[sc.apply(is_compatible_accessory, axis=1)]
            
            if len(sc) < b4_brand:
                notes.append(f"Brand filter (trackers): {b4_brand}→{len(sc)}")

        # 🟢 PHONE FEATURES (used for charger and holder matching)
        has_wireless_charging = 'ασύρματη φόρτιση' in tex
        has_fast_charging = 'γρήγορη φόρτιση' in tex
        
        # 🟢 CHARGER/POWERBANK FEATURE MATCHING
        # Match charger capabilities to phone features (wireless charging, fast charging, wattage)
        charger_slots = ["WALL_CHARGER", "POWERBANK"]
        
        if lk in charger_slots and not sc.empty:
            # Calculate feature boost for each charger/powerbank
            WIRELESS_BOOST = 30000  # Prefer wireless chargers for wireless phones
            FAST_CHARGE_BOOST = 20000  # Prefer fast chargers for fast-charge phones
            HIGH_WATT_BOOST = 15000  # Prefer higher wattage for premium phones
            
            if has_wireless_charging or has_fast_charging or is_premium:
                for idx in sc.index:
                    item_title = str(sc.loc[idx, 'Title']).lower()
                    item_watt = str(sc.loc[idx, 'Ισχύς (Watt)']) if 'Ισχύς (Watt)' in sc.columns else ''
                    
                    # Wireless charging boost
                    if has_wireless_charging:
                        if 'wireless' in item_title or 'ασύρματ' in item_title or 'magsafe' in item_title:
                            sc.loc[idx, 'Final_Score'] += WIRELESS_BOOST
                    
                    # Fast charging / high wattage boost
                    if has_fast_charging or is_premium:
                        # Check wattage in title or Ισχύς column
                        watt_match = re.search(r'(\d+)\s*w', item_title)
                        watt_from_col = re.search(r'(\d+)', str(item_watt)) if item_watt else None
                        
                        wattage = 0
                        if watt_match:
                            wattage = int(watt_match.group(1))
                        elif watt_from_col:
                            wattage = int(watt_from_col.group(1))
                        elif '21 - 60' in str(item_watt):
                            wattage = 45  # Assume mid-range
                        
                        # Boost based on wattage (higher = better for premium/fast-charge phones)
                        if wattage >= 45:
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST + HIGH_WATT_BOOST
                        elif wattage >= 25:
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST
                        elif wattage >= 20:
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST // 2
                
                # Re-sort after boosts
                sc = sc.sort_values('Final_Score', ascending=False)
                
                features = []
                if has_wireless_charging: features.append("Wireless")
                if has_fast_charging: features.append("FastCharge")
                if is_premium: features.append("Premium")
                notes.append(f"Phone features: {', '.join(features)}")

        # 🟢 YEAR MATCHING: For premium phones, prefer newest earbuds/smartwatches
        year_match_slots = ["EARBUDS", "SMARTWATCH"]
        ULTRA_PREMIUM_THRESHOLD = 1700  # For phones €1700+, show only premium accessories
        
        # 🟢 PRICE TIER FILTERING: Accessory price should match phone tier
        # Prevents showing €9 earbuds with €2000 phones
        if lk in year_match_slots and not sc.empty:
            # Define minimum accessory prices based on phone price
            if lk == "EARBUDS":
                if tprice >= 1500:
                    min_price = 100
                elif tprice >= 1000:
                    min_price = 60
                elif tprice >= 600:
                    min_price = 30
                elif tprice >= 300:
                    min_price = 15
                else:
                    min_price = 0
            else:  # SMARTWATCH
                if tprice >= 1500:
                    min_price = 200
                elif tprice >= 1000:
                    min_price = 150
                elif tprice >= 600:
                    min_price = 80
                elif tprice >= 300:
                    min_price = 40
                else:
                    min_price = 0
            
            if min_price > 0:
                b4_price = len(sc)
                # Parse prices and filter
                sc['Acc_Price'] = sc['LIST PRICE'].apply(lambda x: parse_euro_price(x))
                price_filtered = sc[sc['Acc_Price'] >= min_price]
                
                if not price_filtered.empty:
                    sc = price_filtered
                    notes.append(f"Price tier (€{tprice:.0f} phone): min €{min_price} → {b4_price}→{len(sc)}")
                else:
                    notes.append(f"Price tier: No items ≥€{min_price}, keeping all {b4_price}")
        
        if lk in year_match_slots and is_premium and not sc.empty:
            
            # 🟢 BRAND PREFERENCE: For premium phones, prefer same-brand accessories
            # Filter to same brand first, fallback to all if none available
            b4_brand = len(sc)
            same_brand = sc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb]
            if not same_brand.empty:
                sc = same_brand
                notes.append(f"Brand filter ({tb}): {b4_brand}→{len(sc)}")
            else:
                notes.append(f"Brand filter: No {tb} accessories, keeping all {b4_brand}")
            
            # 🟢 ULTRA-PREMIUM FILTER: For €1700+ phones, only show Pro/Ultra/flagship accessories
            is_ultra_premium = tprice >= ULTRA_PREMIUM_THRESHOLD
            if is_ultra_premium:
                b4_ultra = len(sc)
                # Premium keywords for earbuds/watches
                premium_keywords = ['pro', 'ultra', 'classic', 'studio', 'max', 'elite']
                premium_pattern = '|'.join(premium_keywords)
                
                # Filter to premium models only
                premium_sc = sc[sc['Title'].fillna('').str.lower().str.contains(premium_pattern, regex=True, na=False)]
                
                if not premium_sc.empty:
                    sc = premium_sc
                    notes.append(f"Ultra-premium filter (€{tprice:.0f}): {b4_ultra}→{len(sc)} (Pro/Ultra only)")
                else:
                    notes.append(f"Ultra-premium filter: No Pro/Ultra found, keeping all {b4_ultra}")
            
            # Calculate accessory year for each item
            if phone_year:
                sc['Accessory_Year'] = sc.apply(
                    lambda r: extract_year_from_accessory(str(r.get('Title', '')), str(r.get('Μοντέλο', ''))), 
                    axis=1
                )
                
                # Year priority: NEWER IS BETTER
                # 0 = newer than phone (e.g., 2026 for 2025 phone) - best, latest tech
                # 1 = same year as phone (e.g., 2025 for 2025 phone)
                # 2 = one year older (e.g., 2024 for 2025 phone)
                # 3 = older (e.g., 2023 or earlier)
                sc['Year_Priority'] = 3  # Default: older
                sc.loc[sc['Accessory_Year'] > phone_year, 'Year_Priority'] = 0  # Newer = best
                sc.loc[sc['Accessory_Year'] == phone_year, 'Year_Priority'] = 1  # Same year
                sc.loc[sc['Accessory_Year'] == phone_year - 1, 'Year_Priority'] = 2  # Previous year
                
                # Sort by: Year_Priority (asc), then Final_Score (desc) for availability/sales tiebreaker
                sc = sc.sort_values(['Year_Priority', 'Final_Score'], ascending=[True, False])
                
                newer_count = (sc['Year_Priority'] == 0).sum()
                same_year_count = (sc['Year_Priority'] == 1).sum()
                prev_year_count = (sc['Year_Priority'] == 2).sum()
                notes.append(f"Year priority ({phone_year}): {newer_count} newer, {same_year_count} same, {prev_year_count} prev")

        # 🟢 HOLDER ROTATION: Show different car holders for different phones
        # Also prefer MagSafe/magnetic holders for phones with wireless charging
        if lk == "HOLDER" and not sc.empty:
            # For phones with wireless charging, boost magnetic/MagSafe holders
            if has_wireless_charging or tb == "APPLE":
                for idx in sc.index:
                    item_title = str(sc.loc[idx, 'Title']).lower()
                    if 'magsafe' in item_title or 'magnetic' in item_title or 'mag' in item_title:
                        sc.loc[idx, 'Final_Score'] += 10000
                notes.append("Boosted MagSafe/magnetic holders for wireless phone")
            
            # Sort by Final_Score first
            sc = sc.sort_values('Final_Score', ascending=False).copy()
            
            # Get top 10 available holders
            top_holders = sc.head(10)
            
            if len(top_holders) > 1:
                # Use phone material as seed for consistent but varied selection
                seed = hash(str(tm) + "_holder") % len(top_holders)
                
                # Rotate the selection
                rotated_indices = [(seed + i) % len(top_holders) for i in range(len(top_holders))]
                sc = top_holders.iloc[rotated_indices].copy()
                
                notes.append(f"Holder rotation: showing #{seed + 1} of {len(top_holders)}")

        afa = len(sc)
        slot_diag.append((sn, role, lk, afh, afa))
        slot_notes[sn] = notes

        if not sc.empty:
            # For year-matched slots and rotated HOLDER, sorting was already done - preserve it
            # For other slots, sort by Final_Score
            skip_resort = (lk in year_match_slots and is_premium and phone_year) or lk == "HOLDER"
            if not skip_resort:
                sc = sc.sort_values('Final_Score', ascending=False).copy()
            else:
                sc = sc.copy()  # Already sorted by Year_Priority/rotation
            sc['Assigned_Slot']=sn; sc['Slot_Role']=role
            sc['Item_Rank']=range(1,len(sc)+1)
            sc['Draft_Score']=sc['Item_Rank']*100+sn
            all_slot.append(sc)

    if not all_slot:
        return pd.DataFrame(), diag, slot_diag, slot_notes, pd.DataFrame()

    full = pd.concat(all_slot, ignore_index=True).sort_values('Draft_Score').reset_index(drop=True)

    sel, hc, seen = [], {}, set()
    for _, r in full.iterrows():
        h, mat = r['Hierarchy'], r['Material']
        if mat in seen: continue
        if hc.get(h,0)>=2: continue
        sel.append(r); hc[h]=hc.get(h,0)+1; seen.add(mat)
        if len(sel)>=10: break

    diag.append(("6. Final", len(sel), "Hierarchy cap=2"))
    return (pd.DataFrame(sel) if sel else pd.DataFrame()), diag, slot_diag, slot_notes, full


# ─────────────────────────────────────────────────────────────
# RUN ENGINE
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    recs, diag, slot_diag, slot_notes, full_candidates = run_engine(trigger, df_products, df_history, df_slots)
else:
    books_mode = st.session_state.get('books_mode', 'A')
    recs, diag, slot_notes, full_candidates = run_books_engine(trigger, df_books, df_history, mode=books_mode)
    slot_diag = []

# Marketing Copy
MARKETING_COPY = {
    "PRIMARY_CASE": "Απόλυτη προστασία & τέλεια εφαρμογή.",
    "SCREEN_GLASS": "Αόρατη ασπίδα για την οθόνη σου.",
    "WALL_CHARGER": "Γρήγορη και απόλυτα ασφαλής φόρτιση.",
    "EARBUDS": "Κορυφαία, ασύρματη ακουστική εμπειρία.",
    "POWERBANK": "Ενέργεια on-the-go.",
    "CROSS_SELL": "Smart gadget για το οικοσύστημά σου.",
    "CAMERA_GLASS": "Θωράκιση φακών για τέλειες λήψεις.",
    "SMARTWATCH": "Ο απόλυτος σύντροφος.",
    "HOLDER": "Σταθερή τοποθέτηση για το αυτοκίνητο.",
    "ALT_CASE": "Premium προστασία.",
    # Books
    "Series Book": "Η συνέχεια της περιπέτειας!",
    "Start from Beginning": "Ξεκίνα από την αρχή!",  # Mode B: Start from beginning
    "Other Box Set": "Ολόκληρη η συλλογή!",  # For partial box sets
    "Series Discovery": "Άλλη έκδοση της σειράς!",
    "Cross-Sell: IP Toy": "Ο ήρωας ζωντανεύει!",
    "Cross-Sell: Plush": "Αγκαλιά με τον αγαπημένο σου!",
    "Cross-Sell: Arts": "Δημιούργησε & φαντάσου!",
    "Cross-Sell: Creative Toy": "Χτίσε τον κόσμο σου!",
    "Cross-Sell: Puzzle": "Μάθε παίζοντας!",
    "Cross-Sell: Lifestyle": "Στιλ για κάθε μέρα!",
    "Cross-Sell: Collectable Cards": "Συλλογή για πρωταθλητές!",
    "Cross-Sell: Action Figure": "Ο ήρωας στο ράφι σου!",
    "Explore Series": "Ανακάλυψε κι άλλα από τη σειρά!",  # HP spinoffs
    "Category Discovery": "Μια ακόμα τέλεια επιλογή!",
}

if not recs.empty:
    rts = recs.head(10)
    ch = ""
    for _, r in rts.iterrows():
        iu=safe(str(r.get('Thumbnails','')).strip())
        if not iu or iu == 'nan': iu = "https://via.placeholder.com/150"
        rp=parse_euro_price(r.get('LIST PRICE',0))
        np=f"{rp:.2f}".replace('.',','); op=f"{(rp*1.25):.2f}".replace('.',',')
        ti=safe(str(r.get('Title',''))); sn=int(r.get('Assigned_Slot',0))
        
        raw_role = str(r.get('Slot_Role',''))
        if active_cluster == "Smartphones":
            lk = detect_logic_key(raw_role)
            marketing_text = MARKETING_COPY.get(lk, "Ιδανική επιλογή!")
        else:
            marketing_text = MARKETING_COPY.get(raw_role, "Μια εξαιρετική επιλογή!")
        
        ch+=f"""<div class="pc">
            <div class="sb">Slot {sn}</div>
            <img src="{iu}" alt="product">
            <div class="ti" title="{ti}">{ti}</div>
            <div class="sr">{marketing_text}</div>
            <div class="rv"><span class="sc">4.8</span> <span class="st">★★★★★</span> <span class="ct">(305)</span></div>
            <div class="op">Π.Λ.Τ. : {op}€</div>
            <div class="np">{np.split(',')[0]}<span class="dm">,{np.split(',')[1]}€</span></div>
            <button class="cb">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <circle cx="9" cy="21" r="1"></circle><circle cx="20" cy="21" r="1"></circle>
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                </svg>
            </button>
        </div>"""

    header_text = "Μαζί με αυτό αγοράζουν" if active_cluster == "Smartphones" else "Συνέχισε την περιπέτεια"

    css="""
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:transparent}
    .desktop-wrapper{background-color:#f8f9fa;border-radius:16px;padding:30px;margin:10px 0;position:relative}
    .desktop-header{font-size:24px;font-weight:700;margin-bottom:25px;color:#111;display:flex;align-items:center}
    .desktop-header span{color:#ff5e00;margin-right:10px;font-size:26px;line-height:1;font-weight:900}
    .car{display:flex;overflow-x:auto;gap:15px;padding-bottom:10px;scrollbar-width:none;scroll-behavior:smooth}
    .car::-webkit-scrollbar{display:none}
    .pc{background:#fff;border:1px solid #eaeaea;border-radius:12px;padding:15px 12px;display:flex;flex-direction:column;align-items:center;box-shadow:0 2px 5px rgba(0,0,0,.04);position:relative;flex-shrink:0;width:180px;min-width:180px;max-width:180px}
    .sb{position:absolute;top:8px;left:8px;background:#ff5e00;color:#fff;font-size:10px;font-weight:700;padding:3px 6px;border-radius:6px;z-index:10}
    .pc img{height:110px;width:auto;object-fit:contain;margin-bottom:15px;margin-top:10px}
    .ti{font-size:13px;color:#333;text-align:center;height:36px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-bottom:6px;line-height:1.3;padding:0 5px;word-wrap:break-word;word-break:break-word;max-width:100%;white-space:normal !important}
    .sr{font-size:10px;color:#777;margin-bottom:12px;text-align:center;height:28px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.35;width:100%;padding:0 4px}
    .rv{font-size:11px;margin-bottom:15px}
    .sc{color:#ff5e00;font-weight:700}
    .st{color:#ff5e00;letter-spacing:-2px}
    .ct{color:#1a73e8}
    .op{font-size:11px;color:#888;text-decoration:line-through;margin-bottom:2px}
    .np{font-size:18px;font-weight:700;color:#ff5e00;margin-bottom:15px}
    .dm{font-size:12px}
    .cb{background:#ff5e00;color:#fff;border:none;border-radius:8px;width:40px;height:35px;cursor:pointer;display:flex;justify-content:center;align-items:center}
    .cb:hover{background:#e65500}
    .nav-btn{position:absolute;top:55%;transform:translateY(-50%);width:44px;height:44px;background-color:#fff;border:1px solid #eaeaea;border-radius:50%;box-shadow:0 4px 10px rgba(0,0,0,0.1);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:100;transition:transform 0.2s,box-shadow 0.2s,opacity 0.3s}
    .nav-btn:hover{transform:translateY(-50%) scale(1.05);box-shadow:0 6px 14px rgba(0,0,0,0.15)}
    .nav-left{left:10px;opacity:0;pointer-events:none}
    .nav-right{right:10px}
    .nav-left::after{content:'';width:10px;height:10px;border-top:2px solid #555;border-left:2px solid #555;transform:rotate(-45deg);margin-left:4px}
    .nav-right::after{content:'';width:10px;height:10px;border-top:2px solid #555;border-right:2px solid #555;transform:rotate(45deg);margin-right:4px}
    """

    dp=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head>
    <body>
    <div class="desktop-wrapper">
        <div class="desktop-header"><span>|</span>{header_text}</div>
        <div class="nav-btn nav-left" id="btnLeft" onclick="scrollL()"></div>
        <div class="car" id="scrollContainer">{ch}</div>
        <div class="nav-btn nav-right" id="btnRight" onclick="scrollR()"></div>
    </div>
    <script>
        const container=document.getElementById('scrollContainer');
        const btnLeft=document.getElementById('btnLeft');
        const btnRight=document.getElementById('btnRight');
        function scrollL(){{container.scrollBy({{left:-405,behavior:'smooth'}});}}
        function scrollR(){{container.scrollBy({{left:405,behavior:'smooth'}});}}
        container.addEventListener('scroll',()=>{{
            btnLeft.style.opacity=container.scrollLeft>5?'1':'0';
            btnLeft.style.pointerEvents=container.scrollLeft>5?'auto':'none';
            btnRight.style.opacity=container.scrollLeft+container.clientWidth>=container.scrollWidth-2?'0':'1';
            btnRight.style.pointerEvents=container.scrollLeft+container.clientWidth>=container.scrollWidth-2?'none':'auto';
        }});
        container.dispatchEvent(new Event('scroll'));
    </script>
    </body></html>"""

    components.html(dp, height=540, scrolling=False)
else:
    st.error("❌ No recommendations found.")


# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
st.markdown("---")

st.markdown("""
<style>
[data-testid="stExpander"]{background-color:#ffffff !important;border:1px solid #d9d9d9 !important;border-radius:12px !important;box-shadow:none !important;margin-top:20px}
[data-testid="stExpander"] summary{padding:24px 30px !important;display:flex !important;align-items:center !important}
[data-testid="stExpander"] summary p{font-size:18px !important;font-weight:700 !important;color:#000 !important;flex-grow:1}
[data-testid="stExpander"] summary svg{display:none !important}
[data-testid="stExpander"] summary::after{content:'';display:inline-block;width:12px;height:12px;border-right:2px solid #111;border-bottom:2px solid #111;transform:rotate(45deg);margin-top:-4px}
[data-testid="stExpander"][open] summary::after{transform:rotate(225deg);margin-top:6px}
[data-testid="stExpanderDetails"]{padding:10px 30px 30px 30px !important}
</style>
""", unsafe_allow_html=True)

with st.expander("⚙️ System Diagnostics"):
    st.markdown(f"### Active Cluster: **{active_cluster}**")
    
    if active_cluster == "Kids Books":
        t_series = str(trigger.get('Σειρά βιβλίου', '')).strip()
        t_age = str(trigger.get('Ηλικία', '')).strip()
        t_hierarchy = str(trigger.get('Hierarchy', '')).strip()
        st.markdown(f"**Series:** `{t_series}` (Valid: {is_valid_series(t_series)}) | **Age:** `{t_age}` | **Hierarchy:** `{t_hierarchy}`")

    st.markdown("### Engine Funnel")
    st.dataframe(pd.DataFrame(diag, columns=["Step","Count","Note"]), use_container_width=True, hide_index=True)

    st.markdown("### Slot Details")
    for sn, notes in sorted(slot_notes.items()):
        if notes:
            st.markdown(f"**Priority {sn}**")
            for n in notes: 
                st.text(n)

    st.markdown("### Trigger Attributes")
    if active_cluster == "Kids Books":
        cols = ['Material','Title','Level 2','Hierarchy','Σειρά βιβλίου','Ηλικία','Εξώφυλλο','Brand','LIST PRICE']
    else:
        cols = ['Material','Title','Level 2','Hierarchy','Κατασκευαστής','Μοντέλο','LIST PRICE']
    for col in cols:
        val = trigger.get(col, 'N/A')
        st.text(f"{col}: {val}")

    if not recs.empty:
        st.markdown("### Final Recommendations")
        dc = ['Title','Hierarchy','Assigned_Slot','Slot_Role','Final_Score'] if 'Final_Score' in recs.columns else ['Title','Hierarchy','Assigned_Slot','Slot_Role']
        st.dataframe(recs[[c for c in dc if c in recs.columns]], use_container_width=True, hide_index=True)
