import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
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
        top: 35px !important;
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
    /* Sidebar collapsed toggle → small round orange dot */
    [data-testid="stSidebarCollapsedControl"] {
        position: fixed !important;
        top: 70px !important;
        left: 8px !important;
        z-index: 1000002 !important;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        width: 32px !important;
        height: 32px !important;
        min-height: 32px !important;
        border-radius: 50% !important;
        background-color: #ff5e00 !important;
        border: 2px solid #ffffff !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2) !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="stSidebarCollapsedControl"] button svg {
        width: 16px !important;
        height: 16px !important;
        fill: #ffffff !important;
        color: #ffffff !important;
    }
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
        🟢 Engine v22.1 — Peripherals: Mouse/KB/Gaming Mouse/Gaming KB + Streaming Είδος + Monitors (dedicated HDMI/DP/USB ports) + Backfill + Printers + Webcam + USB Hub
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

# ═════════════════════════════════════════════════════════════
# 🟢 LAPTOPS CONFIGURATION (Mainstream / Road Warrior)
# ═════════════════════════════════════════════════════════════
LAPTOP_L2_VALUES = {"Notebooks", "Laptops"}
 
# (slot_num, role_label, [hierarchies], logic_key)
LAPTOP_MAINSTREAM_SLOTS = [
    (1,  'Τσάντα Laptop',    ['NB BAGS'],                                    'BAG_SIZE'),
    (2,  'Φορτιστής',        ['NB POWER SUPPLIERS', 'APPLE ORIGINAL POWER SUPPLY'], 'CHARGER_PORT'),
    (3,  'Powerbank',        ['POWER STATIONS'],                             'HIGH_WATT_PB'),
    (4,  'Ασύρματο Mouse',   ['MOUSE WIRELESS'],                             'MOUSE_LOGIC'),
    (5,  'Mousepad',         ['MOUSE PADS'],                                 'MOUSEPAD_LOGIC'),
    (6,  'Βάση / Cooler',    ['NOTEBOOK COOLERS', 'ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],        'STAND_SIZE'),
    (7,  'Οθόνη',            ['TFT MONITOR'],                                'MONITOR_LOGIC'),
    (8,  'Αποθήκευση',       ['USB FLASH', 'EXTERNAL HDD USB', 'EXTERNAL SSD USB', 'PORTABLE SSD', 'SSD EXTERNAL'],              'STORAGE_LOGIC'),
    (9,  'Headset / Office', ['OVERHEAD', 'BLUETOOTH', 'OFFICE SUITES', 'APPLE HEADPHONES', 'APPLE ORIGINAL HEADPHONES'], 'OFFICE_HEADSET_LOGIC'),
    (10, 'Θήκη Laptop',      ['ΘΗΚΕΣ SLEEVE LAPTOP'],                        'SLEEVE_SIZE'),
]
 
LAPTOP_MARKETING_COPY = {
    "Τσάντα Laptop": "Άνετη μεταφορά παντού.",
    "Θήκη Laptop": "Slim προστασία.",
    "Φορτιστής": "Γρήγορη, ασφαλής φόρτιση.",
    "Powerbank": "Ενέργεια για όλη τη μέρα.",
    "Ασύρματο Mouse": "Ελευθερία κινήσεων.",
    "Mousepad": "Ομαλή κίνηση, σταθερή βάση.",
    "Βάση / Cooler": "Ιδανική στάση & ψύξη.",
    "Οθόνη": "Περισσότερο workspace.",
    "Αποθήκευση": "Κράτα τα αρχεία σου ασφαλή.",
    "Headset / Office": "Ολοκλήρωσε το setup σου.",
}


# ═════════════════════════════════════════════════════════════
# 🟢 FLOOR CARE CONFIGURATION
# ═════════════════════════════════════════════════════════════
FLOOR_CARE_TRIGGER_HIERARCHIES = {
    "ΗΛΕΚΤΡΙΚΕΣ ΣΚΟΥΠΕΣ", "ΣΚΟΥΠΕΣ STICK", "ΗΛΕΚΤΡΙΚΈΣ ΣΚΟΎΠΕΣ",
    "ΣΚΟΥΠΕΣ ΡΟΜΠΟΤ", "Σκούπες Stick", "Ηλεκτρικές Σκούπες",
    "Σκούπες Ρομπότ",
}

# (slot_num, role_label, logic_key)
FLOOR_CARE_SLOTS = [
    (1,  'Αναλώσιμο',              'CONSUMABLE_MATCH'),
    (2,  'Συντήρηση',              'MAINTENANCE_MATCH'),
    (3,  'Σκουπάκι',               'HANDHELD'),
    (4,  'Σκουπάκι 2',             'HANDHELD_2'),
    (5,  'Σκουπάκι 3',             'HANDHELD_3'),
    (6,  'Ατμοκαθαριστής',         'STEAM_CLEANER'),
    (7,  'Ατμοκαθαριστής 2',       'STEAM_CLEANER_2'),
    (8,  'Σκούπα Στάχτης',         'ASH_VACUUM'),
    (9,  'Pet / Εξάρτημα',         'PET_SPECIALTY'),
    (10, 'Pet / Εξάρτημα 2',       'PET_SPECIALTY_2'),
]

FLOOR_CARE_MARKETING_COPY = {
    "Αναλώσιμο": "Σωστή σακούλα ή φίλτρο = μέγιστη απόδοση.",
    "Συντήρηση": "Εξαρτήματα που παρατείνουν τη ζωή της σκούπας.",
    "Σκουπάκι": "Γρήγορος καθαρισμός σε κάθε γωνιά.",
    "Σκουπάκι 2": "Ένα ακόμα χεράκι για καθαριότητα.",
    "Σκουπάκι 3": "Ιδανικό για αυτοκίνητο ή γραφείο.",
    "Ατμοκαθαριστής": "Βαθύς καθαρισμός χωρίς χημικά.",
    "Ατμοκαθαριστής 2": "Απολύμανση με τη δύναμη του ατμού.",
    "Σκούπα Στάχτης": "Τζάκι, ψησταριά, πέλετ — πάντα καθαρά.",
    "Pet / Εξάρτημα": "Ειδικά σχεδιασμένο για κατοικίδια.",
    "Pet / Εξάρτημα 2": "Εργαλεία για τρίχες & αλλεργιογόνα.",
}

# ── Peripheral trigger detection (used by product selector AND engine) ──
PERIPHERAL_TRIGGERS = {
    "Mouse":           {"hierarchies": {"MOUSE WIRELESS", "MOUSE WIRED", "APPLE ORIGINAL WIRELESS MOUSE"}},
    "Keyboard":        {"hierarchies": {"KEYBOARDS WIRELESS", "KEYBOARDS WIRED", "APPLE ORIGINAL WIRELESS KEYBOARD"}},
    "Gaming Mouse":    {"hierarchies": {"GAMING MOUSE"}},
    "Gaming Keyboard": {"hierarchies": {"GAMING KEYBOARDS"}},
}

# ── Stationery cluster keys (forward ref — full config in engine section) ──
STATIONERY_CLUSTERS = {
    "Pens", "Pencils", "Markers", "Sharpeners", "Erasers", "Correction",
    "Pencil Cases", "Geometric Tools", "Stationery Sets", "Paints",
    "Brushes", "Colored Pencils Art", "Drawing Markers", "Art Paper",
    "Notebooks", "Notepads",
}

STATIONERY_TRIGGERS = {
    "Pens":              {"hierarchies": {"ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ", "ΣΤΥΛΟ GEL", "ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ"}},
    "Pencils":           {"hierarchies": {"ΜΟΛΥΒΙΑ", "ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ"}},
    "Markers":           {"hierarchies": {"ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ", "ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ", "ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ", "ΜΑΡΚΑΔΟΡΟΙ"}},
    "Sharpeners":        {"hierarchies": {"ΞΥΣΤΡΕΣ"}},
    "Erasers":           {"hierarchies": {"ΓΟΜΕΣ"}},
    "Correction":        {"hierarchies": {"ΔΙΟΡΘΩΤΙΚΑ"}},
    "Pencil Cases":      {"hierarchies": {"ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ", "ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ", "ΜΟΛΥΒΟΘΗΚΕΣ"}},
    "Geometric Tools":   {"hierarchies": {"ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ", "ΟΡΓΑΝΑ ΣΧΕΔΙΑΣΗΣ", "ΟΡΓΑΝΑ ΜΕΤΡΗΣΗΣ"}},
    "Stationery Sets":   {"hierarchies": {"ΣΕΤ ΧΑΡΤΙΚΩΝ"}},
    "Paints":            {"hierarchies": {"ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ"}},
    "Brushes":           {"hierarchies": {"ΠΙΝΕΛΑ"}},
    "Colored Pencils Art": {"hierarchies": {"ΞΥΛΟΜΠΟΓΙΕΣ", "ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ"}},
    "Drawing Markers":   {"hierarchies": {"ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ"}},
    "Art Paper":         {"hierarchies": {"ΜΠΛΟΚ-ΧΑΡΤΙΑ", "ΧΑΡΤΙΑ - ΜΠΛΟΚ", "ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ"}},
    "Notebooks":         {"hierarchies": {"ΣΗΜΕΙΩΜΑΤΑΡΙΑ"}},
    "Notepads":          {"hierarchies": {"ΤΕΤΡΑΔΙΑ", "ΗΜΕΡΟΛΟΓΙΑ", "ORGANISER"}},
}# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS CONFIGURATION
# ─────────────────────────────────────────────────────────────
KIDS_BOOKS_LEVEL2 = {"Greek Kids Books", "International Kids Books"}

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

TOY_HIERARCHIES_ACTUAL = {
    "plush": ["ΛΟΥΤΡΙΝΑ", "ΛΟΥΤΡΙΝΑ ΜΠΡΕΛΟΚ"],
    "dolls": ["ΚΟΥΚΛΕΣ"],
    "action_figures": ["ACTION FIGURES", "ΣΥΛΛΕΚΤΙΚΕΣ ΦΙΓΟΥΡΕΣ", "FUNKO POP!"],
    "board_puzzles": ["ΟΙΚΟΓΕΝΕΙΑΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΠΑΙΔΙΚΑ PUZZLES", "CARD GAMES", "ΠΑΙΔΙΚΑ ΕΠΙΤΡΑΠΕΖΙΑ", "ΕΝΗΛΙΚΩΝ 1000+", "ΕΝΗΛΙΚΩΝ ΕΩΣ 999"],
    "building": ["ΚΑΤΑΣΚΕΥΕΣ", "ΜΙΚΡΟΚΟΣΜΟΣ"],
    "toddler": ["ΒΡΕΦΙΚΑ ΠΑΙΧΝΙΔΙΑ ΔΡΑΣΤΗΡΙΟΤΗΤΩΝ", "ΦΙΓΟΥΡΕΣ & PLAYSET", "Ζωάκια"],
    "vehicles": ["ΔΙΑΦΟΡΑ ΑΥΤΟΚΙΝΗΤΑ", "ΑΥΤΟΚΙΝΗΤΑ"],
    "creative": ["ΖΩΓΡΑΦΙΚΗ", "ΠΛΑΣΤΕΛΙΝΕΣ", "ΧΕΙΡΟΤΕΧΝΙΕΣ"],
    "collectable_cards": ["Collectable Cards"],  
    "knowledge_games": ["ΓΝΩΣΕΩΝ"],  
    "adult_board": ["ΕΠΙΤΡΑΠΕΖΙΑ ΕΝΗΛΙΚΩΝ"],  
    "beauty_fashion": ["ΟΜΟΡΦΙΑΣ", "ΔΡΑΣΤΗΡΙΟΤΗΤΕΣ ΓΙΑ ΚΟΡΙΤΣΙΑ"],  
    "lamps_decor": ["LAMPS"],  
}

STATIONERY_HIERARCHIES_ACTUAL = {
    "notebooks": ["ΣΗΜΕΙΩΜΑΤΑΡΙΑ", "ΤΕΤΡΑΔΙΑ"],
    "water_bottles": ["ΘΕΡΜΟΣ - ΠΑΓΟΥΡΙΑ", "ΠΑΓΟΥΡΙΑ", "ΘΕΡΜΟΣ"],
    "arts_crafts": ["ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ", "ΜΠΛΟΚ-ΧΑΡΤΙΑ", "ΚΑΣΕΤΙΝΕΣ", "ΜΑΡΚΑΔΟΡΟΙ", "ΜΑΡΚΑΔΟΡΟΙ ΣΧΕΔΙΟΥ-ΕΙΔΙΚΩΝ ΧΡΗΣΕΩΝ", "ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ"],
    "reading": ["READING ACCESSORIES"],
    "writing": ["ΜΟΛΥΒΙΑ", "ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ", "ΣΤΥΛΟ GEL"],
    "keychains": ["ΜΠΡΕΛΟΚ", "ΜΑΓΝΗΤΑΚΙΑ"],
    "cups": ["ΚΟΥΠΕΣ &  ΠΟΤΗΡΙΑ", "ΚΟΥΠΕΣ & ΠΟΤΗΡΙΑ"],
    "bags": ["ΤΣΑΝΤΑΚΙΑ - ΠΟΡΤΟΦΟΛΙΑ", "ΤΣΑΝΤΕΣ LIFESTYLE", "SHOPPING BAGS"],
    "food_containers": ["ΦΑΓΗΤΟΔΟΧΕΙΑ", "ΤΣΑΝΤΕΣ ΦΑΓΗΤΟΥ"],
    "stickers": ["ΑΥΤΟΚΟΛΛΗΤΑ-STICKERS"],
    "gift_gadgets": ["GIFT GADGETS"],
}

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
    if "-" in age:
        match = re.search(r'(\d+)', age)
        if match: return float(match.group(1))
    return 5.0

def is_valid_series(series_val) -> bool:
    if series_val is None or pd.isna(series_val): return False
    s = str(series_val).strip()
    if s.lower() in ['', '0', 'nan', 'n/a', 'none']: return False
    return True

def normalize_ip_name(name: str) -> str:
    return str(name).strip().lower().replace('-', ' ').replace('_', ' ')

def get_rotated_selection(df: pd.DataFrame, trigger_material: str, slot_type: str, n: int = 1) -> pd.DataFrame:
    if df.empty: return df.head(0)
    sorted_df = df.sort_values('Final_Score', ascending=False).reset_index(drop=True)
    if len(sorted_df) <= n: return sorted_df.head(n)
    
    hash_input = f"{trigger_material}_{slot_type}"
    hash_value = hash(hash_input)
    top_candidates = min(10, len(sorted_df))
    candidates = sorted_df.head(top_candidates)
    
    offset = abs(hash_value) % top_candidates
    selected_indices = [(offset + i) % top_candidates for i in range(min(n, top_candidates))]
    return candidates.iloc[selected_indices]

def ip_matches(series_name: str, brand: str, heroes: str) -> bool:
    if not is_valid_series(series_name): return False
    series_norm = normalize_ip_name(series_name)
    brand_norm = normalize_ip_name(brand)
    heroes_norm = normalize_ip_name(heroes)
    
    if series_norm in brand_norm or brand_norm in series_norm: return True
    if series_norm in heroes_norm or heroes_norm in series_norm: return True
    
    mappings = {
        'harry potter': ['harry potter'], 'peppa pig': ['peppa pig', 'peppa'],
        'bluey': ['bluey'], 'spiderman': ['spiderman', 'spider-man', 'spider man', 'spidey'],
        'frozen': ['frozen', 'elsa', 'anna'], 'disney': ['disney', 'mickey', 'minnie'],
        'barbie': ['barbie'], 'marvel': ['marvel', 'avengers', 'hulk', 'iron man', 'captain america'],
        'μικροί κύριοι': ['μικροί κύριοι', 'mr. men', 'little miss'],
    }
    
    for key, variants in mappings.items():
        if any(v in series_norm for v in variants):
            if any(v in brand_norm or v in heroes_norm for v in variants): return True
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
    'black titanium': ['μαύρο', 'black'], 'natural titanium': ['μπεζ', 'natural'],
    'white titanium': ['λευκό', 'white'], 'blue titanium': ['μπλε', 'blue'],
    'space black': ['μαύρο', 'black'], 'silver': ['ασημί', 'silver', 'γκρι'],
    'gold': ['χρυσό', 'gold', 'μπεζ'], 'starlight': ['λευκό', 'μπεζ'],
    'midnight': ['μαύρο', 'black'], 'white': ['λευκό', 'white', 'άσπρο'],
    'black': ['μαύρο', 'black'], 'blue': ['μπλε', 'blue', 'γαλάζιο'],
    'red': ['κόκκινο', 'red'], 'green': ['πράσινο', 'green'],
    'pink': ['ροζ', 'pink'], 'purple': ['μωβ', 'purple'],
    'gray': ['γκρι', 'gray', 'grey'], 'silver shadow': ['ασημί', 'silver', 'γκρι'],
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

# ═════════════════════════════════════════════════════════════
# 🟢 LAPTOPS HELPERS
# ═════════════════════════════════════════════════════════════

 
def parse_screen_size(val):
    """Parse screen size string to float inches. E.g. '15.6"' -> 15.6"""
    s = str(val).strip()
    if not s or s.lower() == 'nan': return 0.0
    s = s.replace(',', '.').replace('"', '').replace("''", '').replace('inch', '').replace('ίντσες', '')
    m = re.search(r'(\d+\.?\d*)', s)
    return float(m.group(1)) if m else 0.0
 
def extract_wattage_from_text(text):
    """Extract wattage number from title/field like '65W Charger'."""
    s = str(text).lower()
    m = re.search(r'(\d+)\s*w(?:att)?\b', s)
    return int(m.group(1)) if m else 0

def get_resolution_tier(res_str):
    """Maps screen resolution text to a numeric tier for easy comparison."""
    s = str(res_str).lower()
    if not s or s == 'nan': return 0
    
    # Tier 4: 4K / 5K / UHD
    if any(x in s for x in ['5k', '4k', 'uhd', 'ultra hd']): return 4
    # Tier 3: QHD / 2K
    if any(x in s for x in ['qhd', 'quad hd', 'wqxga']): return 3
    # Tier 2: FHD / 1080p
    if any(x in s for x in ['fhd', 'full hd', 'wuxga', '1080']): return 2
    # Tier 1: HD / <1080p
    if any(x in s for x in ['hd', 'sxga', '720']): return 1
    
    return 0

# ─────────────────────────────────────────────────────────────
# 🟢 LAPTOP TIER & BUDGET LOGIC (2026 Greek Market — Performance Pairing)
# ─────────────────────────────────────────────────────────────
# Tier 1: Budget & Entry-Level         (€350 – €699)
# Tier 2: Mid-Range & "AI-Ready"       (€700 – €1,199)
# Tier 3: High-End & Professional      (€1,200 – €2,499)
# Tier 4: Extreme Gaming & Workstations(€2,500 – €5,500+)

def get_laptop_tier(price):
    """Returns 1-4 segmentation tier for a laptop price (2026 GR market)."""
    if price >= 2500: return 4
    if price >= 1200: return 3
    if price >= 700:  return 2
    if price >= 350:  return 1
    return 0  # Below entry-level — no tier logic applied

# 20% Rule Breakdown — (min_€, max_€) sweet-spot per accessory per tier.
# Items inside the range get a strong boost; items outside still allowed
# but unboosted (so we don't fail-empty on sparse catalog).
ACCESSORY_BUDGET_TABLE = {
    # Scales heavily with laptop price (10–15% of setup cost)
    'MONITOR':  {1: (60, 90),   2: (120, 160), 3: (250, 320), 4: (500, 700)},
    # Scales moderately — diminishing returns above €80
    'MOUSE':    {1: (15, 25),   2: (35, 50),   3: (60, 90),   4: (100, 160)},
    'KEYBOARD': {1: (15, 25),   2: (25, 40),   3: (50, 80),   4: (100, 160)},
    # Headset — capped at ~15% of laptop price
    'HEADSET':  {1: (20, 60),   2: (50, 120),  3: (100, 250), 4: (150, 400)},
    # FLAT RATE — does NOT scale with laptop price (anti price-gouging)
    'MOUSEPAD': {1: (5, 15),    2: (10, 20),   3: (15, 25),   4: (15, 25)},
    'BAG':      {1: (30, 60),   2: (30, 60),   3: (40, 70),   4: (50, 80)},
    'SLEEVE':   {1: (15, 35),   2: (20, 40),   3: (30, 55),   4: (40, 60)},
}

def get_accessory_budget(slot_role, tier):
    """Returns (min_€, max_€) sweet-spot. Returns (0, 999999) if no rule."""
    return ACCESSORY_BUDGET_TABLE.get(slot_role, {}).get(tier, (0.0, 999999.0))

# Cheap-Trap floor: For laptops ≥ €800, never recommend accessories under €30
# EXCEPT mousepads and cables (which legitimately cost less).
CHEAP_TRAP_LAPTOP_THRESHOLD = 800.0
CHEAP_TRAP_MIN_ACCESSORY_PRICE = 30.0
CHEAP_TRAP_EXEMPT_ROLES = {'MOUSEPAD'}  # Cables exempt by hierarchy match below

def apply_cheap_trap(pool, laptop_price, slot_role, price_col='_p'):
    """Removes accessories under €30 when laptop ≥ €800, except for exempt slots.
    Returns (filtered_pool, note_str_or_None)."""
    if laptop_price < CHEAP_TRAP_LAPTOP_THRESHOLD: return pool, None
    if slot_role in CHEAP_TRAP_EXEMPT_ROLES:      return pool, None
    if price_col not in pool.columns:             return pool, None
    b4 = len(pool)
    filtered = pool[pool[price_col] >= CHEAP_TRAP_MIN_ACCESSORY_PRICE]
    if filtered.empty: return pool, f"⚠ Cheap-trap would empty pool — kept all {b4}"
    return filtered, f"Cheap-trap (€{laptop_price:.0f} laptop): ≥€{CHEAP_TRAP_MIN_ACCESSORY_PRICE:.0f} only ({b4}→{len(filtered)})"


def filter_or_penalize(pool, keep_mask, label, penalty=150000):
    """Try to filter pool down to keep_mask. If that would empty, fall back to
    applying a penalty to the ~keep_mask items instead (so they can still appear
    if nothing else does, but anything better will beat them).
    Returns (new_pool, note_str).

    Pattern used by: monitor gaming/FHD exclusions, mouse/pad gaming filters,
    storage SSD-only filter — anywhere a "remove X" filter might empty the pool."""
    b4 = len(pool)
    kept = pool[keep_mask]
    if not kept.empty:
        return kept, f"{label}: filtered {b4}→{len(kept)}"
    # Would empty → keep pool but penalise the items we wanted to drop
    if keep_mask.all() or (~keep_mask).all():
        # Every item is either kept or every item is dropped — nothing to penalise
        return pool, f"⚠ {label}: all items on same side, no filter applied"
    pool = pool.copy()
    pool.loc[~keep_mask, 'Final_Score'] -= penalty
    return pool, f"⚠ {label}: would empty pool → penalised {int((~keep_mask).sum())} items (-{penalty//1000}k)"


# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
EXCEL_FILE = "Recommendations GitHub.xlsx"  

@st.cache_data(ttl=600)
def load_all_data():
    excel_file = pd.ExcelFile(EXCEL_FILE, engine='openpyxl')
    available_sheets = excel_file.sheet_names
    
    if 'Products' in available_sheets:
        dp = pd.read_excel(excel_file, sheet_name='Products')
        dp.columns = dp.columns.str.strip()
    else: dp = pd.DataFrame()
    
    if 'History' in available_sheets:
        dh = pd.read_excel(excel_file, sheet_name='History')
        dh.columns = dh.columns.str.strip()
    else: dh = pd.DataFrame()
    
    if 'Slot_Matrix' in available_sheets:
        ds = pd.read_excel(excel_file, sheet_name='Slot_Matrix')
        ds.columns = ds.columns.str.strip()
    else: ds = pd.DataFrame()
    
    if 'Books' in available_sheets:
        db = pd.read_excel(excel_file, sheet_name='Books')
        db.columns = db.columns.str.strip()
    else: db = pd.DataFrame()

    if 'Laptops' in available_sheets:
        dl = pd.read_excel(excel_file, sheet_name='Laptops')
        dl.columns = dl.columns.str.strip()
    else: dl = pd.DataFrame()

    if 'Vacuums' in available_sheets:
        dv = pd.read_excel(excel_file, sheet_name='Vacuums')
        dv.columns = dv.columns.str.strip()
    else: dv = pd.DataFrame()

    if 'Peripherals' in available_sheets:
        dper = pd.read_excel(excel_file, sheet_name='Peripherals')
        dper.columns = dper.columns.str.strip()
    else: dper = pd.DataFrame()

    if 'Stationery' in available_sheets:
        dstat = pd.read_excel(excel_file, sheet_name='Stationery')
        dstat.columns = dstat.columns.str.strip()
    else: dstat = pd.DataFrame()
    
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
    
    return dp, dh, ds, db, dl, dv, dper, dstat, available_sheets

try:
    df_products, df_history, df_slots, df_books, df_laptops, df_vacuums, df_peripherals, df_stationery, sheets_loaded = load_all_data()
    compat_cols_found = [c for c in COMPAT_COLS if c in df_products.columns]
except Exception as e:
    st.error(f"🚨 Error loading data: {e}")
    st.code(traceback.format_exc())
    st.stop()


# ═════════════════════════════════════════════════════════════
# 🟢 NEW SIDEBAR — 2-Level Navigation (Level 1 → Level 2)
# ═════════════════════════════════════════════════════════════
# Replaces the entire existing sidebar block from:
#   "# 🟢 SIDEBAR STYLING" 
# down through:
#   the trigger selection if/elif/elif chain
#
# This block also handles trigger selection internally (it sets `sel`
# and `trigger` variables that the rest of your app uses).
# ═════════════════════════════════════════════════════════════



# ───── Navigation state ─────
if 'nav_level' not in st.session_state:
    st.session_state.nav_level = 1   # 1 = L1 grid, 2 = L2 grid + selector
if 'selected_l1' not in st.session_state:
    st.session_state.selected_l1 = None
if 'active_cluster' not in st.session_state:
    st.session_state.active_cluster = None

# ───── Taxonomy: L1 → L2 mapping ─────
# To add a new cluster later, add it here AND ensure its engine is wired up below.
L1_CATEGORIES = [
    {
        "key": "Books",
        "label": "Βιβλία",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/%3E%3C/svg%3E",
    },
    {
        "key": "Telephony",
        "label": "Τηλεφωνία,\nTablets &\nWearables",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='2' width='14' height='20' rx='2' ry='2'/%3E%3Cline x1='12' y1='18' x2='12.01' y2='18'/%3E%3C/svg%3E",
    },
    {
        "key": "IT",
        "label": "Υπολογιστές\n& Περιφερειακά",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='4' width='20' height='12' rx='1' ry='1'/%3E%3Cline x1='6' y1='20' x2='18' y2='20'/%3E%3Cline x1='12' y1='16' x2='12' y2='20'/%3E%3C/svg%3E",
    },
    {
        "key": "Stationery",
        "label": "Χαρτικά\n& Ζωγραφική",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E",
    },
    {
        "key": "SDA",
        "label": "Μικρές\nΣυσκευές",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 2v8l4-2'/%3E%3Cpath d='M12 10l-4-2'/%3E%3Ccircle cx='12' cy='18' r='4'/%3E%3Cline x1='12' y1='10' x2='12' y2='14'/%3E%3C/svg%3E",
    },
]

L2_CHILDREN = {
    "Books":     [{"key": "Kids Books",  "label": "Παιδικά\nΒιβλία",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/%3E%3C/svg%3E"}],
    "Telephony": [{"key": "Smartphones", "label": "Smart-\nphones",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='5' y='2' width='14' height='20' rx='2' ry='2'/%3E%3Cline x1='12' y1='18' x2='12.01' y2='18'/%3E%3C/svg%3E"}],
    "IT":        [{"key": "Laptops",     "label": "Laptops",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='4' width='20' height='12' rx='1' ry='1'/%3E%3Cline x1='6' y1='20' x2='18' y2='20'/%3E%3Cline x1='12' y1='16' x2='12' y2='20'/%3E%3C/svg%3E"},
                  {"key": "Mouse",      "label": "Mouse",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='6' y='3' width='12' height='18' rx='6'/%3E%3Cline x1='12' y1='7' x2='12' y2='11'/%3E%3C/svg%3E"},
                  {"key": "Keyboard",   "label": "Keyboard",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='6' width='20' height='12' rx='2'/%3E%3Cline x1='6' y1='10' x2='6.01' y2='10'/%3E%3Cline x1='10' y1='10' x2='10.01' y2='10'/%3E%3Cline x1='14' y1='10' x2='14.01' y2='10'/%3E%3Cline x1='18' y1='10' x2='18.01' y2='10'/%3E%3Cline x1='8' y1='14' x2='16' y2='14'/%3E%3C/svg%3E"},
                  {"key": "Gaming Mouse", "label": "Gaming\nMouse",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='6' y='3' width='12' height='18' rx='6'/%3E%3Cline x1='12' y1='7' x2='12' y2='11'/%3E%3Cpath d='M6 12h12'/%3E%3C/svg%3E"},
                  {"key": "Gaming Keyboard", "label": "Gaming\nKeyboard",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='6' width='20' height='12' rx='2'/%3E%3Cline x1='6' y1='10' x2='6.01' y2='10'/%3E%3Cline x1='10' y1='10' x2='10.01' y2='10'/%3E%3Cline x1='14' y1='10' x2='14.01' y2='10'/%3E%3Cline x1='18' y1='10' x2='18.01' y2='10'/%3E%3Cpath d='M6 12h12'/%3E%3Cline x1='8' y1='14' x2='16' y2='14'/%3E%3C/svg%3E"},
                  {"key": "Monitors",     "label": "Οθόνες",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='3' width='20' height='14' rx='2'/%3E%3Cline x1='8' y1='21' x2='16' y2='21'/%3E%3Cline x1='12' y1='17' x2='12' y2='21'/%3E%3C/svg%3E"},
                  {"key": "Printers",     "label": "Εκτυπωτές",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9V2h12v7'/%3E%3Crect x='6' y='14' width='12' height='8'/%3E%3Cpath d='M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2'/%3E%3C/svg%3E"},
                  {"key": "Webcam",       "label": "Webcam",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='10' r='7'/%3E%3Ccircle cx='12' cy='10' r='3'/%3E%3Cline x1='12' y1='17' x2='12' y2='21'/%3E%3Cline x1='8' y1='21' x2='16' y2='21'/%3E%3C/svg%3E"},
                  {"key": "USB Hub",      "label": "USB Hub",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='8' width='16' height='8' rx='2'/%3E%3Cline x1='8' y1='12' x2='8.01' y2='12'/%3E%3Cline x1='12' y1='12' x2='12.01' y2='12'/%3E%3Cline x1='16' y1='12' x2='16.01' y2='12'/%3E%3C/svg%3E"},
                 ],
    "Stationery": [
                  {"key": "Pens",           "label": "Στυλό",        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Pencils",        "label": "Μολύβια",     "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Markers",        "label": "Μαρκαδόροι",  "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Sharpeners",     "label": "Ξύστρες",     "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Erasers",        "label": "Γόμες",       "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Correction",     "label": "Διορθωτικά",  "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Pencil Cases",   "label": "Κασετίνες",   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Geometric Tools","label": "Γεωμετρικά",  "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Stationery Sets","label": "Σετ\nΧαρτικών","icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Paints",         "label": "Χρώματα",     "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M18.37 2.63a2 2 0 0 1 3 3L14 13l-4 1 1-4 7.37-7.37z'/%3E%3Cpath d='M9 14.5a4 4 0 0 1-4 4H3v-2a4 4 0 0 1 4-4'/%3E%3C/svg%3E"},
                  {"key": "Brushes",        "label": "Πινέλα",      "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M18.37 2.63a2 2 0 0 1 3 3L14 13l-4 1 1-4 7.37-7.37z'/%3E%3Cpath d='M9 14.5a4 4 0 0 1-4 4H3v-2a4 4 0 0 1 4-4'/%3E%3C/svg%3E"},
                  {"key": "Colored Pencils Art","label": "Ξυλομπογιές", "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M18.37 2.63a2 2 0 0 1 3 3L14 13l-4 1 1-4 7.37-7.37z'/%3E%3Cpath d='M9 14.5a4 4 0 0 1-4 4H3v-2a4 4 0 0 1 4-4'/%3E%3C/svg%3E"},
                  {"key": "Drawing Markers","label": "Μαρκαδόροι\nΖωγρ.", "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M18.37 2.63a2 2 0 0 1 3 3L14 13l-4 1 1-4 7.37-7.37z'/%3E%3Cpath d='M9 14.5a4 4 0 0 1-4 4H3v-2a4 4 0 0 1 4-4'/%3E%3C/svg%3E"},
                  {"key": "Art Paper",      "label": "Μπλοκ\nΧαρτιά",   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M18.37 2.63a2 2 0 0 1 3 3L14 13l-4 1 1-4 7.37-7.37z'/%3E%3Cpath d='M9 14.5a4 4 0 0 1-4 4H3v-2a4 4 0 0 1 4-4'/%3E%3C/svg%3E"},
                  {"key": "Notebooks",      "label": "Τετράδια",    "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Notepads",       "label": "Σημειωμ.",    "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                 ],
    "SDA":       [{"key": "Floor Care", "label": "Σκούπες",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 2v8l4-2'/%3E%3Cpath d='M12 10l-4-2'/%3E%3Ccircle cx='12' cy='18' r='4'/%3E%3Cline x1='12' y1='10' x2='12' y2='14'/%3E%3C/svg%3E"}],
}

# Reverse: L2 key → parent L1 key (used to highlight which L2 is active)
L2_TO_L1 = {child["key"]: l1 for l1, children in L2_CHILDREN.items() for child in children}

# ───── Sidebar base styling ─────
st.sidebar.markdown("""
<style>
    [data-testid="stSidebar"] > div:first-child { background-color: #f5f5f5 !important; }
    [data-testid="stSidebar"] { background-color: #f5f5f5 !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    /* Hide Streamlit's default sidebar page nav and resize handle */
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebarNavItems"] { display: none !important; }
    [data-testid="stSidebarNavSeparator"] { display: none !important; }
    [data-testid="stSidebarResizeHandle"] { display: none !important; }
    /* Kill any remaining tall vertical strip in sidebar */
    [data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child > nav { display: none !important; }
    [data-testid="stSidebar"] nav { display: none !important; }

    .sidebar-header {
        background-color: #ff5e00; color: white; padding: 18px 20px;
        margin-left: -1rem; margin-right: -1rem; margin-top: -1rem; margin-bottom: 10px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 18px; font-weight: 700;
        display: flex; align-items: center; justify-content: space-between;
        box-sizing: border-box;
    }
    .sidebar-close-btn {
        background: transparent; border: none; color: white; font-size: 22px;
        font-weight: 300; cursor: pointer; padding: 5px 10px; line-height: 1; border-radius: 4px;
    }
    .sidebar-close-btn:hover { background: rgba(255,255,255,0.2); }

    [data-testid="stSidebar"] .block-container { padding-top: 0 !important; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] { gap: 0.3rem !important; }

    /* Tile buttons (L1 and L2 grids) */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
        background: #ffffff !important;
        border: 1px solid #eaeaea !important;
        border-radius: 12px !important;
        padding: 55px 6px 12px 6px !important;
        min-height: 105px !important;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-size: 11px !important; font-weight: 600 !important; color: #333 !important;
        white-space: pre-line !important; line-height: 1.3 !important;
        box-shadow: none !important;
        position: relative !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button:hover {
        border-color: #ff5e00 !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
        transform: translateY(-1px);
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button p {
        font-size: 11px !important; margin-top: 2px !important;
    }

    .section-divider { border: none; border-top: 1px solid #e0e0e0; margin: 8px 0 4px 0; }
    .sidebar-section {
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 11px; font-weight: 700; color: #888;
        text-transform: uppercase; letter-spacing: 0.5px; margin: 8px 0 4px 0;
    }

    /* Back button dot (L2 view) */
    .l2-back-dot {
        display: inline-flex; align-items: center; justify-content: center;
        width: 32px; height: 32px; min-width: 32px;
        border-radius: 50%;
        background: #ffffff;
        border: 1px solid #eaeaea;
        font-size: 18px; font-weight: 300; color: #333;
        cursor: pointer; flex-shrink: 0;
        transition: all 0.15s ease;
        line-height: 1;
    }
    .l2-back-dot:hover { border-color: #ff5e00; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .l2-breadcrumb-label {
        font-size: 15px; font-weight: 700; color: #111;
        line-height: 1.2; cursor: default;
    }
    /* Style the back button as a subtle pill */
    [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {
        /* Default: keep normal tile styling (handled by other rules) */
    }
</style>
""", unsafe_allow_html=True)

# Header with close button
st.sidebar.markdown('''
<div class="sidebar-header">
    <span>Μενού</span>
    <button class="sidebar-close-btn" onclick="window.parent.document.querySelector('[data-testid=\\'stSidebarCollapsedControl\\'] button').click();" title="Κλείσιμο">✕</button>
</div>
''', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# LEVEL 1 VIEW — Show top-level category tiles
# ─────────────────────────────────────────────────────────────
if st.session_state.nav_level == 1:
    st.sidebar.markdown('<p class="sidebar-section">Προϊόντα</p>', unsafe_allow_html=True)

    # Render dynamic icon CSS for each L1 column position
    icon_css = "<style>"
    for i, l1 in enumerate(L1_CATEGORIES, start=1):
        icon_css += f"""
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:nth-child({i}) button::before {{
            content: ''; display: block; width: 32px; height: 32px;
            background-image: url("data:image/svg+xml,{l1['icon_svg']}");
            background-size: contain; background-repeat: no-repeat; background-position: center;
            position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
        }}
        """
    icon_css += "</style>"
    st.sidebar.markdown(icon_css, unsafe_allow_html=True)

    # 2-column grid (3 categories: 2 in row 1, 1 in row 2... or use columns dynamically)
    # We'll show pairs of 2 to match the screenshot
    n_l1 = len(L1_CATEGORIES)
    for row_start in range(0, n_l1, 2):
        row_items = L1_CATEGORIES[row_start:row_start + 2]
        cols = st.sidebar.columns(2)
        for col, l1 in zip(cols, row_items):
            with col:
                if st.button(l1["label"], key=f"l1_{l1['key']}", use_container_width=True):
                    st.session_state.nav_level = 2
                    st.session_state.selected_l1 = l1["key"]
                    # Auto-select the first L2 child if there's only one
                    children = L2_CHILDREN.get(l1["key"], [])
                    if len(children) == 1:
                        st.session_state.active_cluster = children[0]["key"]
                    else:
                        st.session_state.active_cluster = None
                    st.rerun()

    # No active cluster yet → stop here, nothing to recommend
    sel = None
    trigger = None


# ─────────────────────────────────────────────────────────────
# LEVEL 2 VIEW — Show L2 tiles + product selector + trigger card
# ─────────────────────────────────────────────────────────────
else:
    selected_l1_key = st.session_state.selected_l1
    selected_l1 = next((x for x in L1_CATEGORIES if x["key"] == selected_l1_key), None)
    children = L2_CHILDREN.get(selected_l1_key, [])

    # Breadcrumb row: ‹ back arrow + parent label
    # Rendered as label first, then a small back button — avoiding st.columns
    # which created a tall vertical strip for the narrow back column.
    label_clean = (selected_l1["label"] if selected_l1 else "").replace("\n", " ")
    st.sidebar.markdown(f'<div class="l2-breadcrumb-label" style="margin-bottom:6px;">‹&nbsp;&nbsp;{label_clean}</div>', unsafe_allow_html=True)
    if st.sidebar.button("↩ Πίσω", key="back_to_l1", use_container_width=True):
        st.session_state.nav_level = 1
        st.session_state.selected_l1 = None
        st.session_state.active_cluster = None
        st.rerun()

    # L2 tiles — render after the breadcrumb (in their own horizontal block)
    st.sidebar.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Active border CSS for L2 tiles
    active_cluster = st.session_state.active_cluster
    border_css = "<style>"
    for i, child in enumerate(children, start=1):
        border = "2px solid #ff5e00" if child["key"] == active_cluster else "1px solid #eaeaea"
        border_css += f"""
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child({i}) button {{
            border: {border} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:not(:first-of-type) > div:nth-child({i}) button::before {{
            content: ''; display: block; width: 32px; height: 32px;
            background-image: url("data:image/svg+xml,{child['icon_svg']}");
            background-size: contain; background-repeat: no-repeat; background-position: center;
            position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
        }}
        """
    border_css += "</style>"
    st.sidebar.markdown(border_css, unsafe_allow_html=True)

    # Render L2 tiles in pairs
    n_l2 = len(children)
    for row_start in range(0, n_l2, 2):
        row_items = children[row_start:row_start + 2]
        # Pad to 2 columns for consistent layout
        if len(row_items) == 1:
            cols = st.sidebar.columns(2)
            with cols[0]:
                child = row_items[0]
                if st.button(child["label"], key=f"l2_{child['key']}", use_container_width=True):
                    st.session_state.active_cluster = child["key"]
                    st.rerun()
            # cols[1] left empty
        else:
            cols = st.sidebar.columns(2)
            for col, child in zip(cols, row_items):
                with col:
                    if st.button(child["label"], key=f"l2_{child['key']}", use_container_width=True):
                        st.session_state.active_cluster = child["key"]
                        st.rerun()

    st.sidebar.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# ───── Product selector + trigger setup based on active_cluster ─────
    sel = None
    trigger = None
    active_cluster = st.session_state.active_cluster

    if active_cluster == "Smartphones":
        if df_products.empty: st.stop()
        phones = df_products[(df_products['Level 2']=='Mobiles') & (df_products['Hierarchy']=='Smartphones')]
        if phones.empty: phones = df_products[df_products['Level 2']=='Mobiles']
        if not phones.empty:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Smartphone</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", phones['Title'].unique(), label_visibility="collapsed", key="sm_sel")
            trigger = phones[phones['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Laptops":
        if df_laptops.empty:
            st.sidebar.warning("Sheet 'Laptops' is empty or missing.")
        else:
            laptops = df_laptops[(df_laptops['Level 1']=='IT') & (df_laptops['Level 2'].isin(LAPTOP_L2_VALUES))]
            if laptops.empty:
                # Fallback: hierarchy-based
                laptops = df_laptops[df_laptops['Hierarchy'].fillna('').astype(str).str.upper().str.contains('NOTEBOOK|LAPTOP', regex=True, na=False)]
            
            # ─────────────────────────────────────────────────────────────
            # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
            # ─────────────────────────────────────────────────────────────
            laptop_test_skus = {
                "2032853", "2077374", "2114170", "2106436", "2076615", 
                "1950043", "1950030", "1993377", "2056517", "1993362"
            }
            if not laptops.empty:
                laptops = laptops[laptops['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(laptop_test_skus)]
            # ─────────────────────────────────────────────────────────────

            if laptops.empty:
                st.sidebar.warning("Δεν βρέθηκαν test Laptops.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Laptop</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", laptops['Title'].unique(), label_visibility="collapsed", key="lt_sel")
                trigger = laptops[laptops['Title']==sel].iloc[0] if sel else Non


    elif active_cluster == "Floor Care":
        if df_vacuums.empty:
            st.sidebar.warning("Sheet 'Vacuums' is empty or missing.")
        else:
            hier_upper = df_vacuums['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
            trigger_hiers_upper = {h.upper().strip() for h in FLOOR_CARE_TRIGGER_HIERARCHIES}
            vacuums = df_vacuums[hier_upper.isin(trigger_hiers_upper)].copy()
            if vacuums.empty:
                # Fallback: all rows in Vacuums sheet
                vacuums = df_vacuums.copy()
            if vacuums.empty:
                st.sidebar.warning("Δεν βρέθηκαν σκούπες.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Σκούπα</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", vacuums['Title'].unique(), label_visibility="collapsed", key="fc_sel")
                trigger = vacuums[vacuums['Title']==sel].iloc[0] if sel else None

    elif active_cluster in ("Mouse", "Keyboard", "Gaming Mouse", "Gaming Keyboard"):
        if df_peripherals.empty:
            st.sidebar.warning("Sheet 'Peripherals' is empty or missing.")
        else:
            pconfig = PERIPHERAL_TRIGGERS.get(active_cluster, {})
            p_hiers = {h.upper().strip() for h in pconfig.get('hierarchies', set())}
            periph = df_peripherals[df_peripherals['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(p_hiers)].copy()
            
            
            # ─────────────────────────────────────────────────────────────
            # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
            # ─────────────────────────────────────────────────────────────
            if active_cluster in ("Mouse", "Keyboard", "Gaming Mouse", "Gaming Keyboard"):
                target_skus = {
                    "1148597", "1200734", "1986598", "2092896", "1533714", 
                    "2064103", "1736727", "1576681", "1974266", "1981199", 
                    "1334843", "1334845", "1566188", "1571956", "1574806", 
                    "1585918", "1611810", "1646794", "1646827", "1663975",
                    "1696998", "1539766", "2084471", "1534473", "1867024",
                    "1600373", "1950837", "1839249", "1825285", "1841438", 
                    "1794589", "1841439", "2057552", "1906214"
                }
                periph = periph[periph['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(target_skus)]
            # ─────────────────────────────────────────────────────────────

            if periph.empty:
                st.sidebar.warning(f"Δεν βρέθηκαν {active_cluster} products.")
            else:
                label = {"Mouse": "Ποντίκι", "Keyboard": "Πληκτρολόγιο", "Gaming Mouse": "Gaming Mouse", "Gaming Keyboard": "Gaming Keyboard"}.get(active_cluster, active_cluster)
                st.sidebar.markdown(f'<p class="sidebar-section">Επιλέξτε {label}</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", periph['Title'].unique(), label_visibility="collapsed", key=f"periph_{active_cluster}_sel")
                trigger = periph[periph['Title']==sel].iloc[0] if sel else None

    elif active_cluster in STATIONERY_CLUSTERS:
        if df_stationery.empty:
            st.sidebar.warning("Sheet 'Stationery' is empty or missing.")
        else:
            sconfig = STATIONERY_TRIGGERS.get(active_cluster, {})
            s_hiers = {h.upper().strip() for h in sconfig.get('hierarchies', set())}
            stat_pool = df_stationery[df_stationery['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(s_hiers)].copy()
            
            # ─────────────────────────────────────────────────────────────
            # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
            # ─────────────────────────────────────────────────────────────
            placeholder_skus = {
                "733204", "733203", "733226", "2109505", "733196", "733195", "733183",
                "1102646", "758573", "1161576", "2024990", "1687016", "1687019", "405936",
                "1818846", "2025218", "2025219", "1941157", "788651", "1157073", "1164848",
                "696004", "2041223", "696006", "2024461", "172707", "2024465", "1104407",
                "1616375", "1616374", "1382240", "1242141", "696013", "1686583", "776869",
                "1686595", "2040906", "2041343", "2041351", "1277684", "1687017", "1510441",
                "2093224", "1164356", "1104159", "1211061", "1211060", "1071635", "834696",
                "1201739", "1211053", "733263", "1249322", "733259", "1249324", "1249325",
                "1239333", "1378911", "1378914", "1248952", "2109506", "2109520", "2109518",
                "2109507", "2038650", "2038651", "1652983", "1652982", "1154599", "1573739",
                "1154597", "2025638", "1587061", "1920828", "827033", "1407299", "827032",
                "1244275", "1829342", "1537593", "1492203", "1492202", "1492201", "1656003",
                "1492200", "1309722", "2040968", "2040978", "2040965", "1600603", "1110711",
                "2044539", "2109501", "2109502", "1445716", "1958366", "2088012", "1958365",
                "2025197", "1710644"
            }
            test_filtered = stat_pool[stat_pool['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(placeholder_skus)]
            if not test_filtered.empty:
                stat_pool = test_filtered
            # ─────────────────────────────────────────────────────────────

            if stat_pool.empty:
                st.sidebar.warning(f"Δεν βρέθηκαν {active_cluster} products.")
            else:
                label = active_cluster
                st.sidebar.markdown(f'<p class="sidebar-section">Επιλέξτε {label}</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", stat_pool['Title'].unique(), label_visibility="collapsed", key=f"stat_{active_cluster}_sel")
                trigger = stat_pool[stat_pool['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Monitors":
        # Monitor triggers may be in Products sheet or Peripherals
        combined = pd.concat([df_products, df_peripherals], ignore_index=True) if not df_peripherals.empty else df_products
        monitors = combined[combined['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin({'TFT MONITOR', 'MONITORS'})].copy()
        if monitors.empty:
            monitors = combined[combined['Level 2'].fillna('').str.strip().str.lower().isin(['monitors', 'οθόνες'])].copy()
        if monitors.empty:
            st.sidebar.warning("Δεν βρέθηκαν οθόνες.")
        else:
            # ─────────────────────────────────────────────────────────────
            # 🧪 TEST LIST: Restrict the dropdown to specific Monitor SKUs
            # ─────────────────────────────────────────────────────────────
            monitor_test_skus = {
                "2096238", "1992012", "2076445", "2066078",
                "2093201", "1795955", "2024266"
            }
            monitors = monitors[monitors['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(monitor_test_skus)]
            # ─────────────────────────────────────────────────────────────
            if monitors.empty:
                st.sidebar.warning("Δεν βρέθηκαν test οθόνες.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Οθόνη</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", monitors['Title'].unique(), label_visibility="collapsed", key="mon_sel")
                trigger = monitors[monitors['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Printers":
        combined = pd.concat([df_products, df_peripherals], ignore_index=True) if not df_peripherals.empty else df_products
        printer_hiers = {'INKJET', 'MULTIFUNCTION INKJET', 'MULTIFUCTION LASER', 'LASER', 'LASER A4 MONO',
                         'LASER A4 COLOR', 'LASER A3 MONO', 'LASER A3 COLOR', 'FAX LASER',
                         'MULTIFUCTION LASER A4 COLOR', 'MULTIFUCTION LASER A4 MONO',
                         'MULTIFUCTION LASER A3 COLOR', 'MULTIFUCTION LASER A3 MONO'}
        printers = combined[combined['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(printer_hiers)].copy()
        if printers.empty:
            printers = combined[combined['Level 2'].fillna('').str.strip().str.lower().isin(['printers', 'εκτυπωτές'])].copy()
        if printers.empty:
            st.sidebar.warning("Δεν βρέθηκαν εκτυπωτές.")
        else:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Εκτυπωτή</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", printers['Title'].unique(), label_visibility="collapsed", key="print_sel")
            trigger = printers[printers['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Webcam":
        if df_peripherals.empty:
            st.sidebar.warning("Sheet 'Peripherals' is empty or missing.")
        else:
            webcams = df_peripherals[df_peripherals['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin({'PC WEB CAMS', 'WEB CAMS', 'NOTEBOOK WEB CAMS'})].copy()
            if webcams.empty:
                st.sidebar.warning("Δεν βρέθηκαν webcams.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Webcam</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", webcams['Title'].unique(), label_visibility="collapsed", key="wc_sel")
                trigger = webcams[webcams['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "USB Hub":
        if df_peripherals.empty:
            st.sidebar.warning("Sheet 'Peripherals' is empty or missing.")
        else:
            hubs = df_peripherals[df_peripherals['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin({'USB HUB DEVICES'})].copy()
            if hubs.empty:
                st.sidebar.warning("Δεν βρέθηκαν USB Hubs.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε USB Hub</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", hubs['Title'].unique(), label_visibility="collapsed", key="hub_sel")
                trigger = hubs[hubs['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Kids Books":
        if df_books.empty: st.stop()
        kids_books = df_books[(df_books['Level 1'] == 'Books') & (df_books['Level 2'].isin(KIDS_BOOKS_LEVEL2))]
        if kids_books.empty: kids_books = df_books[df_books['Level 1'] == 'Books']
        if not kids_books.empty:
            if 'Σειρά βιβλίου' in kids_books.columns:
                series_col = kids_books['Σειρά βιβλίου'].fillna('').astype(str)
                series_col = series_col[(series_col != '0') & (series_col != '') & (series_col.str.lower() != 'nan') & (series_col.str.lower() != 'n/a')]
                if len(series_col) > 0:
                    series_counts = series_col.value_counts()
                    top_series = series_counts.head(200)
                    series_items = [(f"{name} ({count})", name) for name, count in top_series.items()]

                    st.sidebar.markdown('<p class="sidebar-section">Φιλτράρισμα ανά Σειρά</p>', unsafe_allow_html=True)
                    series_search = st.sidebar.text_input("🔍 Αναζήτηση σειράς:", placeholder="π.χ. Harry Potter", label_visibility="collapsed", key="kb_search")
                    if series_search:
                        matching = [(f"{name} ({count})", name) for name, count in series_counts.items() if series_search.lower() in name.lower()][:100]
                        series_options = ['Όλες οι σειρές'] + [m[0] for m in matching]
                        series_display = {m[0]: m[1] for m in matching}
                    else:
                        series_options = ['Όλες οι σειρές'] + [item[0] for item in series_items]
                        series_display = {item[0]: item[1] for item in series_items}

                    selected_series_display = st.sidebar.selectbox("", series_options, label_visibility="collapsed", key="kb_series")
                    if selected_series_display != 'Όλες οι σειρές':
                        actual_series = series_display.get(selected_series_display, selected_series_display)
                        kids_books = kids_books[kids_books['Σειρά βιβλίου'] == actual_series]

            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Βιβλίο</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", kids_books['Title'].unique(), label_visibility="collapsed", key="kb_sel")
            if sel:
                matching_books = kids_books[kids_books['Title'] == sel].copy()
                if len(matching_books) > 1 and 'Σειρά βιβλίου' in matching_books.columns:
                    matching_books['_has_series'] = matching_books['Σειρά βιβλίου'].apply(lambda x: 0 if (pd.isna(x) or str(x).strip().lower() in ['', '0', 'nan']) else 1)
                    matching_books = matching_books.sort_values('_has_series', ascending=False)
                trigger = matching_books.iloc[0]


# ───── Compatibility shim: rest of app expects `active_cluster` as a string ─────
active_cluster = st.session_state.active_cluster or ""

# If we're at L1 view OR no cluster selected yet → show prompt and stop
if trigger is None:
    st.markdown("""
    <div style='margin-top:80px; padding:40px; background:#f8f9fa; border-radius:16px; text-align:center;'>
        <h2 style='color:#333; font-family:-apple-system,BlinkMacSystemFont,sans-serif; font-weight:700; margin-bottom:10px;'>
            Επίλεξε κατηγορία
        </h2>
        <p style='color:#666; font-size:14px;'>Πάτησε ένα εικονίδιο στο μενού αριστερά για να ξεκινήσεις.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ─────────────────────────────────────────────────────────────
# DISPLAY HEADER & SIDEBAR CARD
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    st.markdown('<div class="public-header">Επιλογές για εσένα</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Συμβατά αξεσουάρ για το <b>{sel}</b></p>", unsafe_allow_html=True)
elif active_cluster == "Laptops":
    st.markdown('<div class="public-header">Ολοκλήρωσε το setup σου</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Αξεσουάρ & εξοπλισμός για το <b>{sel}</b></p>", unsafe_allow_html=True)
else:
    st.markdown('<div class="public-header">Διάλεξε κι άλλα!</div>', unsafe_allow_html=True)
    st.markdown(f"<p style='color: #555; font-size: 14px; margin-top: -15px; margin-bottom: 25px;'>Προτάσεις με βάση το <b>{sel}</b></p>", unsafe_allow_html=True)

card_title = safe(str(trigger.get('Title', sel)))
card_sku = safe(str(trigger.get('Material', 'N/A')))
card_img = safe(str(trigger.get('Thumbnails', '')).strip())
if not card_img or card_img == 'nan': card_img = "https://via.placeholder.com/150?text=No+Image"
card_avail = safe(str(trigger.get('AVAILABILITY', 'Άμεσα Διαθέσιμο')))
avail_theme = "avail-blue" if card_avail in ["Κατόπιν Παραγγελίας", "Αναμένεται Σύντομα", "Διαθέσιμο με παραγγελία"] else "avail-green"

try: t_price = parse_euro_price(trigger.get('LIST PRICE', 0))
except: t_price = 0.0
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
    st.markdown("---")
    if st.button("🔄 Ανανέωση Δεδομένων", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────────────────────
# 🟢 KIDS BOOKS ENGINE (REWRITTEN FOR DYNAMIC ORDERING)
# ─────────────────────────────────────────────────────────────
def run_books_engine(trigger, df_all, df_history):
    diag = []
    slot_notes = {}
    all_recs = []
    used_materials = set()
    used_titles = set()
    
    # ══════════════════════════════════════════════════════════
    # 🟢 LOAD GENDER & ORDER CATEGORIES FROM FILE
    # ══════════════════════════════════════════════════════════
    SERIES_GENDER_MAP = {}
    SERIES_ORDER_MAP = {}
    try:
        import os
        gender_file_paths = [
            '/mnt/user-data/uploads/kids_books_categories.xlsx',
            'kids_books_categories.xlsx',
            '/mount/src/recommender-poc/kids_books_categories.xlsx',
        ]
        for gf_path in gender_file_paths:
            if os.path.exists(gf_path):
                gender_df = pd.read_excel(gf_path)
                for _, row in gender_df.iterrows():
                    series_name = str(row.get('Series Name', '')).strip()
                    category = str(row.get('Category', 'Universal')).strip()
                    
                    # Read Order logic from 3rd column
                    order_type = str(row.iloc[2]).strip() if len(row) > 2 else 'Standalone'
                    
                    if series_name:
                        series_lower = series_name.lower()
                        if category == 'Girls-leaning':
                            SERIES_GENDER_MAP[series_lower] = 'girl'
                        elif category == 'Boys-leaning':
                            SERIES_GENDER_MAP[series_lower] = 'boy'
                        else:
                            SERIES_GENDER_MAP[series_lower] = 'neutral'
                            
                        SERIES_ORDER_MAP[series_lower] = order_type
                break
    except Exception as e:
        pass 

    # 🟢 HARDCODED ORDER EXTRACTIONS
    HARRY_POTTER_ORDER = {
        'φιλοσοφική λίθος': 1, 'philosopher': 1, "sorcerer's stone": 1,
        'μυστικό δωμάτιο': 2, 'chamber of secrets': 2, 'κάμαρα': 2,
        'αιχμάλωτος': 3, 'αζκαμπάν': 3, 'prisoner of azkaban': 3,
        'κύπελλο φωτιάς': 4, 'goblet of fire': 4, 'κύπελλο της φωτιάς': 4,
        'τάγμα του φοίνικα': 5, 'order of the phoenix': 5, 'φοίνικα': 5,
        'ημίαιμος πρίγκιψ': 6, 'half-blood prince': 6, 'ημίαιμος': 6,
        'κλήροι του θανάτου': 7, 'deathly hallows': 7, 'θανάτου': 7,
        'καταραμένο παιδί': 8, 'cursed child': 8,
        'φανταστικά ζώα': 9, 'fantastic beasts': 9,
        'quidditch': 10, 'κουίντιτς': 10,
        'beedle': 11, 'μπιντλ': 11,
    }
    
    def get_hp_order(title):
        title_lower = str(title).lower()
        for keyword, order in HARRY_POTTER_ORDER.items():
            if keyword in title_lower: return order
        return 99 
    
    def is_harry_potter_series(series_name):
        series_lower = str(series_name).lower()
        return 'harry potter' in series_lower or 'χάρι πότερ' in series_lower or 'χαρι ποτερ' in series_lower

    def is_dog_man_series(series_name):
        return 'dog man' in str(series_name).lower()
    
    def get_dog_man_order(title):
        title_lower = str(title).lower()
        match = re.search(r'dog\s*man\s*(\d{1,2})(?:\s*[-:]|\s|$)', title_lower)
        if match: return int(match.group(1))
        if 'dog man' in title_lower and not re.search(r'dog\s*man\s*\d', title_lower):
            adv_match = re.search(r'adventures\s*of\s*dog\s*man\s*(\d)', title_lower)
            if adv_match: return int(adv_match.group(1))
            return 1
        known_titles = {
            'a tale of two kitties': 3, 'tale of two kitties': 3,
            'lord of the fleas': 5, 'brawl of the wild': 6,
            'for whom the ball rolls': 7, 'fetch-22': 8, 'fetch 22': 8,
            'grime and punishment': 9, 'mothering heights': 10,
            'twenty thousand fleas': 11, 'scarlet shedder': 12, 'big jim begins': 13,
        }
        for keyword, order in known_titles.items():
            if keyword in title_lower: return order
        return 99
    
    def is_mikroi_kyrioi_series(series_name):
        series_lower = str(series_name).lower()
        return 'μικροί κύριοι' in series_lower or 'μικρές κυρίες' in series_lower or 'mr. men' in series_lower or 'little miss' in series_lower
    
    def get_mikroi_kyrioi_order(title):
        title_lower = str(title).lower()
        match = re.search(r'(?:μικροί κύριοι|μικρές κυρίες|mr\.?\s*men|little miss)[^0-9]*(\d{1,3})', title_lower)
        if match: return int(match.group(1))
        return 99 

    def is_box_set(title):
        title_lower = str(title).lower()
        box_keywords = ['box set', 'boxset', 'box-set', 'κασετίνα', 'συλλογή', 'collection', 
                        'βαλιτσάκι', 'σετ βιβλίων', 'book set', 'complete series', 'books 1-']
        return any(kw in title_lower for kw in box_keywords)
    
    def is_complete_box_set(title):
        title_lower = str(title).lower()
        complete_keywords = ['complete', 'ολοκληρωμένη', 'πλήρης', 'all books', 'όλα τα βιβλία', 
                            'full collection', '1-7', '1-8', 'complete collection']
        return any(kw in title_lower for kw in complete_keywords)

    def get_canonical_book_name(title, orig_title=''):
        title_lower = str(title).lower().strip() if title and str(title) != 'nan' else ''
        orig_lower = ''
        if orig_title is not None and not pd.isna(orig_title):
            orig_str = str(orig_title).lower().strip()
            if orig_str and orig_str != 'nan':
                orig_lower = orig_str
        
        canonical = orig_lower if orig_lower else title_lower
        if not canonical or canonical == 'nan':
            return title_lower if title_lower and title_lower != 'nan' else ''
        
        prefixes = [
            'ο χάρι πότερ και ', 'ο χαρι ποτερ και ', 'harry potter and the ', 'harry potter and ',
            'fantastic beasts: ', 'φανταστικά ζώα: ', 'φανταστικά ζώα και ',
            'diary of a wimpy kid: ', 'diary of a wimpy kid ',
            'captain underpants: ', 'captain underpants ',
        ]
        for prefix in prefixes:
            if canonical.startswith(prefix):
                canonical = canonical[len(prefix):]
                break
        
        dm_patterns = [
            r'^adventures\s+of\s+dog\s*man\s*\d{0,2}\s*[-:]\s*',
            r'^dog\s*man\s*\d{1,2}\s*[-:]\s*',
            r'^dog\s*man\s*[-:]\s*',
            r'^dog\s*man\s+',
        ]
        for pattern in dm_patterns:
            dm_match = re.match(pattern, canonical)
            if dm_match:
                canonical = canonical[dm_match.end():]
                break
        
        edition_keywords = [
            'edition', 'έκδοση', 'illustrated', 'εικονογραφημένο', 'εικονογραφημένη',
            'collector', 'συλλεκτική', 'deluxe', 'anniversary', 'special', 'gift',
            'paperback', 'hardcover', 'hardback', 'softcover', 'minalima',
            'gryffindor', 'slytherin', 'hufflepuff', 'ravenclaw', 'rehearsal',
        ]
        
        paren_match = re.search(r'\s*\([^)]*(?:' + '|'.join(edition_keywords) + r')[^)]*\)\s*$', canonical)
        if paren_match: canonical = canonical[:paren_match.start()]
        
        for delimiter in [' - ', ': ', ' – ', ' — ']:
            if delimiter in canonical:
                parts = canonical.split(delimiter)
                if len(parts) >= 2:
                    suffix_part = parts[-1].lower().strip()
                    words = suffix_part.split()
                    if len(words) <= 4 and any(kw in suffix_part for kw in edition_keywords):
                        canonical = delimiter.join(parts[:-1])
        
        for suffix in [' cd', ' audiobook', ' audio book', ' mp3', ' audio']:
            if canonical.endswith(suffix):
                canonical = canonical[:-len(suffix)]
                break
        
        for suffix in [' pb', ' hb', ' (pb)', ' (hb)']:
            if canonical.endswith(suffix):
                canonical = canonical[:-len(suffix)]
                break
        
        marketing_paren = re.search(r'\s*\([^)]*(?:new|graphic novel|book|novel)[^)]*\)\s*$', canonical, re.IGNORECASE)
        if marketing_paren: canonical = canonical[:marketing_paren.start()]
        
        for suffix in [': a graphic novel', ' - a graphic novel', ': graphic novel']:
            if canonical.endswith(suffix):
                canonical = canonical[:-len(suffix)]
                break
        
        if canonical.startswith('dog man: '): canonical = canonical[9:]
        canonical = canonical.replace("'", "'").replace("'", "'").replace("`", "'")
        
        return canonical.strip()

    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    used_materials.add(tm)
    
    t_series_raw = trigger.get('Σειρά βιβλίου', None)
    if t_series_raw is None:
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
    
    trigger_is_box_set = is_box_set(tt)
    trigger_is_complete_box = trigger_is_box_set and is_complete_box_set(tt)
    trigger_canonical = get_canonical_book_name(tt, t_orig_title)
    used_titles.add(trigger_canonical)
    
    box_status = "complete box set" if trigger_is_complete_box else ("partial box set" if trigger_is_box_set else "individual book")
    diag.append(("0. Trigger", "", f"Series: '{t_series}' (valid: {has_series}), Age: '{effective_age}', Type: {box_status}"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 1: SERIES ENGINE (Up to 10 slots)
    # ══════════════════════════════════════════════════════════
    series_notes = ["=== PRIORITY 1: SERIES ENGINE ==="]
    series_count = 0
    max_series = 10
    
    if trigger_is_complete_box:
        series_notes.append("⚠ Complete box set detected - skipping series books")
        diag.append(("1. Series Engine", 0, "Skipped (complete box set)"))
    elif has_series:
        books_only = df_all[df_all['Level 1'] == 'Books'].copy()
        series_col = 'Σειρά βιβλίου'
        if series_col not in books_only.columns:
            for col in books_only.columns:
                if 'σειρά' in col.lower() or 'series' in col.lower():
                    series_col = col
                    break
        
        if series_col in books_only.columns:
            series_books = books_only[books_only[series_col].fillna('').astype(str).str.strip() == t_series].copy()
        else:
            series_books = pd.DataFrame()
        
        series_books = series_books[series_books['Material'] != tm]
        series_books['_canonical'] = series_books.apply(lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', '')), axis=1)
        series_books = series_books[series_books['_canonical'] != trigger_canonical]
        
        if not trigger_is_box_set and not series_books.empty:
            series_books = series_books[~series_books['Title'].apply(is_box_set)]
            
        if t_level2:
            series_books = series_books[series_books['Level 2'] == t_level2]
            
        def is_novelty_language(title):
            novelty_langs = ['(ancient greek)', '(latin)', '(irish)', '(scots)', '(welsh)', '(gaelic)', '(αρχαία ελληνικά)', '(λατινικά)']
            return any(lang in str(title).lower() for lang in novelty_langs)
        if not series_books.empty:
            series_books = series_books[~series_books['Title'].apply(is_novelty_language)]
            
        def is_audiobook(title):
            audiobook_keywords = [' cd', ' audiobook', ' audio book', ' mp3', 'ηχητικό', 'ακουστικό']
            return any(kw in str(title).lower() for kw in audiobook_keywords)
        if not series_books.empty:
            series_books = series_books[~series_books['Title'].apply(is_audiobook)]
            
        def get_edition_line(title):
            title_lower = str(title).lower()
            for house in ['gryffindor', 'slytherin', 'hufflepuff', 'ravenclaw']:
                if house in title_lower: return 'house_' + house
            edition_patterns = [
                ('minalima', 'minalima'), ('illustrated', 'illustrated'), ('20th anniversary', 'anniversary_20'),
                ('25th anniversary', 'anniversary_25'), ('anniversary', 'anniversary'), ('deluxe', 'deluxe'),
                ('collector', 'collector'), ('special', 'special'), ('gift', 'gift'),
            ]
            for pattern, line in edition_patterns:
                if pattern in title_lower: return line
            return 'standard'
        
        trigger_edition_line = get_edition_line(tt)
        
        # Base Format Score
        if not series_books.empty:
            series_books['Format_Score'] = 0
            series_books['_edition_line'] = series_books['Title'].apply(get_edition_line)
            series_books.loc[series_books['_edition_line'] == trigger_edition_line, 'Format_Score'] += 5000
            
            if t_cover and t_cover != 'nan' and t_cover != '0' and 'Εξώφυλλο' in series_books.columns:
                series_books.loc[series_books['Εξώφυλλο'].fillna('').astype(str).str.strip() == t_cover, 'Format_Score'] += 1000
            if t_dims and t_dims != 'nan' and t_dims != 'NaN' and 'Διαστάσεις' in series_books.columns:
                series_books.loc[series_books['Διαστάσεις'].fillna('').astype(str).str.strip() == t_dims, 'Format_Score'] += 1000
            if t_pub_series and t_pub_series != 'nan' and t_pub_series != '0' and 'Εκδοτική Σειρά' in series_books.columns:
                series_books.loc[series_books['Εκδοτική Σειρά'].fillna('').astype(str).str.strip() == t_pub_series, 'Format_Score'] += 1000
            if t_illus and t_illus != 'nan' and t_illus != '0' and 'Λεπτομέρειες εικονογράφησης' in series_books.columns:
                series_books.loc[series_books['Λεπτομέρειες εικονογράφησης'].fillna('').astype(str).str.strip() == t_illus, 'Format_Score'] += 1000
                
            series_books['Final_Score'] = SERIES_BOOST + series_books['Format_Score']
            if 'AVAILABILITY' in series_books.columns:
                series_books.loc[series_books['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST

        # 🟢 PREPARE PUBLISH DATE & SALES 
        if 'Ημερ/νία έκδοσης' in series_books.columns:
            series_books['Pub_Date'] = pd.to_datetime(series_books['Ημερ/νία έκδοσης'], errors='coerce')
        else:
            series_books['Pub_Date'] = pd.NaT
            
        t_pub_date = trigger.get('Ημερ/νία έκδοσης', '')
        t_pub_date_parsed = pd.to_datetime(t_pub_date, errors='coerce') if t_pub_date else pd.NaT
        
        if 'Sum of Sales' in series_books.columns:
            series_books['Sales_Score'] = pd.to_numeric(series_books['Sum of Sales'], errors='coerce').fillna(0)
        else:
            # Fallback to history frequency if Sum of Sales isn't attached
            tcust = df_history[df_history['Material']==tm]['customerEmail'].unique() if not df_history.empty else []
            bw = df_history[(df_history['customerEmail'].isin(tcust))&(df_history['Material']!=tm)] if not df_history.empty else pd.DataFrame()
            fdf = bw['Material'].value_counts().reset_index() if not bw.empty else pd.DataFrame(columns=['NID', 'Frequency'])
            if not fdf.empty:
                fdf.columns = ['NID', 'Frequency']
                series_books = series_books.merge(fdf, left_on='Material', right_on='NID', how='left')
                series_books['Sales_Score'] = series_books['Frequency'].fillna(0)
            else:
                series_books['Sales_Score'] = 0

        # 🟢 DETERMINE LOGIC (Ordered/Mixed vs Standalone)
        t_series_lower = t_series.lower()
        if is_harry_potter_series(t_series) or is_dog_man_series(t_series) or is_mikroi_kyrioi_series(t_series):
            order_logic = 'Ordered'
        else:
            order_logic = SERIES_ORDER_MAP.get(t_series_lower, 'Standalone')
        
        series_notes.append(f"Logic applied: {order_logic}")

        series_books_sorted = pd.DataFrame()
        
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
                series_notes.append(f"Added other box sets: {series_count}")

        if series_count < max_series and not series_books.empty:
            if order_logic in ['Ordered', 'Mixed']:
                if is_harry_potter_series(t_series):
                    trigger_order = get_hp_order(tt)
                    series_books['_order'] = series_books['Title'].apply(get_hp_order)
                elif is_dog_man_series(t_series):
                    trigger_order = get_dog_man_order(tt)
                    series_books['_order'] = series_books['Title'].apply(get_dog_man_order)
                elif is_mikroi_kyrioi_series(t_series):
                    trigger_order = get_mikroi_kyrioi_order(tt)
                    series_books['_order'] = series_books['Title'].apply(get_mikroi_kyrioi_order)
                else:
                    trigger_order = t_pub_date_parsed
                    series_books['_order'] = series_books['Pub_Date']
                
                if pd.isna(trigger_order):
                    series_books_sorted = series_books.sort_values(['_order', 'Final_Score'], ascending=[True, False])
                else:
                    books_after = series_books[series_books['_order'] > trigger_order].sort_values(['_order', 'Final_Score'], ascending=[True, False])
                    books_before = series_books[series_books['_order'] < trigger_order].sort_values(['_order', 'Final_Score'], ascending=[True, False])
                    books_same = series_books[series_books['_order'] == trigger_order].sort_values('Final_Score', ascending=False)
                    series_books_sorted = pd.concat([books_after, books_before, books_same])
            else:
                # Standalone Logic: Sales first, fallback to Publish Date (Newest)
                series_books_sorted = series_books.sort_values(['Sales_Score', 'Pub_Date', 'Final_Score'], ascending=[False, False, False])
            
            for _, row in series_books_sorted.iterrows():
                if series_count >= max_series: break
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
            
            series_notes.append(f"Filled {series_count} Series Books slots.")
    else:
        series_notes.append("No valid series found on trigger")
    
    slot_notes[1] = series_notes
    diag.append(("1. Series Engine", series_count, f"Filled {series_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 2: CROSS-SELL (Toys & Stationery)
    # ══════════════════════════════════════════════════════════
    crosssell_notes = ["=== PRIORITY 2: CROSS-SELL ==="]
    crosssell_count = 0
    max_crosssell = min(4, 10 - series_count)
    crosssell_notes.append(f"Cross-sell: {max_crosssell} slots available")
    
    if max_crosssell > 0:
        toys = df_all[df_all['Level 1'] == 'Toys'].copy()
        stationery = df_all[df_all['Level 1'] == 'Stationery'].copy()
        
        age_bracket_str = get_age_bracket(t_age)
        age_bracket = int(age_bracket_str.replace('BRACKET_', '')) if 'BRACKET_' in age_bracket_str else 5
        def get_allowed_toy_ages(bracket):
            if bracket == 1: return ['0+ μηνών', '0+ ετών', '3+ μηνών', '5+ μηνών', '6+ μηνών', '']
            elif bracket == 2: return ['6+ μηνών', '9+ μηνών', '12+ μηνών', '1+ ετών', '']
            elif bracket == 3: return ['9+ μηνών', '12+ μηνών', '1+ ετών', '1.5+ ετών', '24+ μηνών', '2+ ετών', '']
            elif bracket == 4: return ['1.5+ ετών', '24+ μηνών', '2+ ετών', '3+ ετών', '']
            elif bracket == 5: return ['3+ ετών', '4+ ετών', '5+ ετών', '6+ ετών', '7+ ετών', '8+ ετών', '']
            elif bracket == 6: return ['6+ ετών', '7+ ετών', '8+ ετών', '9+ ετών', '10+ ετών', '11+ ετών', '12+ ετών', '13+ ετών', '14+ ετών', '']
            elif bracket == 7: return ['10+ ετών', '11+ ετών', '12+ ετών', '13+ ετών', '14+ ετών', '15+ ετών', '16+ ετών', '17+ ετών', '18+ ετών', '']
            return ['']
        bracket_allowed_ages = get_allowed_toy_ages(age_bracket)
        
        def detect_gender(trigger_row, series_name, title, hierarchy):
            series_lower = str(series_name).lower().strip()
            if series_lower in SERIES_GENDER_MAP: return SERIES_GENDER_MAP[series_lower]
            gender_field = str(trigger_row.get('Φύλο', '')).lower().strip()
            if gender_field:
                if any(x in gender_field for x in ['κορίτσι', 'girl', 'θηλυκό', 'female']): return 'girl'
                elif any(x in gender_field for x in ['αγόρι', 'boy', 'αρσενικό', 'male']): return 'boy'
            hier_lower = str(hierarchy).lower()
            if any(x in hier_lower for x in ['barbie', 'princess', 'πριγκίπισσα']): return 'girl'
            text = (str(series_name) + ' ' + str(title)).lower()
            girl_keywords = ['fairy', 'magic', 'princess', 'rainbow', 'unicorn', 'ballerina', 'barbie', 'frozen', 'elsa', 'anna', 'mermaid', 'kitty', 'doll', 'sparkle', 'glitter', 'flower', 'νεράιδα', 'πριγκίπισσα', 'κούκλα']
            boy_keywords = ['quest', 'warrior', 'beast', 'dragon', 'dinosaur', 'dino', 'monster', 'ninja', 'pirate', 'superhero', 'hero', 'battle', 'fight', 'soldier', 'robot', 'car', 'truck', 'spider-man', 'batman', 'marvel', 'avengers', 'star wars', 'minecraft', 'pokemon', 'δεινόσαυρος', 'πειρατής', 'ήρωας']
            if any(kw in text for kw in girl_keywords): return 'girl'
            elif any(kw in text for kw in boy_keywords): return 'boy'
            return 'neutral'
        
        detected_gender = detect_gender(trigger, t_series, tt, t_hierarchy)
        
        def get_hierarchy_category(hierarchy):
            hier_lower = str(hierarchy).lower()
            if any(x in hier_lower for x in ['ζωγραφικη', 'χειροτεχνι', 'αυτοκολλητ', 'δραστηριοτητ', 'τεχνη', 'μουσικ']): return 'arts'
            elif any(x in hier_lower for x in ['εφευρεσ', 'πειραμ', 'αστρονομ', 'φυσικ', 'χημ', 'βιολογ', 'επιστημ', 'τεχνολογ', 'γνωσ', 'εγκυκλοπαιδ', 'περιβαλλον', 'οικολογ', 'ζωα', 'ιστορ', 'γεωγραφ', 'ατλαντ', 'μυθολογ']): return 'stem'
            elif any(x in hier_lower for x in ['προσχολικ', 'χρωματα', 'σχηματα', 'αντιθετ', 'αναγνωση', 'γραφη']): return 'preschool'
            elif any(x in hier_lower for x in ['λογοτεχν', 'παραμυθ', 'μυθ', 'κομικ', 'χιουμορ', 'παιδικ']): return 'fiction'
            elif any(x in hier_lower for x in ['παζλ', 'σπαζοκεφαλ', 'αινιγμ', 'παιχνιδ', 'διαδραστικ']): return 'activity'
            return 'general'
        
        hierarchy_category = get_hierarchy_category(t_hierarchy)
        
        adult_brands = ['moleskine', 'leuchtturm', 'rhodia', 'field notes', 'midori']
        def is_adult_brand(title, brand=''):
            text = (str(title) + ' ' + str(brand)).lower()
            return any(ab in text for ab in adult_brands)
        stationery = stationery[~stationery.apply(lambda r: is_adult_brand(r.get('Title', ''), r.get('Brand', '')), axis=1)]
        
        adult_toy_hierarchies = ['TECHNIC', 'LEGO ICONS', 'ICONS', 'CREATOR EXPERT', 'ARCHITECTURE', 'LEGO ART', 'IDEAS', 'BOTANICS', 'LEGO BOTANICAL']
        toys = toys[~toys['Hierarchy'].str.upper().str.strip().isin([h.upper() for h in adult_toy_hierarchies])]
        
        if 'Προτεινόμενη Ηλικία' in toys.columns:
            if age_bracket <= 5: 
                toys = toys[toys['Προτεινόμενη Ηλικία'].fillna('').astype(str).str.strip().isin(bracket_allowed_ages)]
            else: 
                toys = toys[toys['Προτεινόμενη Ηλικία'].fillna('').astype(str).str.strip().isin(bracket_allowed_ages) | (toys['Προτεινόμενη Ηλικία'].fillna('') == '') | (toys['Προτεινόμενη Ηλικία'].fillna('').astype(str) == '0')]
        
        def toy_matches_gender(title, brand, gender):
            text = (str(title) + ' ' + str(brand)).lower()
            if gender == 'girl':
                boy_only = ['spider-man', 'batman', 'avengers', 'marvel', 'dinosaur', 'dino', 'monster truck', 'transformers', 'ninja', 'nerf', 'army', 'soldier']
                return not any(b in text for b in boy_only)
            elif gender == 'boy':
                girl_only = ['barbie', 'princess', 'frozen', 'elsa', 'anna', 'fairy', 'unicorn', 'my little pony', 'hello kitty', 'ballerina']
                return not any(g in text for g in girl_only)
            return True
        
        def stationery_matches_gender(title, brand, gender):
            text = (str(title) + ' ' + str(brand)).lower()
            if gender == 'girl':
                boy_only = ['spider-man', 'batman', 'avengers', 'marvel', 'dinosaur', 'cars', 'minecraft']
                return not any(b in text for b in boy_only)
            elif gender == 'boy':
                girl_only = ['barbie', 'princess', 'frozen', 'fairy', 'unicorn', 'hello kitty']
                return not any(g in text for g in girl_only)
            return True
        
        toys['Final_Score'] = 0
        stationery['Final_Score'] = 0
        if 'AVAILABILITY' in toys.columns: toys.loc[toys['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
        if 'AVAILABILITY' in stationery.columns: stationery.loc[stationery['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
        
        if has_series:
            for idx in toys.index:
                if ip_matches(t_series, str(toys.loc[idx, 'Brand']) if 'Brand' in toys.columns else '', str(toys.loc[idx, 'Ήρωες Παιχνιδιών']) if 'Ήρωες Παιχνιδιών' in toys.columns else '') or normalize_ip_name(t_series) in normalize_ip_name(str(toys.loc[idx, 'Title']) if 'Title' in toys.columns else ''):
                    toys.loc[idx, 'Final_Score'] += SMART_BOOST * 5
            for idx in stationery.index:
                if ip_matches(t_series, str(stationery.loc[idx, 'Brand']) if 'Brand' in stationery.columns else '', str(stationery.loc[idx, 'Ήρωες Παιχνιδιών']) if 'Ήρωες Παιχνιδιών' in stationery.columns else '') or normalize_ip_name(t_series) in normalize_ip_name(str(stationery.loc[idx, 'Title']) if 'Title' in stationery.columns else ''):
                    stationery.loc[idx, 'Final_Score'] += SMART_BOOST * 5
                    
        # Cross-Sell Slot 1: IP Toy or Age-Appropriate Fallback
        if crosssell_count < max_crosssell:
            item1_found = False
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
                        item1_found = True
            
            if not item1_found:
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
                                item1_found = True
                elif age_bracket == 5 and not item1_found:
                    if detected_gender == 'girl':
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
                                    item1_found = True
                    else:
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
                                    item1_found = True
                elif age_bracket >= 6 and not item1_found:
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
                                item1_found = True
                if not item1_found:
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

        # Cross-Sell Slot 2: Hierarchy-Based Creative
        if crosssell_count < max_crosssell:
            item2_found = False
            if hierarchy_category == 'arts' and not item2_found:
                arts = stationery[stationery['Hierarchy'].isin(STATIONERY_HIERARCHIES_ACTUAL.get('arts_crafts', []))].copy()
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
                            item2_found = True
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
                            item2_found = True
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
                            item2_found = True
            if not item2_found:
                if age_bracket <= 6:
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
                                item2_found = True
                else:
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

        # Cross-Sell Slot 3: Puzzles/Games
        if crosssell_count < max_crosssell:
            item3_found = False
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
                            item3_found = True
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

        # Cross-Sell Slot 4: Lifestyle
        if crosssell_count < max_crosssell:
            item4_found = False
            if age_bracket <= 6:
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
                            item4_found = True
            else:
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
                            item4_found = True
    
    slot_notes[2] = crosssell_notes
    diag.append(("2. Cross-Sell", crosssell_count, f"Filled {crosssell_count} slots"))
    
    # ══════════════════════════════════════════════════════════
    # PRIORITY 3: CATEGORY DISCOVERY (Fill remaining slots)
    # ══════════════════════════════════════════════════════════
    discovery_notes = ["=== PRIORITY 3: CATEGORY DISCOVERY ==="]
    total_filled = series_count + crosssell_count
    remaining = 10 - total_filled
    discovery_count = 0
    
    if not trigger_is_complete_box and remaining > 0:
        books_only = df_all[df_all['Level 1'] == 'Books'].copy()
        
        # Priority A: HP Spinoffs (keep hardcoded feature)
        if has_series and is_harry_potter_series(t_series):
            series_col = 'Σειρά βιβλίου'
            if series_col in books_only.columns:
                hp_all = books_only[books_only[series_col].fillna('').astype(str).str.strip() == t_series].copy()
                if t_level2: hp_all = hp_all[hp_all['Level 2'] == t_level2]
                hp_all['_hp_order'] = hp_all['Title'].apply(get_hp_order)
                spinoffs = hp_all[hp_all['_hp_order'] > 7].copy()
                spinoffs = spinoffs[~spinoffs['Material'].isin(used_materials)]
                spinoffs = spinoffs[spinoffs['Material'] != tm]
                if not trigger_is_box_set: spinoffs = spinoffs[~spinoffs['Title'].apply(is_box_set)]
                
                if not spinoffs.empty:
                    spinoffs['Final_Score'] = 0
                    if 'AVAILABILITY' in spinoffs.columns:
                        spinoffs.loc[spinoffs['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
                    spinoffs = spinoffs.sort_values('Final_Score', ascending=False)
                    for _, row in spinoffs.iterrows():
                        if discovery_count >= remaining: break
                        row_canonical = get_canonical_book_name(row['Title'], row.get('Τίτλος πρωτοτύπου', ''))
                        if row['Material'] not in used_materials and row_canonical not in used_titles:
                            row_copy = row.copy()
                            row_copy['Assigned_Slot'] = total_filled + discovery_count + 1
                            row_copy['Slot_Role'] = 'Explore Series' 
                            row_copy['Item_Rank'] = 1
                            all_recs.append(row_copy)
                            used_materials.add(row['Material'])
                            used_titles.add(row_canonical)
                            discovery_count += 1
        
        remaining_after_spinoffs = remaining - discovery_count
        
        # Priority B: Same category/hierarchy
        if remaining_after_spinoffs > 0:
            discovery_pool = books_only[books_only['Hierarchy'] == t_hierarchy].copy()
            discovery_pool = discovery_pool[~discovery_pool['Material'].isin(used_materials)]
            discovery_pool = discovery_pool[discovery_pool['Material'] != tm]
            if t_level2: discovery_pool = discovery_pool[discovery_pool['Level 2'] == t_level2]
            
            discovery_pool['_canonical'] = discovery_pool.apply(lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', ''))), axis=1)
            discovery_pool = discovery_pool[discovery_pool['_canonical'] != trigger_canonical]
            discovery_pool = discovery_pool[~discovery_pool['_canonical'].isin(used_titles)]
            
            if not trigger_is_box_set: discovery_pool = discovery_pool[~discovery_pool['Title'].apply(is_box_set)]
            
            if 'Ηλικία' in discovery_pool.columns and allowed_ages:
                discovery_pool = discovery_pool[discovery_pool['Ηλικία'].fillna('').astype(str).str.strip().isin(allowed_ages) | (discovery_pool['Ηλικία'].fillna('') == '') | (discovery_pool['Ηλικία'].fillna('').astype(str) == '0')]
            
            if 'Sum of Sales' in discovery_pool.columns:
                discovery_pool['Sales_Score'] = pd.to_numeric(discovery_pool['Sum of Sales'], errors='coerce').fillna(0)
            else:
                tcust = df_history[df_history['Material']==tm]['customerEmail'].unique() if not df_history.empty else []
                bw = df_history[(df_history['customerEmail'].isin(tcust))&(df_history['Material']!=tm)] if not df_history.empty else pd.DataFrame()
                fdf = bw['Material'].value_counts().reset_index() if not bw.empty else pd.DataFrame(columns=['NID', 'Frequency'])
                if not fdf.empty:
                    fdf.columns = ['NID', 'Frequency']
                    discovery_pool = discovery_pool.merge(fdf, left_on='Material', right_on='NID', how='left')
                    discovery_pool['Sales_Score'] = discovery_pool['Frequency'].fillna(0)
                else:
                    discovery_pool['Sales_Score'] = 0
            
            discovery_pool['Final_Score'] = 0
            if 'AVAILABILITY' in discovery_pool.columns:
                discovery_pool.loc[discovery_pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST
            
            discovery_pool = discovery_pool.sort_values(['Sales_Score', 'Final_Score'], ascending=[False, False])
            discovery_notes.append(f"Sorting discovery pool by Sales (Best Sellers) and Availability.")
            
            for _, row in discovery_pool.head(remaining_after_spinoffs).iterrows():
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
    
    slot_notes[3] = discovery_notes
    diag.append(("3. Discovery", discovery_count, f"Filled {discovery_count} slots"))
    diag.append(("TOTAL", series_count + crosssell_count + discovery_count, f"out of 10"))
    
    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        recs_df = recs_df.sort_values('Assigned_Slot').reset_index(drop=True)
        return recs_df, diag, slot_notes, recs_df
    else:
        return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 🟢 SMARTPHONES ENGINE (UPDATED FOR HIGH-END BRAND & BEST SELLER FALLBACK)
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
    
    b4hier = len(c)
    if tb == "APPLE":
        android_hier_keywords = ['samsung', 'xiaomi', 'huawei', 'oppo', 'oneplus', 'realme', 'android']
        hier_pattern = '|'.join(android_hier_keywords)
        c = c[~c['Hierarchy'].fillna('').str.lower().str.contains(hier_pattern, regex=True, na=False)]
    elif tb in ANDROID_OEMS:
        apple_hier_keywords = ['iphone', 'apple', 'ipad', 'macbook', 'airpods']
        hier_pattern = '|'.join(apple_hier_keywords)
        c = c[~c['Hierarchy'].fillna('').str.lower().str.contains(hier_pattern, regex=True, na=False)]
    diag.append(("4c. Ecosystem wall (hierarchy)", len(c), f"Removed {b4hier-len(c)}"))

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
    c['Smart_Boost'] = 0.0
    
    if strict_tmod:
        c.loc[c['Μοντέλο'].fillna('').astype(str).str.contains(strict_tmod, case=False, regex=True, na=False), 'Smart_Boost'] += SMART_BOOST

    # 🟢 NEW: Premium phone absolute brand preference & High-End Best Seller Fallback
    PREMIUM_PRICE_THRESHOLD = 850
    PREMIUM_BRAND_BOOST = 5000000.0  # Massive absolute boost to guarantee brand matches win
    BEST_SELLER_BOOST = 200000.0
    EXPENSIVE_BOOST = 100000.0
    PREMIUM_ACC_MIN_PRICE = 25.0
    
    is_premium = tprice >= PREMIUM_PRICE_THRESHOLD
    if is_premium:
        is_same_brand = c['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
        is_best_seller = c['Sales_Tiebreaker'].fillna(0.0) > 0
        is_expensive = c['Next_Price'].fillna(0.0) >= PREMIUM_ACC_MIN_PRICE
        
        # Tier 0: Absolute Priority: Exact Brand Match in every slot (e.g., Apple on Apple)
        c.loc[is_same_brand, 'Smart_Boost'] += PREMIUM_BRAND_BOOST
        
        # Tier 1: Fallback Priority 1: Best Sellers for slots without brand match
        c.loc[~is_same_brand & is_best_seller, 'Smart_Boost'] += BEST_SELLER_BOOST
        
        # Tier 2: Fallback Priority 2: Expensive items
        c.loc[~is_same_brand & ~is_best_seller & is_expensive, 'Smart_Boost'] += EXPENSIVE_BOOST
        
        # Intra-tier sorting: scale everything by price so the PRICIEST item floats to the top of its respective tier
        c['Smart_Boost'] += c['Next_Price'].fillna(0.0) * 1000.0
        
        diag.append(("Premium High-End Strategy", f"€{tprice:.0f} >= €{PREMIUM_PRICE_THRESHOLD}", "1. Exact Brand, 2. Priciest Best-Sellers, 3. Priciest Fallbacks"))
    else:
        # 🟢 LOWER-END STRATEGY
        # Rule 2: Exclude other major brands from being recommended entirely to avoid cross-contamination
        MAJOR_BRANDS = ["APPLE", "SAMSUNG", "XIAOMI", "HUAWEI", "OPPO"]
        other_majors = [b for b in MAJOR_BRANDS if b != tb]
        b4_major = len(c)
        c = c[~c['Κατασκευαστής'].fillna('').str.strip().str.upper().isin(other_majors)]
        diag.append(("Lower-End Major Brand Filter", len(c), f"Removed {b4_major - len(c)} cross-brand items"))
        
        # Base smart boost for exact brand matches globally
        c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Smart_Boost'] += SMART_BOOST
    
    def extract_year_from_model(model_str):
        model = str(model_str).lower()
        year_match = re.search(r'\b(202[3-9])\b', model)
        if year_match: return int(year_match.group(1))
        s_match = re.search(r'galaxy\s*s\s*(\d{2})', model)
        if s_match:
            num = int(s_match.group(1))
            if 20 <= num <= 30: return 2000 + num
        a_match = re.search(r'galaxy\s*a\s*(\d{2})', model)
        if a_match:
            num = int(a_match.group(1))
            if num >= 50: return 2019 + (num - 50)
        z_match = re.search(r'(flip|fold)\s*(\d)', model)
        if z_match: return 2019 + int(z_match.group(2))
        iphone_match = re.search(r'iphone\s*(\d{1,2})', model)
        if iphone_match:
            num = int(iphone_match.group(1))
            if num >= 12: return 2008 + num 
            elif num >= 10: return 2017 
        return None
    
    def extract_year_from_accessory(title_str, model_str=''):
        text = f"{title_str} {model_str}".lower()
        year_match = re.search(r'\b(202[3-9])\b', text)
        if year_match: return int(year_match.group(1))
        buds_match = re.search(r'buds\s*(\d|fe|pro|live)', text)
        if buds_match:
            v = buds_match.group(1)
            if v == '4': return 2025
            if v == '3': return 2024
            if v == '2': return 2022
            if v == 'fe': return 2023
            if v == 'pro': return 2022
            if v == 'live': return 2020
        watch_match = re.search(r'(galaxy\s*)?watch\s*(\d)', text)
        if watch_match: return 2018 + int(watch_match.group(2))
        fit_match = re.search(r'(galaxy\s*)?fit\s*(\d)', text)
        if fit_match: return 2021 + int(fit_match.group(2))
        return None
    
    phone_year = extract_year_from_model(tmod) or extract_year_from_model(tt)
    
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

        model_specific_slots = ["PRIMARY_CASE", "SCREEN_GLASS", "CAMERA_GLASS", "ALT_CASE"]
        
        if lk in model_specific_slots:
            if strict_tmod:
                b4 = len(sc)
                cv = sc[CC].fillna('').astype(str).str.lower()
                m = sc[cv.str.contains(strict_tmod, case=False, regex=True, na=False)]
                if m.empty:
                    m = sc[sc['Title'].fillna('').astype(str).str.lower().str.contains(strict_tmod, case=False, regex=True, na=False)]
                if rival_regex and not m.empty:
                    m = m[~m[CC].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                    m = m[~m['Title'].fillna('').astype(str).str.lower().str.contains(rival_regex, regex=True, na=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                sc = m  
            else:
                sc = sc.head(0)
            
            if lk == "PRIMARY_CASE":
                if not sc.empty:
                    b4=len(sc)
                    f=sc[sc['Τύπος Θήκης'].fillna('').astype(str).str.contains("Back Cover", case=False, na=False)]
                    notes.append(f"Back Cover: {b4}→{len(f)}")
                    sc = f  
                if not sc.empty and tcol:
                    b4=len(sc)
                    exact_colors = [clr for clr in ccols if clr != 'διάφανο' and clr != 'transparent']
                    sc_exact = sc[sc['Χρώμα'].fillna('').astype(str).str.strip().str.lower().isin(exact_colors)]
                    if not sc_exact.empty:
                        sc = sc_exact
                        notes.append(f"Color (exact): {b4}→{len(sc)}")
                    else:
                        sc_transparent = sc[sc['Χρώμα'].fillna('').astype(str).str.strip().str.lower().isin(['διάφανο', 'transparent', 'clear'])]
                        if not sc_transparent.empty:
                            sc = sc_transparent
                            notes.append(f"Color (transparent fallback): {b4}→{len(sc)}")
                        else:
                            notes.append(f"Color: no match, keeping all {b4}")
            
            # 🟢 LOWER-END PROTECTION RULE (Rule 1)
            # Prioritize Brand+Sales, then TUNE, then Brand w/o Sales
            if not is_premium and not sc.empty:
                is_same_brand_slot = sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                has_sales_slot = sc['Sales_Tiebreaker'].fillna(0.0) > 0
                is_tune_slot = sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == "TUNE"
                
                # Apply custom score hierarchy
                sc.loc[is_same_brand_slot & has_sales_slot, 'Final_Score'] += 200000.0
                sc.loc[is_tune_slot, 'Final_Score'] += 100000.0
                sc.loc[is_same_brand_slot & ~has_sales_slot, 'Final_Score'] += 50000.0
                
                # Standard sales tiebreaker within the tiers
                sc['Final_Score'] += sc['Sales_Tiebreaker'].fillna(0.0) * 10.0
                notes.append("Applied Lower-End Protection Rule: 1. Brand+Sales, 2. TUNE")

        if lk == "CROSS_SELL" and not sc.empty:
            b4_brand = len(sc)
            samsung_only_keywords = ['smarttag', 'galaxy smart']
            apple_only_keywords = ['airtag']
            
            def is_compatible_accessory(row):
                title_lower = str(row.get('Title', '')).lower()
                if any(kw in title_lower for kw in samsung_only_keywords): return tb == "SAMSUNG" 
                if any(kw in title_lower for kw in apple_only_keywords): return tb == "APPLE" 
                return True
            
            sc = sc[sc.apply(is_compatible_accessory, axis=1)]
            if len(sc) < b4_brand: notes.append(f"Brand filter (trackers): {b4_brand}→{len(sc)}")

        has_wireless_charging = 'ασύρματη φόρτιση' in tex
        has_fast_charging = 'γρήγορη φόρτιση' in tex
        
        charger_slots = ["WALL_CHARGER", "POWERBANK"]
        if lk in charger_slots and not sc.empty:
            WIRELESS_BOOST = 30000 
            FAST_CHARGE_BOOST = 20000 
            HIGH_WATT_BOOST = 15000 
            
            # Apply dynamic wattage boosts
            for idx in sc.index:
                item_title = str(sc.loc[idx, 'Title']).lower()
                item_watt = str(sc.loc[idx, 'Ισχύς (Watt)']) if 'Ισχύς (Watt)' in sc.columns else ''
                
                if has_fast_charging or is_premium:
                    watt_match = re.search(r'(\d+)\s*w', item_title)
                    watt_from_col = re.search(r'(\d+)', str(item_watt)) if item_watt else None
                    
                    wattage = 0
                    if watt_match: wattage = int(watt_match.group(1))
                    elif watt_from_col: wattage = int(watt_from_col.group(1))
                    elif '21 - 60' in str(item_watt): wattage = 45 
                    
                    if is_premium:
                        if wattage >= 45: sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST + HIGH_WATT_BOOST
                        elif wattage >= 25: sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST
                        elif wattage >= 20: sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST // 2
                    else: # Lower-end phone with fast charge
                        if 20 <= wattage <= 35: 
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST + HIGH_WATT_BOOST
                        elif wattage >= 45: 
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST // 2
                        elif wattage >= 15:
                            sc.loc[idx, 'Final_Score'] += FAST_CHARGE_BOOST // 3

            # 🟢 STRICT STRUCTURAL LOOPING FOR WALL_CHARGER 
            if lk == "WALL_CHARGER":
                is_cable = sc['Title'].fillna('').str.lower().str.contains(r'καλώδιο|cable') & ~sc['Title'].fillna('').str.lower().str.contains(r'φορτισ|charger|adapt|αντάπτ')
                is_wireless_item = sc['Title'].fillna('').str.lower().str.contains(r'wireless|ασύρματ|magsafe')
                is_brick = (~is_cable) & (~is_wireless_item)
                
                if has_wireless_charging:
                    # 1. Wireless, 2. Brick, 3. Cable
                    sc.loc[is_wireless_item, 'Final_Score'] += 3000000.0
                    sc.loc[is_brick, 'Final_Score'] += 2000000.0
                    sc.loc[is_cable, 'Final_Score'] += 1000000.0
                    notes.append("Charger Order: 1st Wireless, 2nd Brick, 3rd Cable")
                else:
                    # 1. Brick, 2. Cable
                    sc.loc[is_brick, 'Final_Score'] += 3000000.0
                    sc.loc[is_cable, 'Final_Score'] += 2000000.0
                    sc.loc[is_wireless_item, 'Final_Score'] -= 1000000.0
                    notes.append("Charger Order: 1st Brick, 2nd Cable (No Wireless)")
                
                # Filter strictly for cable port match
                if tport:
                    wrong_port = is_cable & ~sc['Title'].fillna('').str.lower().str.contains(tport.lower())
                    sc.loc[wrong_port, 'Final_Score'] -= 5000000.0

            sc = sc.sort_values('Final_Score', ascending=False)
            
            features = []
            if has_wireless_charging: features.append("Wireless")
            if has_fast_charging: features.append("FastCharge")
            if is_premium:
                notes.append(f"Phone features: {', '.join(features)} (Premium 45W+ preferred)")
            else:
                notes.append(f"Phone features: {', '.join(features)} (Standard 25W preferred)")

        year_match_slots = ["EARBUDS", "SMARTWATCH"]
        ULTRA_PREMIUM_THRESHOLD = 1700 
        
        if lk in year_match_slots and not sc.empty:
            # 1. Price Threshold Logic
            if lk == "EARBUDS":
                if tprice >= 1500: min_price = 100
                elif tprice >= 1000: min_price = 60
                elif tprice >= 600: min_price = 30
                elif tprice >= 300: min_price = 15
                else: min_price = 0
            else: 
                if tprice >= 1500: min_price = 200
                elif tprice >= 1000: min_price = 150
                elif tprice >= 600: min_price = 80
                elif tprice >= 300: min_price = 40
                else: min_price = 0
            
            if min_price > 0:
                b4_price = len(sc)
                sc['Acc_Price'] = sc['LIST PRICE'].apply(lambda x: parse_euro_price(x))
                price_filtered = sc[sc['Acc_Price'] >= min_price]
                if not price_filtered.empty:
                    sc = price_filtered
                    notes.append(f"Price tier (€{tprice:.0f} phone): min €{min_price} → {b4_price}→{len(sc)}")
                else:
                    notes.append(f"Price tier: No items ≥€{min_price}, keeping all {b4_price}")
            
            # 2. UNIVERSAL BRAND PRIORITY
            is_same_brand_wearable = sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
            sc.loc[is_same_brand_wearable, 'Final_Score'] += 5000000.0
            notes.append(f"Universal Wearable Brand Priority (+5M for {tb})")
            
            # 3. Ultra-Premium Filter (>= 1700€)
            is_ultra_premium = tprice >= ULTRA_PREMIUM_THRESHOLD
            if is_ultra_premium:
                b4_ultra = len(sc)
                premium_keywords = ['pro', 'ultra', 'classic', 'studio', 'max', 'elite']
                premium_pattern = '|'.join(premium_keywords)
                premium_sc = sc[sc['Title'].fillna('').str.lower().str.contains(premium_pattern, regex=True, na=False)]
                if not premium_sc.empty:
                    sc = premium_sc
                    notes.append(f"Ultra-premium filter (€{tprice:.0f}): {b4_ultra}→{len(sc)} (Pro/Ultra only)")
                else:
                    notes.append(f"Ultra-premium filter: No Pro/Ultra found, keeping all {b4_ultra}")
            
            # 4. Universal Year Matching
            if phone_year:
                sc['Accessory_Year'] = sc.apply(lambda r: extract_year_from_accessory(str(r.get('Title', '')), str(r.get('Μοντέλο', ''))), axis=1)
                
                # Add year boost directly to Final_Score so it respects Brand/Tier hierarchy
                sc.loc[sc['Accessory_Year'] > phone_year, 'Final_Score'] += 800000.0 
                sc.loc[sc['Accessory_Year'] == phone_year, 'Final_Score'] += 600000.0 
                sc.loc[sc['Accessory_Year'] == phone_year - 1, 'Final_Score'] += 400000.0 
                
                newer_count = (sc['Accessory_Year'] > phone_year).sum()
                same_year_count = (sc['Accessory_Year'] == phone_year).sum()
                prev_year_count = (sc['Accessory_Year'] == phone_year - 1).sum()
                notes.append(f"Year boost ({phone_year}): {newer_count} newer, {same_year_count} same, {prev_year_count} prev")

        if lk == "HOLDER" and not sc.empty:
            if has_wireless_charging or tb == "APPLE":
                for idx in sc.index:
                    item_title = str(sc.loc[idx, 'Title']).lower()
                    if 'magsafe' in item_title or 'magnetic' in item_title or 'mag' in item_title:
                        sc.loc[idx, 'Final_Score'] += 10000
                notes.append("Boosted MagSafe/magnetic holders for wireless phone")
            
            sc = sc.sort_values('Final_Score', ascending=False).copy()
            top_holders = sc.head(10)
            
            if len(top_holders) > 1:
                seed = hash(str(tm) + "_holder") % len(top_holders)
                rotated_indices = [(seed + i) % len(top_holders) for i in range(len(top_holders))]
                sc = top_holders.iloc[rotated_indices].copy()
                notes.append(f"Holder rotation: showing #{seed + 1} of {len(top_holders)}")

        afa = len(sc)
        slot_diag.append((sn, role, lk, afh, afa))
        slot_notes[sn] = notes

        if not sc.empty:
            skip_resort = (lk == "HOLDER" or lk == "WALL_CHARGER")
            if not skip_resort:
                sc = sc.sort_values('Final_Score', ascending=False).copy()
            else:
                sc = sc.copy() 
            sc['Assigned_Slot']=sn; sc['Slot_Role']=role
            sc['Item_Rank']=range(1,len(sc)+1)
            sc['Draft_Score']=sc['Item_Rank']*100+sn
            all_slot.append(sc)

    if not all_slot: return pd.DataFrame(), diag, slot_diag, slot_notes, pd.DataFrame()

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

# ═════════════════════════════════════════════════════════════
# 🟢 LAPTOPS ENGINE — Mainstream / Road Warrior
# ═════════════════════════════════════════════════════════════

def run_laptops_engine(trigger, df_products, df_history):
    diag = []
    slot_notes = {}
    all_recs = []
 
    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))
    tscreen = parse_screen_size(trigger.get('Μέγεθος οθόνης', ''))
    tports = str(trigger.get('Θύρες', '')).lower()
    tusage = str(trigger.get('Προτεινόμενη χρήση', '')).lower()
    
    # ---PERSONA VARIABLES ---
    is_premium = tprice >= 1000 or 'premium' in tusage
    is_apple = tb == 'APPLE'
    is_gaming = 'gaming' in tusage or 'gamer' in tusage
    # Microsoft Surface devices all have USB-C + Surface Connect, but your
    # Ports column sometimes only lists DisplayPort. Treat Surface as USB-C.
    is_surface = tb == 'MICROSOFT' and 'surface' in tt.lower()

    # 2-in-1 convertibles: touchscreen + hinge laptops. Coolers don't fit these 
    # (often used in tablet mode, detached from desk), and a Surface 2-in-1 
    # benefits from a dedicated Surface Keyboard + Pen setup.
    is_2in1 = '2 σε 1' in tusage or '2-in-1' in tusage or '2 in 1' in tusage or 'convertible' in tusage or 'συνδυαστικ' in tusage or '2σε1' in tusage
    is_ms_2in1 = is_surface or (tb == 'MICROSOFT' and is_2in1)

    # OLED screen detection — for OLED-laptop buyers we should prefer OLED monitors
    # (color-accurate creative work, HDR media, etc.)
    tscreen_tech = str(trigger.get('Τεχνολογία Οθόνης', '')).lower() + ' ' + str(trigger.get('Τύπος Οθόνης', '')).lower() + ' ' + tt.lower() + ' ' + tusage
    trigger_is_oled = 'oled' in tscreen_tech or 'amoled' in tscreen_tech
    # Retina detection (Apple). Retina laptops are premium — we should only pair with
    # monitors that have a proper panel technology (IPS/VA/OLED/etc.), not generic TN.
    trigger_is_retina = 'retina' in tscreen_tech

    # --- 2026 GR Market Tier (Performance Pairing) ---
    laptop_tier = get_laptop_tier(tprice)
    tier_names = {1: "Budget/Entry", 2: "Mid-Range/AI-Ready", 3: "High-End/Pro", 4: "Extreme/Workstation"}
    tier_label = tier_names.get(laptop_tier, "Sub-Entry")

    # --- Get Laptop Resolution Tier ---
    tres_str = str(trigger.get('Ανάλυση Οθόνης', ''))
    tres_tier = get_resolution_tier(tres_str)
 
    diag.append(("0. Trigger", f"Brand={tb}, €{tprice:.0f}", f"Tier {laptop_tier} ({tier_label}), Screen={tscreen}\", 2-in-1={is_2in1}, OLED={trigger_is_oled}, Retina={trigger_is_retina}, Ports={tports[:60]}"))
 
    # ── Build candidate pool ──
    c = df_products[df_products['Material'] != tm].copy()
    b4 = len(c)
    # Remove laptops/notebooks themselves from candidates
    c = c[~((c['Level 1'] == 'IT') & (c['Level 2'].isin(LAPTOP_L2_VALUES)))]
    diag.append(("1. Excl laptops", len(c), f"Removed {b4 - len(c)}"))
 
    # Remove smartphones from candidates
    b4 = len(c)
    c = c[~((c['Level 2'] == 'Mobiles') & (c['Hierarchy'] == 'Smartphones'))]
    diag.append(("1b. Excl phones", len(c), f"Removed {b4 - len(c)}"))

    # 🚫 Global Apple-ban for non-Apple laptops. AirPods/Magic Mouse/Apple
    # chargers should NEVER appear on a Windows/Microsoft/Dell/etc. laptop —
    # wrong ecosystem, mostly wrong connector, and visually off-brand.
    if not is_apple:
        b4 = len(c)
        c = c[c['Κατασκευαστής'].fillna('').astype(str).str.strip().str.upper() != 'APPLE']
        diag.append(("1c. Apple ban", len(c), f"Removed {b4 - len(c)} Apple items (non-Apple trigger)"))
 
    # Stock filter
    if 'CW Stock Units' in c.columns:
        stv = pd.to_numeric(c['CW Stock Units'], errors='coerce').fillna(0)
        pct = (stv > 0).sum() / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c = c[stv > 0]
            diag.append(("2. Stock filter", len(c), f"Applied ({pct:.0%})"))
        else:
            diag.append(("2. Stock filter", len(c), f"⚠ SKIPPED ({pct:.0%})"))
    else:
        diag.append(("2. Stock filter", len(c), "⚠ SKIPPED (no col)"))
 
    # Macro wall — no appliances
    b4 = len(c)
    if 'Level 1' in c.columns:
        c = c[~c['Level 1'].isin(APPL_CATS)]
    diag.append(("3. Macro wall", len(c), f"Removed {b4 - len(c)}"))
 
    # Sales tiebreaker
    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0
 
    # ── Iterate slots ──
    used_materials = {tm}
    used_hierarchies_count = {}
 
    for slot_num, role, hierarchies, logic_key in LAPTOP_MAINSTREAM_SLOTS:
        notes = [f"Logic: {logic_key}", f"Target: {hierarchies}"]

        # ── 2-in-1 override: skip Cooler slot entirely (useless for convertibles) ──
        if is_2in1 and logic_key == 'STAND_SIZE':
            notes.append("🚫 2-in-1 → skip Cooler (useless for convertibles)")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Skipped (2-in-1)"))
            continue

        # ── Small laptop override: skip Cooler for <14" laptops ──
        if tscreen > 0 and tscreen < 14.0 and logic_key == 'STAND_SIZE':
            notes.append(f"🚫 Small laptop ({tscreen}\") → skip Cooler")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Skipped (<14\" laptop)"))
            continue

        # ── Microsoft 2-in-1 overrides: Surface Keyboard (slot 1), Surface Pen (slot 3) ──
        if is_ms_2in1 and slot_num == 1:
            # Slot 1 normally = "Τσάντα Laptop" → hijack to Surface Keyboard
            hierarchies = ['KEYBOARDS WIRELESS', 'KEYBOARDS']
            role = 'Microsoft Surface Keyboard'
            notes.append("🪟 MS 2-in-1 → Slot 1 = Surface Keyboard")
        elif is_ms_2in1 and slot_num == 3:
            # Slot 3 normally = "Powerbank" → hijack to Surface Pen (stylus)
            hierarchies = ['ΓΡΑΦΙΔΕΣ']
            role = 'Microsoft Surface Pen'
            notes.append("🪟 MS 2-in-1 → Slot 3 = Surface Pen")
 
        # Hierarchy match — exact first, substring fallback
        hier_upper = [h.upper().strip() for h in hierarchies]
        pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(hier_upper)].copy()
 
        if pool.empty:
            hier_col = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
            mask = pd.Series(False, index=c.index)
            for hk in hier_upper:
                if hk:
                    mask |= hier_col.str.contains(re.escape(hk), regex=True, na=False)
            pool = c[mask].copy()
            if not pool.empty:
                notes.append(f"⚠ Substring fallback: {len(pool)}")
 
        notes.append(f"Pool: {len(pool)}")
        pool = pool[~pool['Material'].isin(used_materials)]

        # ── Non-gaming laptop: hide RGB-titled products globally ──
        # Gaming keyboards/mice with RGB don't fit professional/student/MS Surface laptops.
        if not is_gaming and not pool.empty:
            rgb_mask = pool['Title'].fillna('').str.contains(r'\brgb\b', case=False, regex=True, na=False)
            if rgb_mask.any():
                b4_rgb = len(pool)
                pool = pool[~rgb_mask]
                if b4_rgb > len(pool):
                    notes.append(f"🚫 Non-gaming: removed {b4_rgb - len(pool)} RGB-titled items")

        # ── Microsoft 2-in-1 slot 1/3 overrides: filter brand to MICROSOFT first ──
        if is_ms_2in1 and slot_num in (1, 3) and not pool.empty:
            ms_brand_mask = pool['Κατασκευαστής'].fillna('').astype(str).str.strip().str.upper() == 'MICROSOFT'
            if ms_brand_mask.any():
                pool = pool[ms_brand_mask]
                notes.append(f"🪟 Filtered to Microsoft brand: {len(pool)}")
            else:
                notes.append(f"⚠ No Microsoft-brand items in {hierarchies}")
 
        if pool.empty:
            notes.append("❌ Empty after dedup")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Empty"))
            continue
 
        # Base scoring
        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += AVAIL_BOOST * 100
        pool['Final_Score'] += pool['Sales_Tiebreaker'].fillna(0) * 0.1
 
        # ══════════════════════════════════════════════════════
        # SLOT-SPECIFIC LOGIC
        # ══════════════════════════════════════════════════════
 
        # ── Logic 1: Bag/Sleeve Size (Cinderella Fit) ──
        if logic_key in ('BAG_SIZE', 'SLEEVE_SIZE'):
            if tscreen > 0:
                size_col = None
                for candidate_col in ['Μέγεθος', 'Μέγεθος οθόνης']:
                    if candidate_col in pool.columns:
                        size_col = candidate_col
                        break
                if size_col:
                    pool['_acc_size'] = pool[size_col].apply(parse_screen_size)
                    
                    # Target 1: Strict fit (up to +0.8 inches larger)
                    strict_fit = pool[(pool['_acc_size'] >= tscreen - 0.2) & (pool['_acc_size'] <= tscreen + 0.8)]
                    if not strict_fit.empty:
                        pool = strict_fit
                        notes.append(f"Strict size fit {tscreen}\" (+0.8\"): {len(pool)}")
                    else:
                        # Target 2: Loose fit (up to +1.5 inches larger)
                        loose_fit = pool[(pool['_acc_size'] >= tscreen - 0.5) & (pool['_acc_size'] <= tscreen + 1.5)]
                        if not loose_fit.empty:
                            pool = loose_fit
                            notes.append(f"Loose size fit {tscreen}\" (+1.5\"): {len(pool)}")
                        else:
                            # Target 3: Only keep sizeless bags. Ban known wrong sizes!
                            sizeless = pool[pool['_acc_size'] == 0]
                            pool = sizeless
                            notes.append(f"⚠ No size match for {tscreen}\", keeping ONLY sizeless items")

            # ── Bag TYPE priority by size and persona ──
            # Big laptops (≥15") → Backpack (Πλάτης); gaming → Gaming-themed bags first;
            # small laptops (<14") → Sleeve; fallback → Shoulder (Ώμου-χειρός)
            if logic_key == 'BAG_SIZE' and 'Τύπος τσάντας' in pool.columns:
                btype = pool['Τύπος τσάντας'].fillna('').astype(str)
                is_backpack = btype.str.contains('Πλάτης|Backpack', case=False, regex=True, na=False)
                is_sleeve = btype.str.contains('Sleeve|Θήκη|Μανικ', case=False, regex=True, na=False)
                is_shoulder = btype.str.contains('Ώμου|Χειρός|Shoulder|Messenger|Hand', case=False, regex=True, na=False)
                is_gaming_bag = pool['Title'].fillna('').str.lower().str.contains(
                    r'gaming|razer|asus rog|rog ranger|rog backpack|msi\b|hp omen|lenovo legion|predator',
                    regex=True, na=False
                )

                if is_gaming:
                    # Gaming → gaming-themed first, then backpacks, then shoulder
                    pool.loc[is_gaming_bag, 'Final_Score'] += 250000
                    pool.loc[is_backpack & ~is_gaming_bag, 'Final_Score'] += 80000
                    pool.loc[is_shoulder & ~is_backpack & ~is_gaming_bag, 'Final_Score'] += 20000
                    notes.append(f"🎮 Gaming bag: Gaming+250k({is_gaming_bag.sum()}) / Backpack+80k({(is_backpack & ~is_gaming_bag).sum()})")
                elif tscreen and tscreen >= 15.0:
                    # Large laptop → Backpack first (Πλάτης), then Shoulder, then Sleeve
                    pool.loc[is_backpack, 'Final_Score'] += 200000
                    pool.loc[is_shoulder & ~is_backpack, 'Final_Score'] += 60000
                    pool.loc[is_sleeve & ~is_backpack & ~is_shoulder, 'Final_Score'] += 10000
                    notes.append(f"📏 Large ({tscreen}\"): Backpack+200k({is_backpack.sum()}) / Shoulder+60k")
                elif tscreen and tscreen < 14.0:
                    # Small laptop → Sleeve first, then Shoulder, then Backpack
                    pool.loc[is_sleeve, 'Final_Score'] += 200000
                    pool.loc[is_shoulder & ~is_sleeve, 'Final_Score'] += 60000
                    pool.loc[is_backpack & ~is_sleeve & ~is_shoulder, 'Final_Score'] += 20000
                    notes.append(f"📏 Small ({tscreen}\"): Sleeve+200k({is_sleeve.sum()}) / Shoulder+60k")
                else:
                    # Mid-size (14-15") or unknown → Shoulder first
                    pool.loc[is_shoulder, 'Final_Score'] += 150000
                    pool.loc[is_backpack, 'Final_Score'] += 100000
                    pool.loc[is_sleeve, 'Final_Score'] += 50000
                    notes.append("Mid-size: Shoulder-priority")

                # Mainstream usage also wants backpacks (student/commute)
                if 'mainstream' in tusage and not is_gaming:
                    pool.loc[is_backpack, 'Final_Score'] += 40000

            # FLAT-RATE BUDGET: Bags/sleeves are roughly static (€30-€80). Don't
            # show €200 leather sleeves with a €4k laptop — feels like upselling.
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)
            slot_role_key = 'BAG' if logic_key == 'BAG_SIZE' else 'SLEEVE'
            pool, trap_note = apply_cheap_trap(pool, tprice, slot_role_key)
            if trap_note: notes.append(trap_note)
            if laptop_tier > 0:
                bag_min, bag_max = get_accessory_budget(slot_role_key, laptop_tier)
                # Gaming bags legitimately run €50-€120 even on mid-tier laptops
                if is_gaming and logic_key == 'BAG_SIZE':
                    bag_max = max(bag_max, 120)
                in_band = (pool['_p'] >= bag_min) & (pool['_p'] <= bag_max)
                pool.loc[in_band, 'Final_Score'] += 40000
                notes.append(f"Flat budget: Boost €{bag_min:.0f}–€{bag_max:.0f} {slot_role_key.lower()}s")
 
        # ── Logic 2: Charger Port Compatibility (Brand+Port = Top Priority) ──
        elif logic_key == 'CHARGER_PORT':
            # Apple & Microsoft Surface imply USB-C/PD even if the Ports column is empty.
            has_usbc = is_apple or is_surface or any(k in tports for k in ['usb-c', 'type-c', 'usb c', 'thunderbolt', 'usb 4'])
            has_dcin_only = 'dc' in tports and not has_usbc

            # ── ALWAYS-ON #1: Wattage filter (laptop chargers are ≥45W period) ──
            # This fires regardless of port detection — a <45W brick is a phone
            # charger, wrong tool for any laptop.
            watts = pool['Title'].fillna('').apply(extract_wattage_from_text)
            pool.loc[watts >= 45, 'Final_Score'] += 50000
            pool.loc[(watts > 0) & (watts < 45), 'Final_Score'] -= 20000
            notes.append("≥45W boost, <45W deprioritized (always-on)")

            # ── ALWAYS-ON #2: Brand match (fires even with no port info) ──
            # Rationale: if the user's laptop is a Microsoft Surface and a
            # Microsoft charger exists in the catalog, it should beat Hama even
            # if the Ports column is incomplete. Brand = correct connector by
            # construction.
            if tb:
                is_same_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                same_brand_laptop_watt = is_same_brand & (watts >= 45)
                pool.loc[same_brand_laptop_watt, 'Final_Score'] += 200000
                if same_brand_laptop_watt.any():
                    notes.append(f"Brand match (always-on): {tb} ≥45W → +200k, {same_brand_laptop_watt.sum()} items")

            if has_usbc:
                usbc_mask = pool['Title'].fillna('').str.lower().str.contains('usb-c|type-c|usb c|pd|power delivery', regex=True, na=False)
                if 'Υποδοχές' in pool.columns:
                    usbc_mask |= pool['Υποδοχές'].fillna('').astype(str).str.lower().str.contains('usb-c|type-c', regex=True, na=False)
                pool.loc[usbc_mask, 'Final_Score'] += 100000
                trig_label = "USB-C trigger" if not is_surface else "Surface (implicit USB-C)"
                notes.append(f"{trig_label} → USB-C charger boost")

                # ⭐ TOP PRIORITY: Same-brand charger AND matching port AND ≥45W
                if tb:
                    is_same_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                    brand_port_match = is_same_brand & usbc_mask & (watts >= 45)
                    pool.loc[brand_port_match, 'Final_Score'] += 500000
                    if brand_port_match.any():
                        notes.append(f"⭐ TOP: Same-brand ({tb}) + USB-C + ≥45W → {brand_port_match.sum()} items")

                # Brand Ecosystem fallback for chargers
                if is_apple:
                    # 🍎 STRICT: Apple laptops get Apple chargers ONLY.
                    apple_mask = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'APPLE'
                    if apple_mask.any():
                        b4 = len(pool)
                        pool = pool[apple_mask].copy()
                        notes.append(f"🍎 Apple-only charger filter: {b4}→{len(pool)}")
                    else:
                        # No Apple chargers in catalog → boost premium PD brands
                        # (Anker/Belkin/UGREEN are what Apple Store stocks as 3rd-party)
                        premium_pd = pool['Κατασκευαστής'].fillna('').str.upper().isin(['ANKER', 'BELKIN', 'UGREEN'])
                        pool.loc[premium_pd & usbc_mask, 'Final_Score'] += 80000
                        notes.append("⚠ No Apple chargers in catalog → fallback: premium PD brands boosted +80k")

            elif has_dcin_only:
                universal = pool['Title'].fillna('').str.lower().str.contains('universal|γενικής|πολλαπλ', regex=True, na=False)
                pool.loc[universal, 'Final_Score'] += 50000
                notes.append("DC-in → Universal charger boost")

                # ⭐ Same-brand DC charger wins if available
                if tb:
                    is_same_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                    dc_mask = pool['Title'].fillna('').str.lower().str.contains('dc|barrel|τροφοδοτικό', regex=True, na=False)
                    brand_dc_match = is_same_brand & (dc_mask | universal)
                    pool.loc[brand_dc_match, 'Final_Score'] += 500000
                    if brand_dc_match.any():
                        notes.append(f"⭐ TOP: Same-brand ({tb}) DC charger → {brand_dc_match.sum()} items")
            else:
                notes.append("⚠ No port info detected → relying on brand+wattage only")
 
        # ── Logic: High-Wattage Powerbank ──
        elif logic_key == 'HIGH_WATT_PB':
            watts = pool['Title'].fillna('').apply(extract_wattage_from_text)
            high = pool[watts >= 45]
            if not high.empty:
                pool = high
                notes.append(f"Laptop PD (≥45W): {len(pool)}")
            else:
                pd_mask = pool['Title'].fillna('').str.lower().str.contains('pd|power delivery|laptop', regex=True, na=False)
                if pd_mask.any():
                    pool = pool[pd_mask]
                    notes.append(f"PD fallback: {len(pool)}")
                else:
                    notes.append("⚠ No ≥45W or PD powerbanks, keeping all")
 

        # ── Logic: Smart Mouse Selection (Performance Pairing — Tier-Driven) ──
        elif logic_key == 'MOUSE_LOGIC':
            if not is_gaming:
                not_gaming_mask = ~pool['Title'].fillna('').str.lower().str.contains('rgb|gaming', regex=True, na=False)
                pool, note = filter_or_penalize(pool, not_gaming_mask, "Persona: Exclude gaming/RGB mice")
                notes.append(note)
            else:
                # 🎮 GAMING LAPTOP: actively BOOST gaming mice (high-DPI sensors,
                # low-latency wireless). Just not excluding them is not enough to
                # win on sales volume vs. office mice.
                gaming_mask = pool['Title'].fillna('').str.lower().str.contains(
                    r'gaming|rgb|razer|logitech g\b|logitech g\d|g pro|g305|g502|viper|deathadder|basilisk|corsair|steelseries|hyperx|glorious|asus rog|rog gladius',
                    regex=True, na=False
                )
                pool.loc[gaming_mask, 'Final_Score'] += 200000
                notes.append(f"🎮 Gaming: Boosted gaming mice +200k ({gaming_mask.sum()} items)")

            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)

            # Cheap-trap: no <€30 mice on ≥€800 laptops
            pool, trap_note = apply_cheap_trap(pool, tprice, 'MOUSE')
            if trap_note: notes.append(trap_note)

            # Tier-based budget boost (the 20% rule, mouse = 25% of bundle)
            mouse_min, mouse_max = get_accessory_budget('MOUSE', laptop_tier)
            if laptop_tier > 0:
                in_band = (pool['_p'] >= mouse_min) & (pool['_p'] <= mouse_max)
                # Boost raised to 150k so it beats the ecosystem +100k
                pool.loc[in_band, 'Final_Score'] += 150000

                # ANTI-OVERBUY: a €150 mouse on a €798 laptop feels like upselling
                overbuy_threshold = mouse_max * 2.0
                pool.loc[pool['_p'] > overbuy_threshold, 'Final_Score'] -= 250000

                # Tier 4 anti-cheap-trap penalty (don't pair €15 mouse with €4k laptop)
                if laptop_tier == 4:
                    pool.loc[pool['_p'] < mouse_min * 0.5, 'Final_Score'] -= 100000
                notes.append(f"Tier {laptop_tier} ({tier_label}): Boost €{mouse_min:.0f}–€{mouse_max:.0f} (+150k), overbuy >€{overbuy_threshold:.0f} (-250k)")

            # Apple ecosystem: HARD FILTER to Magic Mouse or explicitly Mac-compatible mice.
            # User rule: Apple laptop → only show Magic Mouse or mice that say "for Mac"/"για Mac".
            if is_apple:
                apple_mice = pool['Κατασκευαστής'].fillna('').str.upper() == 'APPLE'
                mac_title = pool['Title'].fillna('').str.lower().str.contains(
                    r'για mac|for mac|mac edition|magic mouse',
                    regex=True, na=False
                )
                mac_compatible = apple_mice | mac_title
                if mac_compatible.any():
                    b4 = len(pool)
                    pool = pool[mac_compatible].copy()
                    notes.append(f"🍎 Apple-only mouse filter: Magic Mouse OR 'for Mac': {b4}→{len(pool)}")
                    
                    # ========================================================
                    # NEW: Peripheral Color Match for Apple Mice
                    # ========================================================
                    color_match_found = False # Track if we found a matching color
                    tlaptop_color = str(trigger.get('Χρώμα', '')).strip()
                    
                    # Fallback: Extract color from title if column is empty
                    if not tlaptop_color:
                        color_matches = re.search(r'\b(silver|space gray|space grey|midnight|starlight|gold|rose gold|indigo|black|white|μαύρο|λευκό|γκρι|ασημί)\b', _tt_lower)
                        if color_matches: tlaptop_color = color_matches.group(1)

                    if tlaptop_color and tlaptop_color.lower() not in ('nan', 'n/a', '', 'none'):
                        t_col_upper = tlaptop_color.upper()
                        synonyms = [t_col_upper]
                        
                        if t_col_upper in ['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'GREY', 'GRAY', 'ΓΚΡΙ', 'SPACE GRAY', 'SPACE GREY']:
                            synonyms.extend(['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'ΓΚΡΙ', 'GREY', 'GRAY'])
                        elif t_col_upper in ['BLACK', 'ΜΑΥΡΟ', 'MIDNIGHT']:
                            synonyms.extend(['BLACK', 'ΜΑΥΡΟ', 'MIDNIGHT'])
                        elif t_col_upper in ['WHITE', 'ΛΕΥΚΟ', 'ΑΣΠΡΟ', 'PALE GREY', 'STARLIGHT', 'SILVER', 'ΑΣΗΜΙ']:
                            synonyms.extend(['WHITE', 'ΛΕΥΚΟ', 'PALE GREY', 'SILVER', 'ΑΣΗΜΙ'])
                        elif t_col_upper in ['ROSE', 'ΡΟΖ', 'PINK', 'ROSE GOLD']:
                            synonyms.extend(['ROSE', 'ΡΟΖ', 'PINK'])
                        elif t_col_upper in ['BLUE', 'ΜΠΛΕ', 'INDIGO']:
                            synonyms.extend(['BLUE', 'ΜΠΛΕ', 'INDIGO'])
                        
                        if 'Χρώμα' in pool.columns:
                            attr_match = pool['Χρώμα'].fillna('').astype(str).str.strip().str.upper().isin(synonyms)
                            title_match = pool['Title'].fillna('').str.upper().str.contains('|'.join(synonyms), regex=True, na=False)
                            color_hit = attr_match | title_match
                            if color_hit.any():
                                pool.loc[color_hit, 'Final_Score'] += 150000
                                color_match_found = True
                                notes.append(f"🎨 Mouse Color match ({tlaptop_color}): +150k to {color_hit.sum()} Mac mice")
                    
                    # FIX: Premium Fallback if color match fails
                    if not color_match_found:
                        premium_mice = pool['Κατασκευαστής'].fillna('').str.strip().str.upper().isin(['LOGITECH', 'APPLE'])
                        pool.loc[premium_mice, 'Final_Score'] += 80000
                        notes.append(f"🍎 Premium mouse fallback: Boosted {premium_mice.sum()} Apple/Logitech mice (+80k)")
                    # ========================================================
                else:
                    notes.append("⚠ No Magic Mouse / Mac-compatible mouse in catalog — falling back to all")
            # Microsoft Surface ecosystem — mirror the Apple pattern
            elif is_surface:
                # Match by brand OR by title (Surface Arc, Microsoft Designer, Sculpt)
                ms_mice = (pool['Κατασκευαστής'].fillna('').str.upper() == 'MICROSOFT') | \
                          pool['Title'].fillna('').str.lower().str.contains(
                              r'microsoft|surface (arc|mobile|precision)|designer mouse|sculpt ergonomic',
                              regex=True, na=False
                          )
                if ms_mice.any():
                    if tprice >= 1200:
                        pool.loc[ms_mice, 'Final_Score'] += 100000
                        notes.append(f"🪟 Surface Ecosystem (premium): Microsoft mice boosted +100k ({ms_mice.sum()} items)")
                    else:
                        pool.loc[ms_mice, 'Final_Score'] += 50000
                        notes.append(f"🪟 Surface Ecosystem: Microsoft mice boosted +50k ({ms_mice.sum()} items)")
                else:
                    notes.append("🪟 Surface: No Microsoft mice in pool — no boost applied")

       # ── Logic: Smart Mousepad (FLAT RATE — does NOT scale with laptop price) ──
            elif logic_key == 'MOUSEPAD_LOGIC':
                
                # ========================================================
                # FIX 1: Ban ugly Gel/Wrist pads from the main mousepad slot
                # ========================================================
                gel_mask = pool['Title'].fillna('').str.contains(r'Gel|Wrist|Καρπού|Μαξιλαράκι', case=False, regex=True, na=False)
                pool, gel_note = filter_or_penalize(pool, ~gel_mask, "Aesthetics: Exclude Gel/Wrist pads")
                notes.append(gel_note)

                if not is_gaming:
                    not_gaming_mask = ~pool['Title'].fillna('').str.lower().str.contains('rgb|gaming', regex=True, na=False)
                    pool, note = filter_or_penalize(pool, not_gaming_mask, "Persona: Exclude gaming/RGB pads")
                    notes.append(note)

                pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)

                if is_gaming:
                    # 🎮 GAMING LAPTOP: boost XL/gaming pads, relax the €30 cap (XL pads run €25-50)
                    gaming_mask = pool['Title'].fillna('').str.lower().str.contains(
                        r'gaming|rgb|xl|xxl|qck|mm\d|razer goliathus|corsair mm|steelseries|hyperx|glorious|logitech g',
                        regex=True, na=False
                    )
                    pool.loc[gaming_mask, 'Final_Score'] += 200000
                    # For gaming: boost €15-€45 (covers XL/gaming range)
                    pool.loc[(pool['_p'] >= 15) & (pool['_p'] <= 45), 'Final_Score'] += 50000
                    notes.append(f"🎮 Gaming: Boosted gaming/XL pads +200k ({gaming_mask.sum()} items), price band €15-€45")
                else:
                    # FLAT RATE: A €15-€25 desk mat is sufficient for ANY setup.
                    mp_min, mp_max = get_accessory_budget('MOUSEPAD', laptop_tier or 1)
                    in_band = (pool['_p'] >= mp_min) & (pool['_p'] <= mp_max)
                    pool.loc[in_band, 'Final_Score'] += 50000
                    # Hard cap: penalise anything above €30 regardless of laptop price
                    pool.loc[pool['_p'] > 30, 'Final_Score'] -= 80000
                    notes.append(f"Flat Rate: Boost €{mp_min:.0f}–€{mp_max:.0f}, penalty >€30 (anti-gouging)")

                # ========================================================
                # NEW: Peripheral Color Match & Premium Brand Fallback (Apple Focus)
                # ========================================================
                color_match_found = False
                
                if is_apple:
                    tlaptop_color = str(trigger.get('Χρώμα', '')).strip()
                    if not tlaptop_color:
                        color_matches = re.search(r'\b(silver|space gray|space grey|midnight|starlight|gold|rose gold|indigo|black|white|μαύρο|λευκό|γκρι|ασημί)\b', _tt_lower)
                        if color_matches: tlaptop_color = color_matches.group(1)

                    if tlaptop_color and tlaptop_color.lower() not in ('nan', 'n/a', '', 'none'):
                        t_col_upper = tlaptop_color.upper()
                        synonyms = [t_col_upper]
                        
                        if t_col_upper in ['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'GREY', 'GRAY', 'ΓΚΡΙ', 'SPACE GRAY', 'SPACE GREY']:
                            synonyms.extend(['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'ΓΚΡΙ', 'GREY', 'GRAY'])
                        elif t_col_upper in ['BLACK', 'ΜΑΥΡΟ', 'MIDNIGHT']:
                            synonyms.extend(['BLACK', 'ΜΑΥΡΟ', 'MIDNIGHT'])
                        elif t_col_upper in ['WHITE', 'ΛΕΥΚΟ', 'ΑΣΠΡΟ', 'PALE GREY', 'STARLIGHT', 'SILVER', 'ΑΣΗΜΙ']:
                            synonyms.extend(['WHITE', 'ΛΕΥΚΟ', 'PALE GREY', 'SILVER', 'ΑΣΗΜΙ'])
                        elif t_col_upper in ['ROSE', 'ΡΟΖ', 'PINK', 'ROSE GOLD']:
                            synonyms.extend(['ROSE', 'ΡΟΖ', 'PINK'])
                        elif t_col_upper in ['BLUE', 'ΜΠΛΕ', 'INDIGO']:
                            synonyms.extend(['BLUE', 'ΜΠΛΕ', 'INDIGO'])
                        
                        if 'Χρώμα' in pool.columns:
                            attr_match = pool['Χρώμα'].fillna('').astype(str).str.strip().str.upper().isin(synonyms)
                            title_match = pool['Title'].fillna('').str.upper().str.contains('|'.join(synonyms), regex=True, na=False)
                            color_hit = attr_match | title_match
                            
                            # Ensure the color match isn't an ugly wrist pad that somehow slipped through
                            color_hit = color_hit & ~gel_mask
                            
                            if color_hit.any():
                                # Overrides the flat rate price bands so the colored pad wins
                                pool.loc[color_hit, 'Final_Score'] += 150000
                                color_match_found = True
                                notes.append(f"🎨 Pad Color match ({tlaptop_color}): +150k to {color_hit.sum()} mousepads")
                
                # FIX 2: If we are Apple/Premium and no color match was found, boost Logitech pads
                # so a nice Grey Studio Mat wins instead of a generic €5 pad.
                if not color_match_found and (is_apple or laptop_tier >= 3) and not is_gaming:
                    logi_pads = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'LOGITECH'
                    pool.loc[logi_pads, 'Final_Score'] += 80000
                    notes.append(f"🍎 Premium pad fallback: Boosted {logi_pads.sum()} Logitech pads (+80k)")
                # ========================================================

        # ── Logic: Persona-Driven Monitor (20-25% of Laptop Value) ──
        elif logic_key == 'MONITOR_LOGIC':

            # ── HARD FILTER: Always >= 27" ──
            pool['_mon_size'] = 0.0
            for col in ['Μέγεθος οθόνης', 'Ιντσες', 'Μέγεθος']:
                if col in pool.columns:
                    pool['_mon_size'] = pool[col].apply(parse_screen_size)
                    break
            
            def safe_monitor_size(title):
                s = str(title).lower()
                m = re.search(r'(\d{2}\.?\d*)\s*(?:"|\'\'|inch|ιντσ|-inch)', s)
                if m: return float(m.group(1))
                return 0.0
                
            zero_mask = pool['_mon_size'] == 0
            if zero_mask.any():
                pool.loc[zero_mask, '_mon_size'] = pool.loc[zero_mask, 'Title'].apply(safe_monitor_size)
                
            b4_size = len(pool)
            pool = pool[pool['_mon_size'] >= 27.0]
            notes.append(f"📏 Size filter: Monitors >= 27\" only ({b4_size}→{len(pool)})")

            # ── Req 8: Match laptop Προτεινόμενη χρήση ↔ monitor Χρήση ──
            # Gaming laptop → Gaming monitor. Επαγγελματική → Business. Mainstream → Mainstream.
            # Non-gaming laptop → HARD EXCLUDE Χρήση=Gaming.
            if 'Χρήση' in pool.columns:
                mon_usage = pool['Χρήση'].fillna('').astype(str).str.lower()

                # Determine target usage from laptop tusage (already lowercased above)
                if is_gaming:
                    matching_use = mon_usage.str.contains('gaming', regex=False, na=False)
                    # Hard boost for matching use
                    pool.loc[matching_use, 'Final_Score'] += 200000
                    notes.append(f"🎯 Χρήση match (Gaming): +200k to {matching_use.sum()} monitors")
                elif 'επαγγελματική' in tusage or 'premium' in tusage:
                    matching_use = mon_usage.str.contains('business|επαγγελ', regex=True, na=False)
                    # Non-gaming: hard-exclude gaming monitors
                    gaming_use = mon_usage.str.contains('gaming', regex=False, na=False)
                    if (~gaming_use).any():
                        b4 = len(pool)
                        pool = pool[~gaming_use]
                        mon_usage = pool['Χρήση'].fillna('').astype(str).str.lower()
                        matching_use = mon_usage.str.contains('business|επαγγελ', regex=True, na=False)
                        notes.append(f"🚫 Χρήση=Gaming excluded: {b4}→{len(pool)}")
                    pool.loc[matching_use, 'Final_Score'] += 150000
                    notes.append(f"🎯 Χρήση match (Business/Επαγγελματική): +150k to {matching_use.sum()}")
                elif 'mainstream' in tusage or 'καθημερινή' in tusage:
                    matching_use = mon_usage.str.contains('mainstream|καθημερινή', regex=True, na=False)
                    # Non-gaming: hard-exclude gaming monitors
                    gaming_use = mon_usage.str.contains('gaming', regex=False, na=False)
                    if (~gaming_use).any():
                        b4 = len(pool)
                        pool = pool[~gaming_use]
                        mon_usage = pool['Χρήση'].fillna('').astype(str).str.lower()
                        matching_use = mon_usage.str.contains('mainstream|καθημερινή', regex=True, na=False)
                        notes.append(f"🚫 Χρήση=Gaming excluded: {b4}→{len(pool)}")
                    pool.loc[matching_use, 'Final_Score'] += 150000
                    notes.append(f"🎯 Χρήση match (Mainstream): +150k to {matching_use.sum()}")
                else:
                    # Unknown usage → still exclude gaming monitors unless the laptop is gaming
                    gaming_use = mon_usage.str.contains('gaming', regex=False, na=False)
                    if gaming_use.any() and (~gaming_use).any():
                        b4 = len(pool)
                        pool = pool[~gaming_use]
                        notes.append(f"🚫 Non-gaming laptop: Χρήση=Gaming excluded: {b4}→{len(pool)}")

            # Fallback for items without Χρήση attribute: title-based check
            if not is_gaming:
                gaming_mon = pool['Title'].fillna('').str.lower().str.contains('gaming|odyssey|predator|144hz|165hz|180hz|240hz', regex=True, na=False)
                pool, note = filter_or_penalize(pool, ~gaming_mon, "Non-gaming: Exclude gaming-branded monitors (title)")
                notes.append(note)
            else:
                gaming_mon_mask = pool['Title'].fillna('').str.lower().str.contains(
                    r'gaming|odyssey|predator|aorus|rog swift|rog strix|ultragear|nitro|mag\b|viewsonic elite',
                    regex=True, na=False
                )
                pool.loc[gaming_mon_mask, 'Final_Score'] += 200000
                notes.append(f"🎮 Gaming: Boosted gaming-branded monitors +200k ({gaming_mon_mask.sum()} items)")

            if tres_tier > 0:
                pool['_res_tier'] = pool['Ανάλυση Οθόνης'].apply(get_resolution_tier)
                keep = (pool['_res_tier'] >= tres_tier) | (pool['_res_tier'] == 0)
                pool, note = filter_or_penalize(pool, keep, f"Resolution ≥ tier {tres_tier}")
                notes.append(note)

            if (is_apple or is_premium) and laptop_tier >= 3:
                fhd_mon = pool['Title'].fillna('').str.lower().str.contains('fhd|1080p|1920x1080', regex=True, na=False)
                pool, note = filter_or_penalize(pool, ~fhd_mon, "Tier 3+ premium: Exclude FHD monitors")
                notes.append(note)

            # ── Req 7: Monitor budget = 20-25% of laptop price (replaces tier-based budget) ──
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)
            apple_monitors = pool['Κατασκευαστής'].fillna('').str.upper() == 'APPLE'

            pool, trap_note = apply_cheap_trap(pool, tprice, 'MONITOR')
            if trap_note: notes.append(trap_note)

            if tprice > 0:
                mon_min = tprice * 0.20
                mon_max = tprice * 0.25
                # Widen sweet-spot band slightly to ±5% around the 20-25% range so the
                # in-band pool isn't too tiny for budget laptops. Sweet spot is 15-30%.
                sweet_min = tprice * 0.15
                sweet_max = tprice * 0.30
                in_sweet = (pool['_p'] >= sweet_min) & (pool['_p'] <= sweet_max)
                in_band  = (pool['_p'] >= mon_min) & (pool['_p'] <= mon_max)
                pool.loc[in_sweet, 'Final_Score'] += 100000
                pool.loc[in_band, 'Final_Score'] += 100000  # stacks → 200k for the 20-25% core
                # Overbuy penalty: monitor >50% of laptop price
                overbuy_threshold = tprice * 0.50
                pool.loc[pool['_p'] > overbuy_threshold, 'Final_Score'] -= 250000
                # Cheap penalty for high-tier laptops only
                if laptop_tier >= 3:
                    pool.loc[pool['_p'] < sweet_min * 0.5, 'Final_Score'] -= 100000
                notes.append(f"💶 Monitor budget 20-25% of €{tprice:.0f}: €{mon_min:.0f}-€{mon_max:.0f} (+200k sweet, overbuy >€{overbuy_threshold:.0f} -250k)")

            # High-refresh boost for gaming / Tier 3+
            if laptop_tier >= 3 or is_gaming:
                high_refresh = pool['Title'].fillna('').str.lower().str.contains('144hz|165hz|180hz|240hz|360hz', regex=True, na=False)
                pool.loc[high_refresh, 'Final_Score'] += 30000
                notes.append("High-refresh boost (≥144Hz) — match GPU performance")

            # ── Retina laptop → premium panel technology only (HARD FILTER) ──
            # A Retina MacBook is a color-accurate device. Pairing it with a generic TN (terrible colors)
            # or VA (color shifting) panel undermines the quality. Allow only the BEST premium panels.
            GOOD_PANEL_PAT = r'\bips\b|\boled\b|\bamoled\b|\bqd-oled\b|nano\s*ips|\bretina\b|\bads\b|micro\s*led|mini\s*led'
            
            if trigger_is_retina:
                tech_mask = pd.Series(False, index=pool.index)
                if 'Τεχνολογία Οθόνης' in pool.columns:
                    tech_mask = pool['Τεχνολογία Οθόνης'].fillna('').astype(str).str.lower().str.contains(GOOD_PANEL_PAT, regex=True, na=
