import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
import re
from difflib import SequenceMatcher


st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# ─────────────────────────────────────────────────────────────
# CUSTOM TOP HEADER & GLOBAL STYLING
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* 1. Force the entire app and sidebar to be clean white, killing the grey */
    .stApp, .main, [data-testid="stSidebar"] {
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid #eaeaea !important;
        padding-top: 110px !important; /* Pushed further down to clear the yellow banner */
    }

/* 2. FIX THE SIDEBAR TOGGLE & TOP RIGHT ICONS */
    header[data-testid="stHeader"] { 
        background: transparent !important;
        box-shadow: none !important;
        z-index: 1000001 !important; 
        top: 24px !important; /* Pushes the toolbar down into the bright orange bar */
    }
    
    /* Target the text (like "Share") */
    header[data-testid="stHeader"] span {
        color: #ffffff !important;
    }
    
    /* Target the icons (Paths, Circles, etc) */
    header[data-testid="stHeader"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }
    
    /* 🟢 FIX: Prevent the 3-dots transparent bounding box from turning into a solid white square */
    header[data-testid="stHeader"] svg rect {
        fill: transparent !important;
    }

/* 3. Push the main content down so it doesn't hide under our new header */
    .appview-container .main .block-container { 
        padding-top: 300px !important; /* 🟢 FIX: Increased from 130px to 170px */
    }
    
    /* 4. The Fixed Header Wrapper - WIDTH BUG FIXED */
    .poc-header-wrapper {
        position: fixed;
        top: 0;
        left: 0;
        right: 0; /* FIX: Using right:0 instead of width:100% prevents the horizontal scrollbar gap */
        z-index: 999999;
        display: flex;
        flex-direction: column;
    }
    
    /* The Thin Dark Orange Bar */
    .poc-top-bar {
        background-color: #BF3C00;
        height: 24px;
        width: 100%;
    }
    
    /* The Thick Bright Orange Bar with Text */
    .poc-main-bar {
        background-color: #FE5900; 
        height: 60px;
        width: 100%;
        display: flex;
        align-items: center;
        padding: 0 40px 0 75px; 
    }
    
    /* The PoC Title Text */
    .poc-title {
        color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* 🟢 NEW: The Yellow Promo Banner */
    .poc-promo-banner {
        background-color: #ffeb85;
        height: 36px;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 14px;
        font-weight: 600;
        color: #000000;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }

/* 5. The Vertical Orange Line for Titles */
    .public-header {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: #111111;
        margin-top: 80px !important; /* 🟢 FIX: Increased to push the title safely below the header */
        margin-bottom: 20px;
        display: flex;
        align-items: center;
    }
    .public-header::before {
        content: '';
        display: inline-block;
        width: 4px;
        height: 24px;
        background-color: #ff5e00;
        margin-right: 10px;
        border-radius: 2px;
    }
    
    /* Ensure any default streamlit alerts/infos are hidden if they try to render */
    [data-testid="stAlert"] {
        display: none !important;
    }
</style>

<div class="poc-header-wrapper">
    <div class="poc-top-bar"></div>
    <div class="poc-main-bar">
        <div class="poc-title">Recommendation PoC</div>
    </div>
    <div class="poc-promo-banner">
        🟢 Engine v8.0 — Smartphones + Kids Books Clusters
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"

CLUSTER_CONFIG = {
    "Smartphones": {"allow_siblings": False, "hierarchy_cap": 2},
    "Kids Books":  {"allow_siblings": True,  "hierarchy_cap": 10},
}

# 🟢 THE VIRTUAL SALES BUMP: 
SMART_BOOST      = 15 
ECOSYSTEM_BOOST  = 100000
AVAIL_BOOST      = 2
HISTORY_BOOST    = 100000 
HISTORY_FREQ_MIN = 5
SERIES_BOOST     = 50000  # 🟢 NEW: Massive boost for series matches

TECH_CATS = {"IT", "Telephony", "TV"}
APPL_CATS = {"MDA", "SDA", "Air Condition", "Personal Care"}
COMPAT_COLS = ["Συμβατό με", "Συμβατή συσκευή"]
CC = "_Compatible"

# 🟢 THE WALLED GARDEN LIST
ANDROID_OEMS = {"SAMSUNG", "XIAOMI", "HUAWEI", "MOTOROLA", "HONOR", "POCO", "REALME", "ONEPLUS", "NOTHING"}

# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS CONFIGURATION
# ─────────────────────────────────────────────────────────────
KIDS_BOOKS_LEVEL2 = {"Greek Kids Books", "International Kids Books"}

# Age Bracket Definitions
AGE_BRACKETS = {
    "BRACKET_1": {  # Newborn & Sensory (0-5 months)
        "trigger": ["0+ μηνών", "0+ ετών", "3+ μηνών", "5+ μηνών"],
        "allowed": ["0+ μηνών", "0+ ετών", "3+ μηνών", "5+ μηνών", "6+ μηνών"]
    },
    "BRACKET_2": {  # Sitter & Crawler (6-11 months)
        "trigger": ["6+ μηνών", "9+ μηνών"],
        "allowed": ["6+ μηνών", "9+ μηνών", "12+ μηνών", "1+ ετών"]
    },
    "BRACKET_3": {  # Early Toddler (1-1.5 years)
        "trigger": ["12+ μηνών", "1+ ετών", "1.5+ ετών"],
        "allowed": ["9+ μηνών", "12+ μηνών", "1+ ετών", "1.5+ ετών", "24+ μηνών", "2+ ετών"]
    },
    "BRACKET_4": {  # Advanced Toddler (2 years)
        "trigger": ["24+ μηνών", "2+ ετών"],
        "allowed": ["1.5+ ετών", "24+ μηνών", "2+ ετών", "3+ ετών"]
    },
    "BRACKET_5": {  # Pre-School to Early Primary (3-6 years)
        "trigger": ["3+ ετών", "4+ ετών", "5+ ετών", "6+ ετών"],
        "allowed": ["3+ ετών", "4+ ετών", "5+ ετών", "6+ ετών", "7+ ετών", "8+ ετών"]
    },
    "BRACKET_6": {  # Older Kids & Tweens (7-12 years)
        "trigger": ["7+ ετών", "8+ ετών", "9+ ετών", "10+ ετών", "11+ ετών", "12+ ετών"],
        "allowed": ["6+ ετών", "7+ ετών", "8+ ετών", "9+ ετών", "10+ ετών", "11+ ετών", "12+ ετών", "13+ ετών", "14+ ετών"]
    },
    "BRACKET_7": {  # Teens & Collectors (13-18+ years)
        "trigger": ["13+ ετών", "14+ ετών", "15+ ετών", "16+ ετών", "17+ ετών", "18+ ετών"],
        "allowed": ["10+ ετών", "11+ ετών", "12+ ετών", "13+ ετών", "14+ ετών", "15+ ετών", "16+ ετών", "17+ ετών", "18+ ετών"]
    }
}

# Toy Hierarchies by Category
TOY_HIERARCHIES = {
    "toddler_preschool": ["ΦΙΓΟΥΡΕΣ & PLAYSET", "Διαδραστικά - Εκπαιδευτικά", "ΞΥΛΙΝΑ", 
                          "Επιτραπέζια & Παζλ", "ΒΡΕΦΙΚΑ ΠΑΙΧΝΙΔΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ", 
                          "Μουσικά Όργανα", "ΤΟΥΒΛΑΚΙΑ"],
    "learn_create": ["ΠΛΑΣΤΕΛΙΝΕΣ", "ΖΩΓΡΑΦΙΚΗ", "ΓΝΩΣΕΩΝ", "ΧΕΙΡΟΤΕΧΝΙΕΣ", 
                     "ΚΟΣΜΗΜΑΤΑ", "ΚΑΤΑΣΚΕΥΕΣ", "ΔΙΑΔΡΑΣΤΙΚΑ ΠΑΙΧΝΙΔΙΑ"],
    "board_puzzles": ["ΠΑΙΔΙΚΑ PUZZLES", "ΠΑΙΔΙΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "CARD GAMES", 
                      "ΟΙΚΟΓΕΝΕΙΑΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΓΡΙΦΟΙ", "3D PUZZLES"],
    "plush": ["ΛΟΥΤΡΙΝΑ"],
    "action_figures": ["ACTION FIGURES", "ΣΥΛΛΕΚΤΙΚΕΣ ΦΙΓΟΥΡΕΣ"],
    "dolls": ["ΚΟΥΚΛΕΣ"],
    "lego_building": ["LEGO", "PLAYMOBIL", "HARRY POTTER", "STARWARS", "MARVEL", 
                      "MINECRAFT", "NINJAGO", "SPIDEY", "Disney Princess"],
    "vehicles": ["ΑΥΤΟΚΙΝΗΤΑ"],
    "other_toys": ["ΚΟΥΖΙΝΙΚΑ - ΟΙΚΙΑΚΑ", "ΜΟΥΣΙΚΑ ΟΡΓΑΝΑ"],
    "outdoor_sports": ["ΜΠΑΛΕΣ ΑΘΛΗΜΑΤΩΝ", "ΑΘΛΗΤΙΣΜΟΣ - HOBBY"]
}

# Stationery Hierarchies by Category
STATIONERY_HIERARCHIES = {
    "arts_crafts": ["ΜΑΡΚΑΔΟΡΟΙ", "ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ", "ΚΗΡΟΜΠΟΓΙΕΣ-ΠΑΣΤΕΛ", 
                    "ΠΗΛΟΣ-ΠΛΑΣΤΕΛΙΝΗ", "ΜΠΛΟΚ-ΧΑΡΤΙΑ"],
    "kids_accessories": ["ΠΑΓΟΥΡΙΑ", "ΦΑΓΗΤΟΔΟΧΕΙΑ"],
    "writing": ["ΣΗΜΕΙΩΜΑΤΑΡΙΟ", "ΣΗΜΕΙΩΜΑΤΑΡΙΑ"],
    "gifts": ["READING ACCESSORIES"],
    "paper": ["ΣΕΛΙΔΟΔΕΙΚΤΕΣ"]
}

# Book Hierarchy Mappings for Cross-Sell Logic
BOOK_HIERARCHY_GROUPS = {
    "arts_activity": ["ΖΩΓΡΑΦΙΚΗ", "ΧΕΙΡΟΤΕΧΝΙΕΣ/ΚΑΤΑΣΚΕΥΕΣ", "ΑΥΤΟΚΟΛΛΗΤΑ", 
                      "ΔΡΑΣΤΗΡΙΟΤΗΤΕΣ-ΕΙΔΙΚΟΥ ΤΥΠΟΥ ΒΙΒΛΙΑ", "ΠΑΙΔΙΚΑ - ΒΙΒΛΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ", 
                      "ΤΕΧΝΗ", "ΜΟΥΣΙΚΗ"],
    "fiction_fantasy": ["ΠΑΙΔΙΚΑ - ΠΑΡΑΜΥΘΙΑ", "ΜΥΘΟΙ", "ΜΥΘΟΛΟΓΙΑ", "ΚΟΜΙΚΣ", 
                        "ΠΑΙΔΙΚΑ - ΜΥΘΟΙ & ΜΥΘΟΛΟΓΙΑ", "ΠΑΙΔΙΚΑ - ΚΟΜΙΚΣ & ΧΙΟΥΜΟΡ", 
                        "ΠΑΙΔΙΚΑ - BARBIE", "ΠΑΙΔΙΚΑ - ΒΙΒΛΙΑ", "ΠΑΙΔΙΚΑ", "ΧΙΟΥΜΟΡ",
                        "ΠΑΙΔΙΚΗ - ΕΦΗΒΙΚΗ ΛΟΓΟΤΕΧΝΙΑ ΣΤΑ ΕΛΛΗΝΙΚ", 
                        "ΠΑΙΔΙΚΗ - ΕΦΗΒΙΚΗ ΛΟΓΟΤΕΧΝΙΑ ΜΕΤΑΦΡΑΣΜΕΝ",
                        "ΕΛΛΗΝΙΚΗ ΠΑΙΔΙΚΗ-ΕΦΗΒΙΚΗ ΛΟΓΟΤΕΧΝΙΑ", 
                        "ΠΑΙΔΙΚΗ ΚΑΙ ΕΦΗΒΙΚΗ ΛΟΓΟΤΕΧΝΙΑ", "ΠΑΡΑΜΥΘΙΑ"],
    "stem_knowledge": ["ΕΦΕΥΡΕΣΕΙΣ/ΠΕΙΡΑΜΑΤΑ", "ΑΣΤΡΟΝΟΜΙΑ", "ΦΥΣΙΚΗ", "ΧΗΜΕΙΑ", 
                       "ΒΙΟΛΟΓΙΑ & ΑΝΘΡΩΠΙΝΟ ΣΩΜΑ", "ΠΑΙΔΙΚΑ - ΒΙΒΛΙΑ ΕΠΙΣΤΗΜΩΝ", 
                       "ΤΕΧΝΟΛΟΓΙΑ", "ΓΝΩΣΕΩΝ", "ΕΓΚΥΚΛΟΠΑΙΔΕΙΕΣ", "ΓΗ & ΠΕΡΙΒΑΛΛΟΝ", 
                       "ΟΙΚΟΛΟΓΙΑ", "ΖΩΑ", "ΙΣΤΟΡΙΑ", "ΓΕΩΓΡΑΦΙΑ/ΤΑΞΙΔΙΑ", "ΆΤΛΑΝΤΕΣ",
                       "ΠΑΙΔΙΚΑ - ΒΙΒΛΙΑ ΓΝΩΣΕΩΝ", "ΦΥΤΑ", "ΑΡΙΘΜΟΙ/ΑΡΙΘΜΗΤΙΚΗ",
                       "ΕΠΑΓΓΕΛΜΑΤΑ", "ΜΕΤΑΦΟΡΕΣ/ΟΧΗΜΑΤΑ"],
    "preschool": ["ΠΡΟΣΧΟΛΙΚΑ", "ΧΡΩΜΑΤΑ-ΣΧΗΜΑΤΑ", "ΑΝΤΙΘΕΤΑ", 
                  "ΠΑΙΔΙΚΑ - ΠΡΟΣΧΟΛΙΚΑ ΒΙΒΛΙΑ", "ΠΑΙΔΙΚΑ - ΒΙΒΛΙΑ ΜΕ ΤΡΑΓΟΥΔΙΑ",
                  "ΑΝΑΓΝΩΣΗ/ΓΡΑΦΗ", "ΛΕΞΙΚΑ"],
    "puzzle_activity": ["ΠΑΖΛ", "ΣΠΑΖΟΚΕΦΑΛΙΕΣ/ΑΙΝΙΓΜΑΤΑ", "ΠΑΙΧΝΙΔΙΑ", "ΑΥΤΟΚΟΛΛΗΤΑ",
                        "ΔΙΑΔΡΑΣΤΙΚΑ", "ΤΑΧΥΔΑΚΤΥΛΟΥΡΓΙΑ"],
    "cooking": ["ΜΑΓΕΙΡΙΚΗ"],
    "sports": ["ΑΘΛΗΤΙΣΜΟΣ"],
    "music": ["ΜΟΥΣΙΚΗ"]
}

# ─────────────────────────────────────────────────────────────
# ROLE → LOGIC KEY MAPPING (SMARTPHONES)
# ─────────────────────────────────────────────────────────────
def detect_logic_key(role: str) -> str:
    """Map a slot role string to a logic key based on spec"""
    r = role.lower()
    
    if "perfect fit" in r or "back cover" in r or "primary case" in r:
        return "PRIMARY_CASE"
    if "alternative" in r or "alt case" in r or "book cover" in r or "wallet" in r:
        return "ALT_CASE"
    if "screen" in r or "shield" in r:
        if "camera" not in r:
            return "SCREEN_GLASS"
    if "camera" in r:
        return "CAMERA_GLASS"
    if "power source" in r or "wall" in r or "charger" in r:
        if "car" not in r:
            return "WALL_CHARGER"
    if "backup power" in r or "powerbank" in r or "power bank" in r:
        return "POWERBANK"
    if "wearable" in r or "smartwatch" in r:
        return "SMARTWATCH"
    if "audio" in r or "earbud" in r or "handsfree" in r:
        return "EARBUDS"
    if "commute" in r or "holder" in r or "drive" in r:
        return "HOLDER"
    if "lifestyle" in r or "misc" in r or "cross" in r:
        return "CROSS_SELL"
    return "UNKNOWN"

# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────
def get_age_bracket(age_str: str) -> str:
    """Determine which age bracket a given age string belongs to"""
    age = str(age_str).strip().lower()
    for bracket_name, bracket_data in AGE_BRACKETS.items():
        if age in [a.lower() for a in bracket_data["trigger"]]:
            return bracket_name
    return "BRACKET_5"  # Default to pre-school if unknown

def get_allowed_ages(trigger_age: str) -> list:
    """Get the list of allowed ages for recommendations based on trigger age"""
    bracket = get_age_bracket(trigger_age)
    return AGE_BRACKETS.get(bracket, AGE_BRACKETS["BRACKET_5"])["allowed"]

def age_to_numeric(age_str: str) -> float:
    """Convert age string to numeric value for comparison"""
    age = str(age_str).strip().lower()
    # Handle months
    if "μηνών" in age:
        match = re.search(r'(\d+)', age)
        if match:
            return float(match.group(1)) / 12
    # Handle years
    if "ετών" in age:
        match = re.search(r'(\d+\.?\d*)', age)
        if match:
            return float(match.group(1))
    return 5.0  # Default

def is_toddler_age(age_str: str) -> bool:
    """Check if age is in toddler range (0-3 years)"""
    return age_to_numeric(age_str) <= 3

def is_preschool_age(age_str: str) -> bool:
    """Check if age is in pre-school/early primary range (4-7 years)"""
    num = age_to_numeric(age_str)
    return 4 <= num <= 7

def is_older_kids_age(age_str: str) -> bool:
    """Check if age is in older kids range (8+ years)"""
    return age_to_numeric(age_str) >= 8

def is_teen_age(age_str: str) -> bool:
    """Check if age is in teen range (12+ years)"""
    return age_to_numeric(age_str) >= 12

def match_ip_in_text(series_name: str, text: str) -> bool:
    """Check if book series/IP appears in text (brand, heroes, title)"""
    if not series_name or not text:
        return False
    series_lower = str(series_name).lower().strip()
    text_lower = str(text).lower()
    # Direct match
    if series_lower in text_lower:
        return True
    # Word-by-word match for multi-word series
    words = series_lower.split()
    if len(words) > 1:
        return all(w in text_lower for w in words if len(w) > 2)
    return False

# ─────────────────────────────────────────────────────────────
# PORT & COLOR HELPERS (SMARTPHONES)
# ─────────────────────────────────────────────────────────────
def extract_base_port(raw):
    s = str(raw).strip().lower()
    if not s or s == 'nan': return ''
    if 'type-c' in s or 'type c' in s or 'usb-c' in s or 'usb c' in s: return 'Type-C'
    if 'lightning' in s: return 'Lightning'
    if 'micro usb' in s or 'micro-usb' in s: return 'Micro USB'
    if 'usb' in s: return 'USB'
    return re.sub(r'\s*\d+\.?\d*\s*(gen\s*\d+)?', '', str(raw).strip(), flags=re.IGNORECASE).strip() or str(raw).strip()

COLOR_MAP = {
    'black titanium': ['μαύρο', 'black', 'διάφανο'],
    'natural titanium': ['διάφανο', 'μπεζ', 'natural'],
    'white titanium': ['λευκό', 'white', 'διάφανο'],
    'blue titanium': ['μπλε', 'blue', 'διάφανο'],
    'deep purple': ['μωβ', 'purple', 'διάφανο'],
    'space black': ['μαύρο', 'black', 'διάφανο'],
    'silver': ['ασημί', 'silver', 'διάφανο'],
    'gold': ['χρυσό', 'gold', 'διάφανο'],
    'starlight': ['λευκό', 'μπεζ', 'διάφανο'],
    'midnight': ['μαύρο', 'black', 'διάφανο'],
    'red': ['κόκκινο', 'red', 'διάφανο'],
    'pink': ['ροζ', 'pink', 'διάφανο'],
    'green': ['πράσινο', 'green', 'διάφανο'],
    'blue': ['μπλε', 'blue', 'διάφανο'],
}

def get_case_colors(c):
    k = c.strip().lower()
    for mk, mv in COLOR_MAP.items():
        if mk in k or k in mk: return mv
    return [k, 'διάφανο']

# ─────────────────────────────────────────────────────────────
# GENERAL HELPERS
# ─────────────────────────────────────────────────────────────
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
def has_data(df, col, pct=0.05):
    if col not in df.columns: return False
    v = df[col].fillna('').astype(str).str.strip()
    return ((v!='').sum()/len(df)) >= pct if len(df)>0 else False
def sample(df, col, n=5):
    if col not in df.columns: return f"[NO COL '{col}']"
    v = df[col].dropna().astype(str).str.strip(); v = v[v!='']
    return v.head(n).tolist() if not v.empty else "[EMPTY]"

# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    base = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet="
    
    # Load Products (Smartphones)
    dp = pd.read_csv(base+"Products"); dp.columns = dp.columns.str.strip()
    
    # Load History
    dh = pd.read_csv(base+"History");  dh.columns = dh.columns.str.strip()
    
    # Load Slot Matrix
    ds = pd.read_csv(base+"Slot_Matrix"); ds.columns = ds.columns.str.strip()
    
    # 🟢 NEW: Load Books sheet (contains Books + Toys + Stationery)
    try:
        db = pd.read_csv(base+"Books"); db.columns = db.columns.str.strip()
    except:
        db = pd.DataFrame()  # Empty if sheet doesn't exist
    
    # Merge compat columns for Products
    parts = [dp[c].fillna('').astype(str).str.strip() for c in COMPAT_COLS if c in dp.columns]
    found = [c for c in COMPAT_COLS if c in dp.columns]
    if parts:
        dp[CC] = parts[0]
        for p in parts[1:]:
            empty = dp[CC]==''
            dp.loc[empty, CC] = p[empty]
            dp.loc[~empty, CC] = dp.loc[~empty, CC] + ';' + p[~empty]
        dp[CC] = dp[CC].str.strip(';').str.replace(';;',';')
    else:
        dp[CC] = ''
    
    # Add empty compat column to Books if needed
    if not db.empty and CC not in db.columns:
        db[CC] = ''
    
    return dp, dh, ds, found, db

df_products, df_history, df_slots, compat_cols_found, df_books = load_data()

# ─────────────────────────────────────────────────────────────
# CLUSTER SELECTION
# ─────────────────────────────────────────────────────────────
st.sidebar.markdown("### 📦 Select Cluster")
active_cluster = st.sidebar.radio("", ["Smartphones", "Kids Books"], horizontal=True)

# ─────────────────────────────────────────────────────────────
# TRIGGER SELECTION BASED ON CLUSTER
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    phones = df_products[(df_products['Level 2']=='Mobiles')&(df_products['Hierarchy']=='Smartphones')]
    if phones.empty:
        phones = df_products[df_products['Level 2']=='Mobiles']
        st.sidebar.warning("⚠ Fallback to all Mobiles")
    if phones.empty:
        st.error("🚨 CRITICAL: No phones found at all! Check your Google Sheet.")
        st.stop()
    sel = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
    trigger = phones[phones['Title']==sel].iloc[0] if sel else None

elif active_cluster == "Kids Books":
    # 🟢 FIX: Use df_books instead of df_products
    if df_books.empty:
        st.error("🚨 CRITICAL: Books sheet not found! Check your Google Sheet.")
        st.stop()
    
    # Filter for Kids Books
    kids_books = df_books[
        (df_books['Level 1'] == 'Books') & 
        (df_books['Level 2'].isin(KIDS_BOOKS_LEVEL2))
    ]
    
    if kids_books.empty:
        # Fallback: try any books
        kids_books = df_books[df_books['Level 1'] == 'Books']
        st.sidebar.warning("⚠ Fallback to all Books")
    
    if kids_books.empty:
        st.error("🚨 CRITICAL: No kids books found! Check your Google Sheet.")
        st.stop()
    
    # Add series filter if available
    if 'Σειρά βιβλίου' in kids_books.columns:
        series_list = kids_books['Σειρά βιβλίου'].dropna().astype(str)
        series_list = series_list[series_list != '0'].unique().tolist()
        if series_list:
            series_options = ['All'] + sorted(series_list)
            selected_series = st.sidebar.selectbox("Filter by Series (optional):", series_options)
            if selected_series != 'All':
                kids_books = kids_books[kids_books['Σειρά βιβλίου'] == selected_series]
    
    sel = st.sidebar.selectbox("Select a Kids Book:", kids_books['Title'].unique())
    trigger = kids_books[kids_books['Title']==sel].iloc[0] if sel else None

if trigger is None:
    st.warning("Please select an item from the sidebar.")
    st.stop()

# ─────────────────────────────────────────────────────────────
# DISPLAY HEADER & TRIGGER CARD
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    st.markdown('<div class="public-header">Επιλογές για εσένα</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Συμβατά αξεσουάρ για το <b>{sel}</b></p>", unsafe_allow_html=True)
else:
    st.markdown('<div class="public-header">Διάλεξε κι άλλα!</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Προτάσεις με βάση το <b>{sel}</b></p>", unsafe_allow_html=True)

# Extract EXACT data from dataframe for sidebar card
card_title = safe(str(trigger.get('Title', sel)))
card_sku = safe(str(trigger.get('Material', 'N/A')))
card_img = safe(str(trigger.get('Thumbnails', '')).strip())
if not card_img or card_img == 'nan':
    card_img = "https://via.placeholder.com/150?text=No+Image"
    
card_avail = safe(str(trigger.get('AVAILABILITY', 'Άμεσα Διαθέσιμο')))

# Determine the color theme based on the exact availability text
if card_avail in ["Κατόπιν Παραγγελίας", "Αναμένεται Σύντομα"]:
    avail_theme = "avail-blue"
else:
    avail_theme = "avail-green"

# Format the exact price from LIST PRICE
try:
    raw_price = trigger.get('LIST PRICE', 0)
    t_price = parse_euro_price(raw_price)
except:
    t_price = 0.0
    
p_int = f"{int(t_price)}"
p_dec = f"{t_price:.2f}".split('.')[1]

# Create the HTML/CSS for the sidebar card
sidebar_card_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
body {{
    margin: 0;
    padding: 0;
    background-color: transparent;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}}
.sb-card {{
    border: 1px solid #eaeaea;
    border-radius: 12px;
    overflow: hidden;
    background: #fff;
    margin-top: 5px;
}}
.sb-img-container {{
    padding: 20px;
    text-align: center;
    background: #fff;
}}
.sb-img {{
    max-width: 100%;
    max-height: 220px;
    object-fit: contain;
}}
.sb-details {{
    background: #f8f9fa;
    padding: 15px;
    border-top: 1px solid #eaeaea;
}}
.sb-title {{
    font-size: 14px;
    font-weight: 700;
    color: #222;
    margin-bottom: 6px;
    line-height: 1.3;
}}
.sb-sku {{
    font-size: 10px;
    color: #666;
    margin-bottom: 10px;
}}
.sb-avail-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    padding: 4px 8px;
    border-radius: 6px;
    font-weight: 700;
    margin-bottom: 15px;
}}
.avail-green {{
    background-color: #e5f3f0;
    color: #00897b;
}}
.avail-blue {{
    background-color: #e6f0f6;
    color: #2385aa;
}}
.sb-bottom-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #eaeaea;
    padding-top: 15px;
}}
.sb-price-wrap {{
    color: #ff5e00;
    font-weight: 800;
    font-size: 24px;
    display: flex;
    align-items: flex-start;
    line-height: 1;
}}
.sb-price-dec {{
    font-size: 13px;
    font-weight: 700;
    margin-top: 2px;
}}
.sb-btn {{
    background: #ff5e00;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background 0.2s;
}}
.sb-btn:hover {{
    background: #e65500;
}}
</style>
</head>
<body>
<div class="sb-card">
    <div class="sb-img-container">
        <img class="sb-img" src="{card_img}" alt="Product Image">
    </div>
    <div class="sb-details">
        <div class="sb-title">{card_title}</div>
        <div class="sb-sku">ΚΩΔΙΚΟΣ: {card_sku}</div>
        
        <div class="sb-avail-badge {avail_theme}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            {card_avail}
        </div>
        
        <div class="sb-bottom-row">
            <div class="sb-price-wrap">
                {p_int}<span class="sb-price-dec">,{p_dec}€</span>
            </div>
            <button class="sb-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="9" cy="21" r="1"></circle>
                    <circle cx="20" cy="21" r="1"></circle>
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                </svg>
                Προσθήκη
            </button>
        </div>
    </div>
