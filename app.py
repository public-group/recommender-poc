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
        top: 120px !important;
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
        🟢 Engine v11.3 — Fixed Arts Cross-Sell & Title Wrap
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
ANDROID_OEMS = {"SAMSUNG", "XIAOMI", "HUAWEI", "MOTOROLA", "HONOR", "POCO", "REALME", "ONEPLUS", "NOTHING"}

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
    "plush": ["ΛΟΥΤΡΙΝΑ"],
    "dolls": ["ΚΟΥΚΛΕΣ"],
    "action_figures": ["ACTION FIGURES", "ΣΥΛΛΕΚΤΙΚΕΣ ΦΙΓΟΥΡΕΣ"],
    "board_puzzles": ["ΟΙΚΟΓΕΝΕΙΑΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΠΑΙΔΙΚΑ PUZZLES", "CARD GAMES", "ΠΑΙΔΙΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΕΝΗΛΙΚΩΝ 1000+"],
    "building": ["ΚΑΤΑΣΚΕΥΕΣ", "ΜΙΚΡΟΚΟΣΜΟΣ"],
    "toddler": ["ΒΡΕΦΙΚΑ ΠΑΙΧΝΙΔΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ", "ΦΙΓΟΥΡΕΣ & PLAYSET"],
    "vehicles": ["ΔΙΑΦΟΡΑ ΑΥΤΟΚΙΝΗΤΑ"],
    "creative": ["ΖΩΓΡΑΦΙΚΗ"],
}

# 🟢 ACTUAL STATIONERY HIERARCHIES FROM YOUR DATA
STATIONERY_HIERARCHIES_ACTUAL = {
    "notebooks": ["ΣΗΜΕΙΩΜΑΤΑΡΙΑ", "ΤΕΤΡΑΔΙΑ"],
    "water_bottles": ["ΘΕΡΜΟΣ - ΠΑΓΟΥΡΙΑ", "ΠΑΓΟΥΡΙΑ"],
    "arts_crafts": ["ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ", "ΜΠΛΟΚ-ΧΑΡΤΙΑ", "ΚΑΣΕΤΙΝΕΣ"],  # Removed markers - not ideal for kids books
    "markers_only": ["ΜΑΡΚΑΔΟΡΟΙ", "ΜΑΡΚΑΔΟΡΟΙ ΣΧΕΔΙΟΥ-ΕΙΔΙΚΩΝ ΧΡΗΣΕΩΝ"],  # Separate category if needed
    "reading": ["READING ACCESSORIES"],
    "writing": ["ΜΟΛΥΒΙΑ", "ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ", "ΣΤΥΛΟ GEL"],
    "keychains": ["ΜΠΡΕΛΟΚ", "ΜΑΓΝΗΤΑΚΙΑ"],
    "cups": ["ΚΟΥΠΕΣ &  ΠΟΤΗΡΙΑ"],
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
    'black titanium': ['μαύρο', 'black', 'διάφανο'],
    'natural titanium': ['διάφανο', 'μπεζ', 'natural'],
    'white titanium': ['λευκό', 'white', 'διάφανο'],
    'blue titanium': ['μπλε', 'blue', 'διάφανο'],
    'space black': ['μαύρο', 'black', 'διάφανο'],
    'silver': ['ασημί', 'silver', 'διάφανο'],
    'gold': ['χρυσό', 'gold', 'διάφανο'],
    'starlight': ['λευκό', 'μπεζ', 'διάφανο'],
    'midnight': ['μαύρο', 'black', 'διάφανο'],
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
# 🟢 KIDS BOOKS ENGINE (FIXED)
# ─────────────────────────────────────────────────────────────
def run_books_engine(trigger, df_all, df_history):
    """
    Kids Books Recommendation Engine with FIXED Series Logic
    """
    diag = []
    slot_notes = {}
    all_recs = []
    used_materials = set()
    
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
    
    diag.append(("0. Trigger", "", f"Series: '{t_series}' (valid: {has_series}), Age: '{effective_age}'"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 1: SERIES ENGINE (Slots 1-3, or more if available)
    # ══════════════════════════════════════════════════════════
    series_notes = ["=== PRIORITY 1: SERIES ENGINE ==="]
    series_count = 0
    
    if has_series:
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
        
        # Exclude same original title (different editions of same book)
        if t_orig_title and t_orig_title != 'nan' and t_orig_title != '0':
            before = len(series_books)
            series_books = series_books[
                series_books['Τίτλος πρωτοτύπου'].fillna('').astype(str).str.strip() != t_orig_title
            ]
            series_notes.append(f"Excluded same original title: {before}→{len(series_books)}")
        
        # Language filter (Greek with Greek, English with English)
        if t_level2:
            before = len(series_books)
            series_books = series_books[series_books['Level 2'] == t_level2]
            series_notes.append(f"Level 2 match ({t_level2}): {before}→{len(series_books)}")
        
        # FORMAT LOCK: Match cover type
        if t_cover and t_cover != 'nan' and t_cover != '0' and not series_books.empty:
            before = len(series_books)
            cover_match = series_books[series_books['Εξώφυλλο'].fillna('').astype(str).str.strip() == t_cover]
            if not cover_match.empty:
                series_books = cover_match
                series_notes.append(f"Cover match ({t_cover}): {before}→{len(series_books)}")
        
        # FORMAT LOCK: Match dimensions (same print run)
        if t_dims and t_dims != 'nan' and t_dims != 'NaN' and not series_books.empty:
            before = len(series_books)
            dims_match = series_books[series_books['Διαστάσεις'].fillna('').astype(str).str.strip() == t_dims]
            if not dims_match.empty:
                series_books = dims_match
                series_notes.append(f"Dimensions match: {before}→{len(series_books)}")
        
        # Score series books
        if not series_books.empty:
            series_books['Final_Score'] = SERIES_BOOST
            if 'AVAILABILITY' in series_books.columns:
                series_books.loc[series_books['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
            
            # Sort by availability first, then by any other criteria
            series_books = series_books.sort_values('Final_Score', ascending=False)
            
            # Take up to 7 series books (leaving 3 slots for cross-sell)
            max_series = min(7, len(series_books))
            for idx, (_, row) in enumerate(series_books.head(max_series).iterrows()):
                if row['Material'] not in used_materials:
                    row_copy = row.copy()
                    row_copy['Assigned_Slot'] = series_count + 1
                    row_copy['Slot_Role'] = f'Series Book'
                    row_copy['Item_Rank'] = 1
                    all_recs.append(row_copy)
                    used_materials.add(row['Material'])
                    series_count += 1
            
            series_notes.append(f"✓ Added {series_count} series books to slots 1-{series_count}")
    else:
        series_notes.append("No valid series found on trigger - skipping series engine")
    
    slot_notes[1] = series_notes
    diag.append(("1. Series Engine", series_count, f"Filled {series_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 2: CROSS-SELL (Toys & Stationery)
    # ══════════════════════════════════════════════════════════
    crosssell_notes = ["=== PRIORITY 2: CROSS-SELL ==="]
    crosssell_count = 0
    max_crosssell = min(4, 10 - series_count)  # Fill remaining slots up to 4
    
    if max_crosssell > 0:
        # Get Toys and Stationery
        toys = df_all[df_all['Level 1'] == 'Toys'].copy()
        stationery = df_all[df_all['Level 1'] == 'Stationery'].copy()
        
        crosssell_notes.append(f"Toys pool: {len(toys)}, Stationery pool: {len(stationery)}")
        
        # Age filter for toys
        if 'Προτεινόμενη Ηλικία' in toys.columns and effective_age:
            toys = toys[
                toys['Προτεινόμενη Ηλικία'].fillna('').astype(str).str.strip().isin(allowed_ages) |
                (toys['Προτεινόμενη Ηλικία'].fillna('') == '') |
                (toys['Προτεινόμενη Ηλικία'].fillna('').astype(str) == '0')
            ]
            crosssell_notes.append(f"Toys after age filter: {len(toys)}")
        
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
        
        # ─── CROSS-SELL SLOT 1: IP-matched Toy or Plush ───
        if crosssell_count < max_crosssell:
            item1_notes = ["Item 1: IP Toy / Plush"]
            
            # Priority 1: IP-matched toys
            ip_toys = toys[toys['Final_Score'] >= SMART_BOOST * 5].copy()
            if not ip_toys.empty:
                ip_toys = ip_toys.sort_values('Final_Score', ascending=False)
                best = ip_toys.iloc[0]
                if best['Material'] not in used_materials:
                    row_copy = best.copy()
                    row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                    row_copy['Slot_Role'] = 'Cross-Sell: IP Toy'
                    row_copy['Item_Rank'] = 1
                    all_recs.append(row_copy)
                    used_materials.add(best['Material'])
                    crosssell_count += 1
                    item1_notes.append(f"✓ IP match: {best['Title'][:40]}...")
            
            # Fallback: Plush
            if crosssell_count == 0:
                plush = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL['plush'])]
                if not plush.empty:
                    plush = plush.sort_values('Final_Score', ascending=False)
                    best = plush.iloc[0]
                    if best['Material'] not in used_materials:
                        row_copy = best.copy()
                        row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                        row_copy['Slot_Role'] = 'Cross-Sell: Plush'
                        row_copy['Item_Rank'] = 1
                        all_recs.append(row_copy)
                        used_materials.add(best['Material'])
                        crosssell_count += 1
                        item1_notes.append(f"✓ Plush fallback: {best['Title'][:40]}...")
            
            crosssell_notes.extend(item1_notes)
        
        # ─── CROSS-SELL SLOT 2: Creative / Arts ───
        if crosssell_count < max_crosssell:
            item2_notes = ["Item 2: Creative / Arts"]
            
            # Stationery arts supplies
            arts = stationery[stationery['Hierarchy'].isin(STATIONERY_HIERARCHIES_ACTUAL['arts_crafts'])]
            if not arts.empty:
                arts = arts.sort_values('Final_Score', ascending=False)
                for _, row in arts.iterrows():
                    if row['Material'] not in used_materials:
                        row_copy = row.copy()
                        row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                        row_copy['Slot_Role'] = 'Cross-Sell: Arts'
                        row_copy['Item_Rank'] = 1
                        all_recs.append(row_copy)
                        used_materials.add(row['Material'])
                        crosssell_count += 1
                        item2_notes.append(f"✓ Arts: {row['Title'][:40]}...")
                        break
            
            # Fallback: Creative toys
            if len([n for n in item2_notes if '✓' in n]) == 0:
                creative = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL['creative'] + TOY_HIERARCHIES_ACTUAL['building'])]
                if not creative.empty:
                    creative = creative.sort_values('Final_Score', ascending=False)
                    for _, row in creative.iterrows():
                        if row['Material'] not in used_materials:
                            row_copy = row.copy()
                            row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                            row_copy['Slot_Role'] = 'Cross-Sell: Creative Toy'
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(row['Material'])
                            crosssell_count += 1
                            item2_notes.append(f"✓ Creative toy: {row['Title'][:40]}...")
                            break
            
            crosssell_notes.extend(item2_notes)
        
        # ─── CROSS-SELL SLOT 3: Puzzle / Board Game ───
        if crosssell_count < max_crosssell:
            item3_notes = ["Item 3: Puzzle / Board Game"]
            
            puzzles = toys[toys['Hierarchy'].isin(TOY_HIERARCHIES_ACTUAL['board_puzzles'])]
            if not puzzles.empty:
                puzzles = puzzles.sort_values('Final_Score', ascending=False)
                for _, row in puzzles.iterrows():
                    if row['Material'] not in used_materials:
                        row_copy = row.copy()
                        row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                        row_copy['Slot_Role'] = 'Cross-Sell: Puzzle'
                        row_copy['Item_Rank'] = 1
                        all_recs.append(row_copy)
                        used_materials.add(row['Material'])
                        crosssell_count += 1
                        item3_notes.append(f"✓ Puzzle: {row['Title'][:40]}...")
                        break
            
            crosssell_notes.extend(item3_notes)
        
        # ─── CROSS-SELL SLOT 4: Lifestyle (Water bottle / Notebook) ───
        if crosssell_count < max_crosssell:
            item4_notes = ["Item 4: Lifestyle"]
            
            lifestyle = stationery[stationery['Hierarchy'].isin(
                STATIONERY_HIERARCHIES_ACTUAL['water_bottles'] + 
                STATIONERY_HIERARCHIES_ACTUAL['notebooks']
            )]
            if not lifestyle.empty:
                lifestyle = lifestyle.sort_values('Final_Score', ascending=False)
                for _, row in lifestyle.iterrows():
                    if row['Material'] not in used_materials:
                        row_copy = row.copy()
                        row_copy['Assigned_Slot'] = series_count + crosssell_count + 1
                        row_copy['Slot_Role'] = 'Cross-Sell: Lifestyle'
                        row_copy['Item_Rank'] = 1
                        all_recs.append(row_copy)
                        used_materials.add(row['Material'])
                        crosssell_count += 1
                        item4_notes.append(f"✓ Lifestyle: {row['Title'][:40]}...")
                        break
            
            crosssell_notes.extend(item4_notes)
    
    slot_notes[2] = crosssell_notes
    diag.append(("2. Cross-Sell", crosssell_count, f"Filled {crosssell_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 3: CATEGORY DISCOVERY (Fill remaining slots)
    # ══════════════════════════════════════════════════════════
    discovery_notes = ["=== PRIORITY 3: CATEGORY DISCOVERY ==="]
    total_filled = series_count + crosssell_count
    remaining = 10 - total_filled
    discovery_count = 0
    
    if remaining > 0:
        # Get books from same hierarchy
        books_only = df_all[df_all['Level 1'] == 'Books'].copy()
        discovery_pool = books_only[books_only['Hierarchy'] == t_hierarchy].copy()
        
        discovery_notes.append(f"Same hierarchy ({t_hierarchy}): {len(discovery_pool)}")
        
        # Exclude trigger and already recommended
        discovery_pool = discovery_pool[~discovery_pool['Material'].isin(used_materials)]
        discovery_pool = discovery_pool[discovery_pool['Material'] != tm]
        
        # Language filter
        if t_level2:
            discovery_pool = discovery_pool[discovery_pool['Level 2'] == t_level2]
        
        # Age filter
        if 'Ηλικία' in discovery_pool.columns and allowed_ages:
            discovery_pool = discovery_pool[
                discovery_pool['Ηλικία'].fillna('').astype(str).str.strip().isin(allowed_ages) |
                (discovery_pool['Ηλικία'].fillna('') == '') |
                (discovery_pool['Ηλικία'].fillna('').astype(str) == '0')
            ]
        
        discovery_notes.append(f"After filters: {len(discovery_pool)}")
        
        # Score and sort
        discovery_pool['Final_Score'] = 0
        if 'AVAILABILITY' in discovery_pool.columns:
            discovery_pool.loc[discovery_pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
        
        discovery_pool = discovery_pool.sort_values('Final_Score', ascending=False)
        
        for _, row in discovery_pool.head(remaining).iterrows():
            if row['Material'] not in used_materials:
                row_copy = row.copy()
                row_copy['Assigned_Slot'] = total_filled + discovery_count + 1
                row_copy['Slot_Role'] = 'Category Discovery'
                row_copy['Item_Rank'] = 1
                all_recs.append(row_copy)
                used_materials.add(row['Material'])
                discovery_count += 1
        
        discovery_notes.append(f"✓ Added {discovery_count} discovery books")
    
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
    diag.append(("4b. Ecosystem wall", len(c), f"Removed {b4eco-len(c)}"))

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

        if lk == "PRIMARY_CASE":
            if strict_tmod:
                b4 = len(sc)
                cv = sc[CC].fillna('').astype(str).str.lower()
                m = sc[cv.str.contains(strict_tmod, case=False, regex=True, na=False)]
                if rival_regex and not m.empty:
                    m = m[~m[CC].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                    m = m[~m['Title'].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                sc = m  
            else:
                sc = sc.head(0) 
            if not sc.empty:
                b4=len(sc)
                f=sc[sc['Τύπος Θήκης'].fillna('').astype(str).str.contains("Back Cover", case=False, na=False)]
                notes.append(f"Back Cover: {b4}→{len(f)}")
                sc = f  
            if not sc.empty and tcol:
                b4=len(sc)
                sc_color=sc[sc['Χρώμα'].fillna('').astype(str).str.strip().str.lower().isin(ccols)]
                notes.append(f"Color: {b4}→{len(sc_color)}")
                if not sc_color.empty: sc = sc_color

        afa = len(sc)
        slot_diag.append((sn, role, lk, afh, afa))
        slot_notes[sn] = notes

        if not sc.empty:
            sc = sc.sort_values('Final_Score', ascending=False).copy()
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
    recs, diag, slot_notes, full_candidates = run_books_engine(trigger, df_books, df_history)
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
    "Cross-Sell: IP Toy": "Ο ήρωας ζωντανεύει!",
    "Cross-Sell: Plush": "Αγκαλιά με τον αγαπημένο σου!",
    "Cross-Sell: Arts": "Δημιούργησε & φαντάσου!",
    "Cross-Sell: Creative Toy": "Χτίσε τον κόσμο σου!",
    "Cross-Sell: Puzzle": "Μάθε παίζοντας!",
    "Cross-Sell: Lifestyle": "Στιλ για κάθε μέρα!",
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
    .ti{font-size:13px;color:#333;text-align:center;height:36px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-bottom:6px;line-height:1.3;padding:0 5px;word-wrap:break-word;word-break:break-word;max-width:100%}
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