</div>
</body>
</html>
"""

with st.sidebar:
    components.html(sidebar_card_html, height=500, scrolling=False)


# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS ENGINE
# ─────────────────────────────────────────────────────────────
def run_books_engine(trigger, df_products, df_history):
    """
    Kids Books Recommendation Engine
    Priority 1: Series Engine (up to 10 slots)
    Priority 2: Physical Cross-Sell (up to 4 slots with Toys/Stationery)
    Priority 3: Category Discovery (remaining slots)
    """
    diag = []
    slot_assignments = []
    slot_notes = {}
    
    # Trigger attributes
    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    t_series = str(trigger.get('Σειρά βιβλίου', '')).strip()
    t_age = str(trigger.get('Ηλικία', '')).strip()
    t_rec_age = str(trigger.get('Προτεινόμενη Ηλικία', '')).strip()
    t_cover = str(trigger.get('Εξώφυλλο', '')).strip()
    t_dims = str(trigger.get('Διαστάσεις', '')).strip()
    t_illus = str(trigger.get('Λεπτομέρειες εικονογράφησης', '')).strip()
    t_pub_series = str(trigger.get('Εκδοτική Σειρά', '')).strip()
    t_pub_date = trigger.get('Ημερ/νία έκδοσης', '')
    t_orig_title = str(trigger.get('Τίτλος πρωτοτύπου', '')).strip()
    t_hierarchy = str(trigger.get('Hierarchy', '')).strip()
    t_level2 = str(trigger.get('Level 2', '')).strip()
    t_brand = str(trigger.get('Brand', '')).strip()
    t_heroes = str(trigger.get('Ήρωες Παιχνιδιών', '')).strip()
    t_price = parse_euro_price(trigger.get('LIST PRICE', 0))
    
    # Use recommended age if primary age is missing
    effective_age = t_age if t_age and t_age != 'nan' else t_rec_age
    allowed_ages = get_allowed_ages(effective_age)
    
    diag.append(("0. Trigger Info", "", f"Series: '{t_series}', Age: '{effective_age}', Hierarchy: '{t_hierarchy}'"))
    
    # Start with all products except trigger
    c = df_products[df_products['Material'] != tm].copy()
    diag.append(("1. Start (excl trigger)", len(c), ""))
    
    # Add sales tiebreaker
    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0
    
    # Stock filter
    if 'CW Stock Units' in c.columns:
        st_col = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        pct = (st_col > 0).sum() / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c['CW Stock Units'] = st_col.fillna(0)
            c = c[c['CW Stock Units'] > 0]
            diag.append(("2. Stock filter", len(c), f"Applied ({pct:.0%})"))
        else:
            diag.append(("2. Stock filter", len(c), f"⚠ SKIPPED ({pct:.0%})"))
    
    # Availability boost
    c['Avail_Boost'] = 0
    c.loc[c['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Avail_Boost'] = AVAIL_BOOST
    
    # Initialize slots
    all_recs = []
    slots_filled = 0
    MAX_SLOTS = 10
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 1: THE SERIES ENGINE (Up to 10 Slots)
    # ══════════════════════════════════════════════════════════
    series_notes = ["Priority 1: Series Engine"]
    
    if t_series and t_series != 'nan':
        # Filter for same series
        series_books = c[
            (c['Level 1'] == 'Books') & 
            (c['Σειρά βιβλίου'].fillna('').str.strip() == t_series)
        ].copy()
        series_notes.append(f"Found {len(series_books)} books in series '{t_series}'")
        
        # CRITICAL SAFETY: Exclude same original title
        if t_orig_title and t_orig_title != 'nan':
            before = len(series_books)
            series_books = series_books[
                series_books['Τίτλος πρωτοτύπου'].fillna('').str.strip() != t_orig_title
            ]
            series_notes.append(f"Excluded same original title: {before}→{len(series_books)}")
        
        # Language filter: Keep Greek with Greek, English with English
        if t_level2:
            before = len(series_books)
            series_books = series_books[series_books['Level 2'] == t_level2]
            series_notes.append(f"Level 2 filter ({t_level2}): {before}→{len(series_books)}")
        
        # THE FORMAT LOCK
        if not series_books.empty:
            # Cover type match
            if t_cover and t_cover != 'nan':
                before = len(series_books)
                cover_match = series_books[series_books['Εξώφυλλο'].fillna('').str.strip() == t_cover]
                if not cover_match.empty:
                    series_books = cover_match
                    series_notes.append(f"Cover match ({t_cover}): {before}→{len(series_books)}")
            
            # Dimensions match (same print run)
            if t_dims and t_dims != 'nan':
                before = len(series_books)
                dims_match = series_books[series_books['Διαστάσεις'].fillna('').str.strip() == t_dims]
                if not dims_match.empty:
                    series_books = dims_match
                    series_notes.append(f"Dimensions match: {before}→{len(series_books)}")
            
            # Illustrator match
            if t_illus and t_illus != 'nan':
                before = len(series_books)
                illus_match = series_books[series_books['Λεπτομέρειες εικονογράφησης'].fillna('').str.strip() == t_illus]
                if not illus_match.empty:
                    series_books = illus_match
                    series_notes.append(f"Illustrator match: {before}→{len(series_books)}")
            
            # Publisher series match
            if t_pub_series and t_pub_series != 'nan':
                before = len(series_books)
                pub_match = series_books[series_books['Εκδοτική Σειρά'].fillna('').str.strip() == t_pub_series]
                if not pub_match.empty:
                    series_books = pub_match
                    series_notes.append(f"Publisher series match: {before}→{len(series_books)}")
        
        # Sort by publication date (next in timeline first, then previous)
        if not series_books.empty and 'Ημερ/νία έκδοσης' in series_books.columns:
            try:
                series_books['_pub_date'] = pd.to_datetime(series_books['Ημερ/νία έκδοσης'], errors='coerce')
                trigger_date = pd.to_datetime(t_pub_date, errors='coerce')
                
                if pd.notna(trigger_date):
                    # Split into future and past
                    future = series_books[series_books['_pub_date'] > trigger_date].sort_values('_pub_date')
                    past = series_books[series_books['_pub_date'] <= trigger_date].sort_values('_pub_date', ascending=False)
                    series_books = pd.concat([future, past])
                    series_notes.append(f"Sorted by timeline: {len(future)} future, {len(past)} past")
            except:
                pass
        
        # Add series boost and assign slots
        if not series_books.empty:
            series_books['Final_Score'] = SERIES_BOOST + series_books['Avail_Boost'] + series_books['Sales_Tiebreaker']
            
            for idx, (_, row) in enumerate(series_books.head(MAX_SLOTS).iterrows()):
                row_copy = row.copy()
                row_copy['Assigned_Slot'] = idx + 1
                row_copy['Slot_Role'] = 'Series Book'
                row_copy['Item_Rank'] = 1
                all_recs.append(row_copy)
                slots_filled += 1
            
            series_notes.append(f"✓ Filled {slots_filled} slots with series books")
    else:
        series_notes.append("No series found on trigger")
    
    slot_notes[1] = series_notes
    diag.append(("3. Priority 1 (Series)", slots_filled, f"Slots filled: {slots_filled}/{MAX_SLOTS}"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 2: PHYSICAL CROSS-SELL (Up to 4 Slots)
    # ══════════════════════════════════════════════════════════
    MAX_CROSSSELL = 4
    crosssell_slots_used = 0
    crosssell_notes = ["Priority 2: Cross-Sell"]
    
    if slots_filled < MAX_SLOTS:
        remaining_crosssell = min(MAX_CROSSSELL, MAX_SLOTS - slots_filled)
        
        # Get IP for matching
        ip_name = t_series if t_series and t_series != 'nan' else t_brand
        
        # Filter to Toys and Stationery
        toys_stat = c[c['Level 1'].isin(['Toys', 'Stationery'])].copy()
        crosssell_notes.append(f"Toys/Stationery pool: {len(toys_stat)}")
        
        # Age filter for toys/stationery
        if 'Προτεινόμενη Ηλικία' in toys_stat.columns and effective_age:
            before = len(toys_stat)
            toys_stat = toys_stat[
                toys_stat['Προτεινόμενη Ηλικία'].fillna('').str.strip().isin(allowed_ages) |
                (toys_stat['Προτεινόμενη Ηλικία'].fillna('') == '')
            ]
            crosssell_notes.append(f"Age filter: {before}→{len(toys_stat)}")
        
        # Initialize scores
        toys_stat['Final_Score'] = toys_stat['Avail_Boost'] + toys_stat['Sales_Tiebreaker']
        
        # IP Match Boost
        if ip_name:
            ip_match = (
                toys_stat['Brand'].fillna('').apply(lambda x: match_ip_in_text(ip_name, x)) |
                toys_stat['Ήρωες Παιχνιδιών'].fillna('').apply(lambda x: match_ip_in_text(ip_name, x)) |
                toys_stat['Title'].fillna('').apply(lambda x: match_ip_in_text(ip_name, x))
            )
            toys_stat.loc[ip_match, 'Final_Score'] += SMART_BOOST * 3
            crosssell_notes.append(f"IP match boost applied to {ip_match.sum()} items")
        
        # ─── CROSS-SELL ITEM 1: Age-based prioritization ───
        item1_notes = ["Item 1 (Age-based)"]
        item1_candidates = pd.DataFrame()
        
        if is_toddler_age(effective_age):
            # Priority: Plush > Toddler toys > Arts
            item1_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['plush'] + TOY_HIERARCHIES['toddler_preschool'])
            ]
            item1_notes.append(f"Toddler: Plush/Preschool = {len(item1_candidates)}")
        elif is_preschool_age(effective_age):
            # Priority: Action Figures/Dolls > LEGO > Vehicles/Puzzles
            item1_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(
                    TOY_HIERARCHIES['action_figures'] + TOY_HIERARCHIES['dolls'] + 
                    TOY_HIERARCHIES['lego_building'] + TOY_HIERARCHIES['board_puzzles']
                )
            ]
            item1_notes.append(f"Preschool: Figures/LEGO/Puzzles = {len(item1_candidates)}")
        else:  # Older kids 8+
            # Priority: LEGO > Collectibles > Board Games
            item1_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(
                    TOY_HIERARCHIES['lego_building'] + TOY_HIERARCHIES['action_figures'] + 
                    TOY_HIERARCHIES['board_puzzles']
                )
            ]
            item1_notes.append(f"Older kids: LEGO/Action/Board = {len(item1_candidates)}")
        
        if item1_candidates.empty:
            # Fallback based on age
            if is_toddler_age(effective_age):
                item1_candidates = toys_stat[toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['plush'])]
            elif is_preschool_age(effective_age):
                item1_candidates = toys_stat[toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['board_puzzles'])]
            else:
                item1_candidates = toys_stat[toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['board_puzzles'])]
            item1_notes.append(f"Fallback: {len(item1_candidates)}")
        
        if not item1_candidates.empty and crosssell_slots_used < remaining_crosssell:
            best = item1_candidates.sort_values('Final_Score', ascending=False).iloc[0].copy()
            best['Assigned_Slot'] = slots_filled + crosssell_slots_used + 1
            best['Slot_Role'] = 'Cross-Sell: Toy'
            best['Item_Rank'] = 1
            all_recs.append(best)
            crosssell_slots_used += 1
            toys_stat = toys_stat[toys_stat['Material'] != best['Material']]
            item1_notes.append(f"✓ Selected: {best['Title'][:40]}...")
        
        slot_notes[slots_filled + 1] = item1_notes
        
        # ─── CROSS-SELL ITEM 2: Hierarchy-based ───
        item2_notes = ["Item 2 (Hierarchy-based)"]
        item2_candidates = pd.DataFrame()
        
        if t_hierarchy in BOOK_HIERARCHY_GROUPS.get('arts_activity', []):
            item2_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['arts_crafts'] + TOY_HIERARCHIES['learn_create'])
            ]
            item2_notes.append(f"Arts/Activity book → Arts supplies: {len(item2_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('fiction_fantasy', []):
            item2_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['lego_building'])
            ]
            item2_notes.append(f"Fiction book → LEGO/Building: {len(item2_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('stem_knowledge', []):
            item2_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['learn_create'])
            ]
            item2_notes.append(f"STEM book → Educational: {len(item2_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('preschool', []):
            item2_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['toddler_preschool'])
            ]
            item2_notes.append(f"Preschool book → Toddler toys: {len(item2_candidates)}")
        else:
            # Universal fallback
            if age_to_numeric(effective_age) <= 11:
                item2_candidates = toys_stat[
                    toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['arts_crafts'] + TOY_HIERARCHIES['plush'])
                ]
            else:
                item2_candidates = toys_stat[
                    (toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['plush'])) &
                    (toys_stat['Κατασκευαστής'].fillna('').str.upper() == 'SQUISHMALLOWS')
                ]
            item2_notes.append(f"Fallback: {len(item2_candidates)}")
        
        if not item2_candidates.empty and crosssell_slots_used < remaining_crosssell:
            best = item2_candidates.sort_values('Final_Score', ascending=False).iloc[0].copy()
            best['Assigned_Slot'] = slots_filled + crosssell_slots_used + 1
            best['Slot_Role'] = 'Cross-Sell: Creator'
            best['Item_Rank'] = 1
            all_recs.append(best)
            crosssell_slots_used += 1
            toys_stat = toys_stat[toys_stat['Material'] != best['Material']]
            item2_notes.append(f"✓ Selected: {best['Title'][:40]}...")
        
        slot_notes[slots_filled + 2] = item2_notes
        
        # ─── CROSS-SELL ITEM 3: Puzzle/Board Game ───
        item3_notes = ["Item 3 (Puzzle/Game)"]
        item3_candidates = pd.DataFrame()
        
        if t_hierarchy in BOOK_HIERARCHY_GROUPS.get('puzzle_activity', []):
            item3_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['board_puzzles'])
            ]
            item3_notes.append(f"Puzzle book → Puzzles: {len(item3_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('stem_knowledge', []):
            item3_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(['ΓΝΩΣΕΩΝ'])
            ]
            item3_notes.append(f"STEM book → Knowledge games: {len(item3_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('preschool', []):
            item3_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(['ΒΡΕΦΙΚΑ ΠΑΙΧΝΙΔΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ'] + TOY_HIERARCHIES['plush'])
            ]
            item3_notes.append(f"Preschool → Baby activity/Plush: {len(item3_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('fiction_fantasy', []):
            # Reading accessories for fiction readers
            item3_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['gifts'] + STATIONERY_HIERARCHIES['paper'])
            ]
            item3_notes.append(f"Fiction → Reading accessories: {len(item3_candidates)}")
        
        if item3_candidates.empty:
            item3_candidates = toys_stat[toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['board_puzzles'])]
            item3_notes.append(f"Fallback to puzzles: {len(item3_candidates)}")
        
        if not item3_candidates.empty and crosssell_slots_used < remaining_crosssell:
            best = item3_candidates.sort_values('Final_Score', ascending=False).iloc[0].copy()
            best['Assigned_Slot'] = slots_filled + crosssell_slots_used + 1
            best['Slot_Role'] = 'Cross-Sell: Interactive'
            best['Item_Rank'] = 1
            all_recs.append(best)
            crosssell_slots_used += 1
            toys_stat = toys_stat[toys_stat['Material'] != best['Material']]
            item3_notes.append(f"✓ Selected: {best['Title'][:40]}...")
        
        slot_notes[slots_filled + 3] = item3_notes
        
        # ─── CROSS-SELL ITEM 4: Lifestyle/Theme ───
        item4_notes = ["Item 4 (Lifestyle)"]
        item4_candidates = pd.DataFrame()
        
        if t_hierarchy in BOOK_HIERARCHY_GROUPS.get('stem_knowledge', []):
            item4_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(['ΔΙΑΔΡΑΣΤΙΚΑ ΠΑΙΧΝΙΔΙΑ', '3D PUZZLES'])
            ]
            item4_notes.append(f"STEM → Interactive/3D: {len(item4_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('cooking', []):
            item4_candidates = toys_stat[toys_stat['Hierarchy'].isin(['ΚΟΥΖΙΝΙΚΑ - ΟΙΚΙΑΚΑ'])]
            item4_notes.append(f"Cooking → Kitchen: {len(item4_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('sports', []):
            item4_candidates = toys_stat[toys_stat['Hierarchy'].isin(TOY_HIERARCHIES['outdoor_sports'])]
            item4_notes.append(f"Sports → Sports toys: {len(item4_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('music', []):
            item4_candidates = toys_stat[toys_stat['Hierarchy'].isin(['ΜΟΥΣΙΚΑ ΟΡΓΑΝΑ'])]
            item4_notes.append(f"Music → Instruments: {len(item4_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('preschool', []):
            item4_candidates = toys_stat[
                toys_stat['Hierarchy'].isin(['ΞΥΛΙΝΑ', 'Επιτραπέζια & Παζλ'])
            ]
            item4_notes.append(f"Preschool → Wooden/Puzzle: {len(item4_candidates)}")
        elif t_hierarchy in BOOK_HIERARCHY_GROUPS.get('fiction_fantasy', []):
            if age_to_numeric(effective_age) <= 11:
                item4_candidates = toys_stat[
                    toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['kids_accessories'])
                ]
                item4_notes.append(f"Fiction (young) → Water bottles: {len(item4_candidates)}")
            else:
                item4_candidates = toys_stat[
                    toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['writing'] + STATIONERY_HIERARCHIES['kids_accessories'])
                ]
                item4_notes.append(f"Fiction (teen) → Notebooks/Bottles: {len(item4_candidates)}")
        
        if item4_candidates.empty:
            item4_candidates = toys_stat[toys_stat['Hierarchy'].isin(STATIONERY_HIERARCHIES['kids_accessories'])]
            item4_notes.append(f"Fallback to water bottles: {len(item4_candidates)}")
        
        if not item4_candidates.empty and crosssell_slots_used < remaining_crosssell:
            best = item4_candidates.sort_values('Final_Score', ascending=False).iloc[0].copy()
            best['Assigned_Slot'] = slots_filled + crosssell_slots_used + 1
            best['Slot_Role'] = 'Cross-Sell: Lifestyle'
            best['Item_Rank'] = 1
            all_recs.append(best)
            crosssell_slots_used += 1
            toys_stat = toys_stat[toys_stat['Material'] != best['Material']]
            item4_notes.append(f"✓ Selected: {best['Title'][:40]}...")
        
        slot_notes[slots_filled + 4] = item4_notes
        
        crosssell_notes.append(f"✓ Filled {crosssell_slots_used} cross-sell slots")
    
    slots_filled += crosssell_slots_used
    diag.append(("4. Priority 2 (Cross-Sell)", crosssell_slots_used, f"Total slots: {slots_filled}/{MAX_SLOTS}"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 3: CATEGORY DISCOVERY (Remaining Slots)
    # ══════════════════════════════════════════════════════════
    discovery_notes = ["Priority 3: Category Discovery"]
    discovery_count = 0
    
    if slots_filled < MAX_SLOTS:
        remaining = MAX_SLOTS - slots_filled
        
        # Get books from same hierarchy and age bracket
        discovery_pool = c[
            (c['Level 1'] == 'Books') &
            (c['Hierarchy'] == t_hierarchy)
        ].copy()
        discovery_notes.append(f"Same hierarchy pool: {len(discovery_pool)}")
        
        # Exclude already recommended
        already_recs = [r['Material'] for r in all_recs]
        discovery_pool = discovery_pool[~discovery_pool['Material'].isin(already_recs)]
        
        # Exclude same original title
        if t_orig_title and t_orig_title != 'nan':
            discovery_pool = discovery_pool[
                discovery_pool['Τίτλος πρωτοτύπου'].fillna('').str.strip() != t_orig_title
            ]
        
        # Language filter
        if t_level2:
            discovery_pool = discovery_pool[discovery_pool['Level 2'] == t_level2]
        
        # Age filter
        if 'Ηλικία' in discovery_pool.columns and allowed_ages:
            discovery_pool = discovery_pool[
                discovery_pool['Ηλικία'].fillna('').str.strip().isin(allowed_ages) |
                (discovery_pool['Ηλικία'].fillna('') == '')
            ]
        
        discovery_notes.append(f"After filters: {len(discovery_pool)}")
        
        # Score and sort by best sellers
        discovery_pool['Final_Score'] = discovery_pool['Avail_Boost'] + discovery_pool['Sales_Tiebreaker']
        discovery_pool = discovery_pool.sort_values('Final_Score', ascending=False)
        
        for idx, (_, row) in enumerate(discovery_pool.head(remaining).iterrows()):
            row_copy = row.copy()
            row_copy['Assigned_Slot'] = slots_filled + discovery_count + 1
            row_copy['Slot_Role'] = 'Category Discovery'
            row_copy['Item_Rank'] = idx + 1
            all_recs.append(row_copy)
            discovery_count += 1
        
        discovery_notes.append(f"✓ Filled {discovery_count} discovery slots")
    
    slot_notes[slots_filled + 1] = discovery_notes if discovery_count > 0 else []
    slots_filled += discovery_count
    diag.append(("5. Priority 3 (Discovery)", discovery_count, f"Final total: {slots_filled}/{MAX_SLOTS}"))
    
    # Build final dataframe
    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot'] * 100 + recs_df['Item_Rank']
        recs_df = recs_df.sort_values('Draft_Score').reset_index(drop=True)
        return recs_df, diag, slot_notes, recs_df
    else:
        return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# SMARTPHONES ENGINE (Original)
# ─────────────────────────────────────────────────────────────
def run_engine(trigger, df_products, df_history, df_slots):
    diag, slot_diag, slot_notes = [], [], {}

    # Trigger attrs
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
        "SAMSUNG": ["samsung", "galaxy"],
        "APPLE": ["apple", "iphone", "ipad"],
        "XIAOMI": ["xiaomi", "redmi", "poco"],
        "OPPO": ["oppo"],
        "MOTOROLA": ["motorola", "moto"],
        "HUAWEI": ["huawei"],
        "HONOR": ["honor"],
        "REALME": ["realme"],
        "ONEPLUS": ["oneplus"],
        "VIVO": ["vivo"],
        "NOTHING": ["nothing", "cmf"]
    }
    rival_kws = []
    for k, v in brand_kws.items():
        if k != tb:
            rival_kws.extend(v)
    rival_regex = r"\b(" + "|".join(rival_kws) + r")\b" if rival_kws else ""

    c = df_products[df_products['Material']!=tm].copy()
    diag.append(("0. Start", len(c), ""))

    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0

    c = c[c['Title']!=tt]; diag.append(("1. U2a: title dedup", len(c), ""))

    if 'CW Stock Units' in c.columns:
        st_col = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        pct = (st_col>0).sum()/len(c) if len(c)>0 else 0
        if pct >= 0.10:
            c['CW Stock Units']=st_col.fillna(0); c=c[c['CW Stock Units']>0]
            diag.append(("2. U2b: stock", len(c), f"Applied ({pct:.0%})"))
        else: diag.append(("2. U2b: stock", len(c), f"⚠ SKIPPED ({pct:.0%})"))
    else: diag.append(("2. U2b: stock", len(c), "⚠ SKIPPED (no col)"))

    mask = (c['Hierarchy']==thier) & (c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb)
    ns = mask.sum()
    if ns > 0:
        sims = c.loc[mask,'Title'].apply(lambda t: title_sim(tt,str(t)))
        dupes = sims[sims>=70].index; c=c.drop(dupes)
        diag.append(("3. U1: siblings", len(c), f"Checked {ns}, removed {len(dupes)}"))
    else: diag.append(("3. U1: siblings", len(c), "No siblings"))

    b4=len(c)
    if tl1 in TECH_CATS: c=c[~c['Level 1'].isin(APPL_CATS)]
    elif tl1 in APPL_CATS: c=c[~c['Level 1'].isin(TECH_CATS)]
    diag.append(("4a. U3: macro wall", len(c), f"Removed {b4-len(c)}"))

    b4eco = len(c)
    if tb == "APPLE":
        c = c[~c['Κατασκευαστής'].fillna('').str.strip().str.upper().isin(ANDROID_OEMS)]
    elif tb in ANDROID_OEMS:
        c = c[c['Κατασκευαστής'].fillna('').str.strip().str.upper() != "APPLE"]
    diag.append(("4b. U4: ecosystem wall", len(c), f"Removed {b4eco-len(c)} rival OEM items"))

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
        c.loc[c['Μοντέλο'].fillna('').str.contains(strict_tmod, case=False, regex=True), 'Smart_Boost'] += SMART_BOOST
        
    c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Smart_Boost']+=SMART_BOOST
    
    c['Final_Score'] = c['History_Score'] + c['Frequency'] + c['Avail_Boost'] + c['Smart_Boost'] + c['Sales_Tiebreaker']

    b4u5=len(c)
    nhm=c['History_Score']==0
    if nhm.any():
        ok2=c.loc[nhm].apply(lambda r: price_ok(tprice,r['Next_Price'],tl1), axis=1)
        c=c.drop(ok2[~ok2].index)
    diag.append(("5. U5: price ceiling", len(c), f"Removed {b4u5-len(c)} (ceil: €{max(tprice*0.40,45):.0f})"))

    all_slot = []
    for _, sr in df_slots.iterrows():
        sn = sr['Slot_Number']
        role = str(sr.get('Slot_Role',''))
        lk = detect_logic_key(role)
        ah = [h.strip() for h in str(sr['Allowed_Hierarchies']).split(",")]
        sc = c[c['Hierarchy'].isin(ah)].copy()
        afh = len(sc)
        notes = [f"Logic: {lk}"]

        # [SIMPLIFIED: Include only PRIMARY_CASE logic as example - full logic in original]
        if lk == "PRIMARY_CASE":
            if strict_tmod:
                b4 = len(sc)
                cv = sc[CC].fillna('').str.lower()
                m = sc[cv.str.contains(strict_tmod, case=False, regex=True)]
                if rival_regex and not m.empty:
                    m = m[~m[CC].fillna('').str.lower().str.contains(rival_regex, regex=True)]
                    m = m[~m['Title'].fillna('').str.lower().str.contains(rival_regex, regex=True)]
                notes.append(f"Strict Model '{tmod}': {b4}→{len(m)}")
                sc = m  
            else:
                sc = sc.head(0) 

            if not sc.empty:
                b4=len(sc)
                f=sc[sc['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                notes.append(f"Back Cover: {b4}→{len(f)}")
                sc = f  
                
            if not sc.empty and tcol:
                b4=len(sc)
                sc_color=sc[sc['Χρώμα'].fillna('').str.strip().str.lower().isin(ccols)]
                notes.append(f"Color {ccols[:3]}: {b4}→{len(sc_color)}")
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

    diag.append(("6. Final", len(sel), f"Hierarchy cap=2"))
    return (pd.DataFrame(sel) if sel else pd.DataFrame()), diag, slot_diag, slot_notes, full


# ─────────────────────────────────────────────────────────────
# RUN ENGINE BASED ON CLUSTER
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    recs, diag, slot_diag, slot_notes, full_candidates = run_engine(trigger, df_products, df_history, df_slots)
else:  # Kids Books
    # 🟢 FIX: Use df_books for the books engine
    recs, diag, slot_notes, full_candidates = run_books_engine(trigger, df_books, df_history)
    slot_diag = []  # Not used for books

# Marketing Copy
MARKETING_COPY = {
    "PRIMARY_CASE": "Απόλυτη προστασία & τέλεια εφαρμογή.",
    "SCREEN_GLASS": "Αόρατη ασπίδα για την οθόνη σου.",
    "WALL_CHARGER": "Γρήγορη και απόλυτα ασφαλής φόρτιση.",
    "EARBUDS": "Κορυφαία, ασύρματη ακουστική εμπειρία.",
    "POWERBANK": "Ενέργεια on-the-go για να μη μένεις ποτέ.",
    "CROSS_SELL": "Smart gadget για το οικοσύστημά σου.",
    "CAMERA_GLASS": "Θωράκιση φακών για τέλειες λήψεις.",
    "SMARTWATCH": "Ο απόλυτος σύντροφος για τον καρπό σου.",
    "HOLDER": "Σταθερή τοποθέτηση για το αυτοκίνητο.",
    "ALT_CASE": "Premium προστασία και πρακτικότητα.",
    # Books-specific
    "Series Book": "Η συνέχεια της περιπέτειας σε περιμένει!",
    "Cross-Sell: Toy": "Ο τέλειος σύντροφος για παιχνίδι!",
    "Cross-Sell: Creator": "Δημιούργησε, φαντάσου, εξερεύνα!",
    "Cross-Sell: Interactive": "Μάθε παίζοντας!",
    "Cross-Sell: Lifestyle": "Στιλ και πρακτικότητα καθημερινά.",
    "Category Discovery": "Μια ακόμα εξαιρετική επιλογή!",
}


if not recs.empty:
    rts = recs.head(10)
    ch = ""
    for _, r in rts.iterrows():
        iu=safe(str(r.get('Thumbnails','')).strip())
        rp=parse_euro_price(r.get('LIST PRICE',0))
        np=f"{rp:.2f}".replace('.',','); op=f"{(rp*1.25):.2f}".replace('.',',')
        ti=safe(str(r.get('Title',''))); sn=int(r.get('Assigned_Slot',0))
        
        raw_role = str(r.get('Slot_Role',''))
        
        # Get marketing text
        if active_cluster == "Smartphones":
            lk = detect_logic_key(raw_role)
            marketing_text = MARKETING_COPY.get(lk, "Ιδανική προσθήκη για να ολοκληρώσεις την αγορά σου.")
        else:
            marketing_text = MARKETING_COPY.get(raw_role, "Μια εξαιρετική επιλογή για εσένα!")
        
        ch+=f"""<div class="pc">
            <div class="sb">Slot {sn}</div>
            <img src="{iu}" alt="product">
            <div class="ti" title="{ti}">{ti}</div>
            <div class="sr">{marketing_text}</div>
            <div class="rv"><span class="sc">4.8</span> <span class="st">&#9733;&#9733;&#9733;&#9733;&#9733;</span> <span class="ct">(305)</span></div>
            <div class="op">&#928;.&#923;.&#932;. : {op}&#8364;</div>
            <div class="np">{np.split(',')[0]}<span class="dm">,{np.split(',')[1]}&#8364;</span></div>
            <button class="cb">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="9" cy="21" r="1"></circle>
                    <circle cx="20" cy="21" r="1"></circle>
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
                </svg>
            </button>
        </div>"""

    css="""
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:transparent}
    
    .desktop-wrapper { background-color: #f8f9fa; border-radius: 16px; padding: 30px; margin: 10px 0; position: relative; }
    .desktop-header { font-size: 24px; font-weight: 700; margin-bottom: 25px; color: #111; display:flex; align-items:center; }
    .desktop-header span { color: #ff5e00; margin-right: 10px; font-size: 26px; line-height: 1; font-weight: 900; }
    
    .car { display:flex; overflow-x:auto; gap:15px; padding-bottom:10px; scrollbar-width:none; scroll-behavior: smooth; }
    .car::-webkit-scrollbar { display: none; }
    
    .pc { background:#fff; border:1px solid #eaeaea; border-radius:12px; padding:15px 12px; display:flex; flex-direction:column; align-items:center; box-shadow:0 2px 5px rgba(0,0,0,.04); position:relative; flex-shrink:0; width:195px; min-width:195px; }
    .sb { position:absolute; top:8px; left:8px; background:#ff5e00; color:#fff; font-size:10px; font-weight:700; padding:3px 6px; border-radius:6px; z-index:10; }
    .pc img { height:110px; width:auto; object-fit:contain; margin-bottom:15px; margin-top:10px; }
    .ti { font-size:13px; color:#333; text-align:center; height:36px; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; margin-bottom:6px; line-height:1.3; padding:0 5px; }
    
    .sr { 
        font-size: 10px; 
        color: #777; 
        margin-bottom: 12px; 
        text-align: center; 
        height: 28px;
        overflow: hidden; 
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        line-height: 1.35;
        width: 100%; 
        padding: 0 4px;
    }
    
    .rv { font-size:11px; margin-bottom:15px }
    .sc { color:#ff5e00; font-weight:700 }
    .st { color:#ff5e00; letter-spacing:-2px }
    .ct { color:#1a73e8 }
    .op { font-size:11px; color:#888; text-decoration:line-through; margin-bottom:2px }
    .np { font-size:18px; font-weight:700; color:#ff5e00; margin-bottom:15px }
    .dm { font-size:12px }
    .cb { background:#ff5e00; color:#fff; border:none; border-radius:8px; width:40px; height:35px; cursor:pointer; transition: background 0.2s; display: flex; justify-content: center; align-items: center; }
    .cb:hover { background:#e65500 }
    
    .nav-btn {
        position: absolute;
        top: 55%;
        transform: translateY(-50%);
        width: 44px;
        height: 44px;
        background-color: #fff;
        border: 1px solid #eaeaea;
        border-radius: 50%;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 100;
        transition: transform 0.2s, box-shadow 0.2s, opacity 0.3s;
    }
    .nav-btn:hover {
        transform: translateY(-50%) scale(1.05);
        box-shadow: 0 6px 14px rgba(0,0,0,0.15);
    }
    
    .nav-left { left: 10px; opacity: 0; pointer-events: none; }
    .nav-right { right: 10px; }
    
    .nav-left::after {
        content: ''; width: 10px; height: 10px;
        border-top: 2px solid #555; border-left: 2px solid #555;
        transform: rotate(-45deg); margin-left: 4px;
    }
    .nav-right::after {
        content: ''; width: 10px; height: 10px;
        border-top: 2px solid #555; border-right: 2px solid #555;
        transform: rotate(45deg); margin-right: 4px;
    }
    """

    # Dynamic header based on cluster
    if active_cluster == "Smartphones":
        header_text = "Μαζί με αυτό, οι περισσότεροι αγοράζουν"
    else:
        header_text = "Συνέχισε την περιπέτεια"

    dp=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head>
    <body>
    <div class="desktop-wrapper">
        <div class="desktop-header"><span>|</span>{header_text}</div>
        <div class="nav-btn nav-left" id="btnLeft" onclick="scrollL()"></div>
        <div class="car" id="scrollContainer">{ch}</div>
        <div class="nav-btn nav-right" id="btnRight" onclick="scrollR()"></div>
    </div>

    <script>
        const container = document.getElementById('scrollContainer');
        const btnLeft = document.getElementById('btnLeft');
        const btnRight = document.getElementById('btnRight');
        const scrollAmount = 405; 

        function scrollL() {{ container.scrollBy({{ left: -scrollAmount, behavior: 'smooth' }}); }}
        function scrollR() {{ container.scrollBy({{ left: scrollAmount, behavior: 'smooth' }}); }}

        container.addEventListener('scroll', () => {{
            if (container.scrollLeft > 5) {{
                btnLeft.style.opacity = '1'; btnLeft.style.pointerEvents = 'auto';
            }} else {{
                btnLeft.style.opacity = '0'; btnLeft.style.pointerEvents = 'none';
            }}
            if (container.scrollLeft + container.clientWidth >= container.scrollWidth - 2) {{
                btnRight.style.opacity = '0'; btnRight.style.pointerEvents = 'none';
            }} else {{
                btnRight.style.opacity = '1'; btnRight.style.pointerEvents = 'auto';
            }}
        }});
        container.dispatchEvent(new Event('scroll'));
    </script>
    </body></html>"""

    components.html(dp, height=540, scrolling=False)

else:
    st.error("❌ No recommendations. Check diagnostics below.")


# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
st.markdown("---")

st.markdown("""
<style>
[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #d9d9d9 !important;
    border-radius: 12px !important;
    box-shadow: none !important;
    margin-top: 20px;
}
[data-testid="stExpander"] summary {
    padding: 24px 30px !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stExpander"] summary:hover {
    background-color: transparent !important;
}
[data-testid="stExpander"] summary p {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #000000 !important;
    flex-grow: 1;
}
[data-testid="stExpander"] summary svg {
    display: none !important;
}
[data-testid="stExpander"] summary::after {
    content: '';
    display: inline-block;
    width: 12px;
    height: 12px;
    border-right: 2px solid #111;
    border-bottom: 2px solid #111;
    transform: rotate(45deg);
    transition: transform 0.2s ease;
    margin-top: -4px;
}
[data-testid="stExpander"][open] summary::after {
    transform: rotate(225deg);
    margin-top: 6px;
}
[data-testid="stExpanderDetails"] {
    padding: 10px 30px 30px 30px !important;
}
</style>
""", unsafe_allow_html=True)

with st.expander("⚙️ System Diagnostics & Engine Math"):
    st.markdown(f"### Active Cluster: **{active_cluster}**")
    
    if active_cluster == "Smartphones":
        tpr = str(trigger.get('Θύρα USB','')).strip()
        tp2 = extract_base_port(tpr)
        tc2 = str(trigger.get('Χρώμα','')).strip()
        cc2 = get_case_colors(tc2)
        st.markdown(f"**Port:** `{tpr}` → **`{tp2}`** | **Color:** `{tc2}` → **{cc2}** | **Compat cols:** {compat_cols_found}")
    else:
        t_series = str(trigger.get('Σειρά βιβλίου', '')).strip()
        t_age = str(trigger.get('Ηλικία', '')).strip()
        t_hierarchy = str(trigger.get('Hierarchy', '')).strip()
        st.markdown(f"**Series:** `{t_series}` | **Age:** `{t_age}` | **Hierarchy:** `{t_hierarchy}`")

    st.markdown("### Engine Funnel")
    st.dataframe(pd.DataFrame(diag, columns=["Step","Count/Value","Note"]), use_container_width=True, hide_index=True)

    if active_cluster == "Smartphones" and slot_diag:
        st.markdown("### Per-Slot Breakdown")
        st.dataframe(pd.DataFrame(slot_diag, columns=["Slot","Role","Logic","After Hierarchy","After Attributes"]), use_container_width=True, hide_index=True)

    st.markdown("### Slot Filter Details")
    for sn, notes in sorted(slot_notes.items()):
        if notes:
            st.markdown(f"**Slot {sn}**")
            for n in notes: 
                st.text(n)

    st.markdown("### 📋 Trigger Attributes")
    if active_cluster == "Smartphones":
        cols = ['Material','Title','Level 1','Level 2','Hierarchy','Κατασκευαστής','Μοντέλο',
                'Θύρα USB','Χρώμα','Λειτουργικό σύστημα','Extra Χαρακτηριστικά','LIST PRICE']
    else:
        cols = ['Material','Title','Level 1','Level 2','Hierarchy','Σειρά βιβλίου','Ηλικία',
                'Προτεινόμενη Ηλικία','Εξώφυλλο','Διαστάσεις','Λεπτομέρειες εικονογράφησης',
                'Εκδοτική Σειρά','Brand','Ήρωες Παιχνιδιών','LIST PRICE']
    for col in cols:
        st.text(f"{col}: {trigger.get(col,'N/A')}")

    if not recs.empty:
        st.markdown("### 🏆 Final Recommendations")
        if active_cluster == "Smartphones":
            dc=['Title','Hierarchy','Assigned_Slot','Slot_Role','Item_Rank','History_Score','Frequency','Avail_Boost','Smart_Boost','Sales_Tiebreaker','Final_Score']
        else:
            dc=['Title','Hierarchy','Assigned_Slot','Slot_Role','Item_Rank','Avail_Boost','Sales_Tiebreaker','Final_Score']
        st.dataframe(recs[[c for c in dc if c in recs.columns]], use_container_width=True, hide_index=True)
