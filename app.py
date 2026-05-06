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
        🟢 Engine v25 — Tablets
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
# 🟢 TABLETS CONFIGURATION
# ═════════════════════════════════════════════════════════════

# Tablet-specific data and slot definitions. Tune values here.
 
# ────────────────────────────────────────────────────────────
# Brand / persona constants
# ────────────────────────────────────────────────────────────
TABLET_PREMIUM_BRANDS = {'APPLE', 'SAMSUNG', 'HUAWEI', 'XIAOMI', 'MICROSOFT'}
 
 
# ────────────────────────────────────────────────────────────
# Score weights (higher = stronger preference)
# ────────────────────────────────────────────────────────────
S_BRAND_BOOST       = 100_000   # always-on for trigger-brand match
S_BRAND_STRONG      = 500_000   # for slots where brand is the primary signal
S_MODEL_MATCH       = 500_000   # accessory's compat field contains trigger model
S_CATEGORY_TARGET   = 400_000   # slot's targeted Κατηγορία / Είδος
S_CATEGORY_REPEAT   = -600_000  # already-shown category penalty
S_PORT_MATCH        = 300_000   # Θύρα USB / Σύνδεση direct match
S_PORT_MISMATCH     = -300_000  # explicit port wrong (USB-A flash on Type-C iPad)
S_BLUETOOTH_REQ     = 400_000   # Bluetooth required (iPad mouse/keyboard)
S_USB_RECEIVER_PEN  = -700_000  # USB-receiver mouse on iPad → broken
S_WATTAGE_TIER      = 250_000   # charger wattage matches tablet tier
S_CASE_TYPE_PRIMARY = 250_000   # Folio for premium / Back Cover for standard
S_COLOR_EXACT       = 200_000   # Χρώμα contains a trigger color token
S_COLOR_TRANSPARENT = 80_000    # transparent fallback
S_SIZE_MATCH        = 300_000   # NB-bag size band overlaps tablet screen size
S_TOUCHPAD_BOOST    = 150_000   # premium tablet → touchpad keyboard
S_HIERARCHY_TARGET  = 200_000   # slot prefers a specific hierarchy when multiple allowed
S_PRICE_PENALTY     = -200_000  # exceeds budget cap × 1.5
S_OTG_BONUS         = 100_000   # adapter compat
S_AIRPODS_BOOST     = 400_000   # iPad Bluetooth slot → AirPods
S_MAGIC_MOUSE_BOOST = 600_000   # iPad mouse slot → Magic Mouse
S_UNBRANDED_STYLUS  = 50_000    # generic stylus preferred over branded for non-Apple
 
 
# ────────────────────────────────────────────────────────────
# Budget caps per tier × role group
# ────────────────────────────────────────────────────────────
TABLET_ACCESSORY_BUDGET = {
    'Premium': {'audio': 400, 'power': 100, 'case': 150, 'default': 300},
    'High':    {'audio': 250, 'power':  60, 'case': 100, 'default': 200},
    'Mid':     {'audio': 120, 'power':  35, 'case':  60, 'default': 100},
    'Entry':   {'audio':  60, 'power':  25, 'case':  35, 'default':  60},
}
 
 
# ────────────────────────────────────────────────────────────
# Marketing copy per slot role
# ────────────────────────────────────────────────────────────
TABLET_MARKETING_COPY = {
    # Standard / Premium path
    'Keyboard Case':        'Μεταμόρφωσε το tablet σε laptop.',
    'Tablet Bag':           'Ασφαλής μεταφορά παντού.',
    'NB Bag':               'Χωρητική θήκη laptop-style.',
    'Wall Charger':         'Γρήγορη φόρτιση κάθε στιγμή.',
    'Cable':                'Ανθεκτικό καλώδιο για καθημερινή χρήση.',
    'Bluetooth':            'Ασύρματος ήχος χωρίς συμβιβασμούς.',
    'Wireless Keyboard':    'Πληκτρολόγησε άνετα από παντού.',
    'Wireless Mouse':       'Ακρίβεια χωρίς καλώδια.',
    'Screen Protector':     'Προστασία οθόνης χωρίς συμβιβασμούς.',
    'Overhead':             'Καθηλωτικός ήχος over-ear.',
    'Smartwatch':           'Όλες οι ειδοποιήσεις στον καρπό σου.',
    'Stylus':               'Ακρίβεια για σημειώσεις & σχέδιο.',
    'Storage':              'Επέκτεινε τον αποθηκευτικό σου χώρο.',
    # iPad path
    'Apple Pencil':         'Ακρίβεια Apple για κάθε ιδέα.',
    'Smart Folio':          'Λεπτή προστασία, στιβαρή στήριξη.',
    'Apple Keyboard':       'Πληκτρολόγησε σαν σε laptop.',
    'Apple Other':          'Γνήσιο αξεσουάρ Apple.',
    'Apple Wall Charger':   'Original Apple φόρτιση.',
    'Apple Cable':          'Γνήσιο καλώδιο Apple.',
    'AirPods':              'Ο ασύρματος ήχος της Apple.',
    'Apple Watch':          'Συμπλήρωσε το Apple οικοσύστημα.',
    'USB Storage':          'Επέκτεινε τον αποθηκευτικό σου χώρο.',
    # Kiddoboo path
    'Party Speaker':        'Ξεσήκωσε το πάρτι.',
    'Action Camera':        'Κατέγραψε κάθε περιπέτεια.',
    'Smartphone':           'Πρώτο κινητό για μικρούς εξερευνητές.',
    'Travel/Scooter':       'Έξω από το σπίτι, σε κίνηση.',
}
 
 
# ────────────────────────────────────────────────────────────
# Wattage tier preferences per tablet tier
# Values match the exact strings in WALL CHARGERS.Ισχύς (Watt)
# ────────────────────────────────────────────────────────────
WATTAGE_TIER_PREFS = {
    'Premium': ['21 - 60 Watt', '61 - 100 Watt'],
    'High':    ['21 - 60 Watt', 'Έως 20 Watt'],
    'Mid':     ['Έως 20 Watt', '21 - 60 Watt'],
    'Entry':   ['Έως 20 Watt'],
}
 
 
# ────────────────────────────────────────────────────────────
# Color tokens treated as "transparent / clear" fallbacks
# ────────────────────────────────────────────────────────────
TRANSPARENT_TOKENS = {'διάφανο', 'διαφανο', 'διαφανής', 'διαφανες',
                      'transparent', 'clear', 'διάφανο;μαύρο'}
 
 
# ────────────────────────────────────────────────────────────
# Apple Original categorization (uses structured fields only)
# Maps a row from APPLE ORIGINAL TABLET ACCESSORIES / TABLET BAGS to a
# coarse category: Stylus, Keyboard, Folio, Adapter, Charger, Cable,
# Wireless Charger, Audio Adapter, Other.
# ────────────────────────────────────────────────────────────
def _apple_orig_categorize(row):
    def get(col_name):
        c = None
        for k in row.index:
            if _norm_col_name(k) == _norm_col_name(col_name):
                c = k
                break
        return str(row[c]).strip() if c is not None else ''
 
    katigoria = get('Κατηγορία').lower()
    eidos_kbd = get('Είδος πληκτρολογίου').lower()
    typos_dev = get('Τύπος συσκευής').lower()
    typos3    = get('Τύπος3').lower()
    ypod      = get('Υποδοχές').lower()
    typhikis  = get('Τύπος Θήκης').lower()
    brand_dev = get('Brand συσκευής σου').lower()
 
    if 'γραφίδα' in typos_dev or 'γραφιδα' in typos_dev:
        return 'Stylus'
    if 'magic keyboard' in eidos_kbd or 'smart keyboard' in eidos_kbd:
        return 'Keyboard'
    if 'πληκτρολόγια' in katigoria or 'πληκτρολογια' in katigoria:
        return 'Keyboard'
    if typhikis in ('back cover', 'book cover', 'folio'):
        return 'Folio'
    if 'αντάπτορ' in katigoria or 'αντάπτορ' in typos3 or 'adapter' in typos3:
        return 'Adapter'
    if 'φορτιστής πρίζας' in typos3 or 'φορτιστης πριζας' in typos3:
        return 'Charger'
    if 'καλώδιο' in typos3 or 'καλωδιο' in typos3:
        return 'Cable'
    if 'ασύρματος φορτιστής' in typos3:
        return 'Wireless Charger'
    if 'αντάπτορας ήχου' in typos3:
        return 'Audio Adapter'
    if brand_dev:  # Apple Original Tablet Bags entries
        return 'Folio'
    return 'Other'
 
 
# ────────────────────────────────────────────────────────────
# Slot builders — one per persona
# Tuple shape: (slot_num_placeholder, role_label, [hierarchies], logic_key)
# Slot numbers are stamped at the end via _renumber().
# ────────────────────────────────────────────────────────────
 
def _build_kiddoboo_slots():
    return [
        (None, 'Overhead',         ['OVERHEAD'],                          'GENERIC'),
        (None, 'Smartwatch',       ['SMART WATCHES', 'ACTIVITY TRACKER'], 'GENERIC'),
        (None, 'Wall Charger',     ['WALL CHARGERS'],                     'CHARGER_FIT'),
        (None, 'Cable',            ['ΚΑΛΩΔΙΑ ΔΕΔΟΜΕΝΩΝ', 'USB CABLES'],   'CABLE_FIT'),
        (None, 'Party Speaker',    ['ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ'],                'GENERIC'),
        (None, 'Action Camera',    ['IP CAMERAS', 'TRAVEL ACCESSORIES'],  'GENERIC'),
        (None, 'Smartphone',       ['Smartphones'],                       'GENERIC'),
        (None, 'Travel/Scooter',   ['TRAVEL ACCESSORIES'],                'GENERIC'),
        (None, 'Bluetooth',        ['Bluetooth'],                         'GENERIC'),
        (None, 'Screen Protector', ['MOBILE SCREEN PROTECTORS'],          'SCREEN_PROTECTOR_FIT'),
    ]
 
 
def _build_apple_ipad_slots():
    """First 4 slots target distinct Apple Original categories so the iPad
    gets diverse picks (Pencil → Folio → Keyboard → Other) instead of 4 styluses."""
    APPLE_ORIG = ['APPLE ORIGINAL TABLET ACCESSORIES', 'APPLE ORIGINAL TABLET BAGS']
    APPLE_PSU  = ['APPLE ORIGINAL POWER SUPPLY',
                  'APPLE ORIGINAL IPHONE CABLE-ADAPTORS',
                  'APPLE ORIGINAL IPHONE CABLE-ADA',  # truncated sheet name variant
                  'WALL CHARGERS']
    APPLE_CBL  = ['APPLE ORIGINAL IPHONE CABLE-ADAPTORS',
                  'APPLE ORIGINAL IPHONE CABLE-ADA',
                  'ΚΑΛΩΔΙΑ ΔΕΔΟΜΕΝΩΝ']
    return [
        (None, 'Apple Pencil',       APPLE_ORIG,         'APPLE_TARGET:Stylus'),
        (None, 'Smart Folio',        APPLE_ORIG,         'APPLE_TARGET:Folio'),
        (None, 'Apple Keyboard',     APPLE_ORIG,         'APPLE_TARGET_STRICT:Keyboard'),
        (None, 'Apple Other',        APPLE_ORIG,         'APPLE_TARGET:Adapter,Other'),
        (None, 'Apple Wall Charger', APPLE_PSU,          'APPLE_CHARGER_FIT'),
        (None, 'Apple Cable',        APPLE_CBL,          'APPLE_CABLE_FIT'),
        (None, 'AirPods',            ['Bluetooth'],      'AIRPODS_BOOST'),
        (None, 'Apple Watch',        ['SMART WATCHES'],  'BRAND_MATCH'),
        (None, 'Wireless Mouse',     ['MOUSE WIRELESS'], 'MOUSE_FIT'),
        (None, 'USB Storage',        ['USB FLASH DISK', 'ΚΑΛΩΔΙΑ-ADAPTORS'], 'STORAGE_FIT'),
    ]
 
 
def _build_standard_slots(has_kb_match, is_premium):
    slots = []
    if has_kb_match:
        slots.append((None, 'Keyboard Case',     ['TABLETS KEYBOARDS'],                'KEYBOARD_TABLET_FIT'))
        slots.append((None, 'Wall Charger',      ['WALL CHARGERS'],                    'CHARGER_FIT'))
        slots.append((None, 'NB Bag',            ['NB BAGS', 'ΘΗΚΕΣ SLEEVE LAPTOP'],   'NB_SIZE_FIT'))
        slots.append((None, 'Tablet Bag',        ['TABLET BAGS'],                      'CASE_FIT'))
    else:
        slots.append((None, 'Tablet Bag',        ['TABLET BAGS'],                      'CASE_FIT'))
        slots.append((None, 'Wall Charger',      ['WALL CHARGERS'],                    'CHARGER_FIT'))
 
    slots.append((None, 'Bluetooth',             ['Bluetooth'],                        'GENERIC'))
 
    if not has_kb_match:
        slots.append((None, 'Wireless Keyboard', ['KEYBOARDS WIRELESS'],               'KEYBOARD_WIRELESS_FIT'))
 
    slots.append((None, 'Screen Protector',      ['MOBILE SCREEN PROTECTORS'],         'SCREEN_PROTECTOR_FIT'))
    slots.append((None, 'Overhead',              ['OVERHEAD'],                         'GENERIC'))
    slots.append((None, 'Smartwatch',            ['SMART WATCHES'],                    'GENERIC'))
    slots.append((None, 'Cable',                 ['ΚΑΛΩΔΙΑ ΔΕΔΟΜΕΝΩΝ', 'USB CABLES'], 'CABLE_FIT'))
 
    stylus = (None, 'Stylus', ['ΓΡΑΦΙΔΕΣ'], 'STYLUS_FIT')
    if is_premium:
        # Premium spec: stylus moves up, right after the regular bag.
        insert_idx = 4 if has_kb_match else 1
        slots.insert(insert_idx, stylus)
    else:
        slots.append(stylus)
 
    slots.append((None, 'Wireless Mouse', ['MOUSE WIRELESS'],             'MOUSE_FIT'))
    slots.append((None, 'Storage',        ['MICRO SD', 'USB FLASH DISK'], 'STORAGE_FIT'))
    return slots[:10]
 
 
# ────────────────────────────────────────────────────────────
# Slot post-processing helpers (used only by the slot builders)
# ────────────────────────────────────────────────────────────
def _renumber(slots):
    """Stamp slot numbers 1..N preserving order (placeholder None replaced)."""
    return [(i + 1, role, hier, lk) for i, (_, role, hier, lk) in enumerate(slots)]
 
 
def _budget_cap(role, caps):
    """Map a role label to its budget-group cap (audio/power/case/default)."""
    r = role.lower()
    if any(k in r for k in ('overhead', 'audio', 'bluetooth', 'airpods',
                            'speaker', 'hands-free')):
        return caps.get('audio', 999)
    if any(k in r for k in ('charger', 'cable', 'power')):
        return caps.get('power', 999)
    if any(k in r for k in ('case', 'bag', 'sleeve', 'cover', 'folio')):
        return caps.get('case', 999)



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

# Ορισμός εμφάνισης τετραδίων ανά τάξη (A, B, G, D, E, ST)
# Χαρτογράφηση: Ποιο τετράδιο εμφανίζεται σε ποιες τάξεις
# Rank = Συνολική εμφάνιση σε όλες τις τάξεις (για προτεραιότητα)
NOTEBOOK_CATALOG_LOGIC = {
    'ΕΥΡΕΤΗΡΙΟ':    {'grades': {'A', 'B', 'G', 'D', 'E', 'ST'}, 'rank': 6, 'keywords': ['ευρετήριο', 'ευρετηριο']},
    'ΑΝΤΙΓΡΑΦΗΣ':   {'grades': {'A', 'B', 'G', 'D'},            'rank': 4, 'keywords': ['αντιγραφής', 'αντιγραφης', 'μισο μισο', 'μισό - μισό']},
    'ΣΠΙΡΑΛ 2Θ':    {'grades': {'B', 'G', 'D', 'E', 'ST'},      'rank': 5, 'keywords': ['σπιράλ 2', 'σπιραλ 2', '2 θέματα', '2 θεματα']},
    'ΜΑΘΗΜΑΤΙΚΩΝ':  {'grades': {'A', 'B', 'G', 'D'},            'rank': 4, 'keywords': ['μαθηματικών', 'μαθηματικων', 'τετραγωνάκια']},
    'ΚΛΑΣΙΚΟ ΜΠΛΕ': {'grades': {'D', 'E', 'ST'},                'rank': 3, 'keywords': ['μπλε 50', 'κλασικό μπλε', 'κλασικο μπλε']},
    'ΧΡΩΜΑΤΙΣΤΑ':   {'grades': {'A', 'B', 'G', 'D'},            'rank': 3, 'keywords': ['χρωματιστά', 'χρωματιστα']},
    'ΜΟΥΣΙΚΗΣ':     {'grades': {'G', 'D', 'E', 'ST'},           'rank': 2, 'keywords': ['μουσικής', 'μουσικης', 'πλάγιο']},
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
}


# ═════════════════════════════════════════════════════════════
# 🟢 TV CONFIGURATION (Home Entertainment)
# ═════════════════════════════════════════════════════════════

TV_SLOTS = [
    (1,  'Βάση Στήριξης',      ['MOUNTS & STANDS'],       'MOUNT_LOGIC'),
    (2,  'Soundbar',           ['SOUNDBARS'],             'SOUND_LOGIC'),
    (3,  'Καλώδιο HDMI',       ['HDMI'],                  'HDMI_LOGIC'),
    (4,  'Προστασία Ρεύματος', ['SURGE PROTECTORS'],      'GENERIC'),
    (5,  'Τηλεχειριστήριο',    ['REMOTE CONTROLS'],       'REMOTE_LOGIC'),
    (6,  'Κεραία / Καλώδιο',   ['ANTENNAS', 'ΚΕΡΑΙΑΣ'],    'ANTENNA_LOGIC'),
    (7,  'Μπαταρίες',          ['ΑΛΚΑΛΙΚΕΣ'],             'GENERIC'),
    (8,  'Αποθήκευση USB',     ['USB FLASH DISK'],        'GENERIC'),
    (9,  'Καθαρισμός',         ['CLEANING PRODUCTS'],     'GENERIC'),
    (10, 'Αναβάθμιση Ήχου',    ['SOUNDBARS'],             'SOUND_LOGIC_2'),
]

# ═════════════════════════════════════════════════════════════
# 🟢 TV CONFIGURATION (Home Entertainment)
# ═════════════════════════════════════════════════════════════

TV_MARKETING_COPY = {
    "Βάση Στήριξης": "Ασφαλής και σταθερή τοποθέτηση για την τηλεόρασή σου.",
    "Soundbar": "Αναβάθμισε τον ήχο σου με εντυπωσιακό βάθος.",
    "Προστασία Ρεύματος": "Προστάτευσε την επένδυσή σου από υπερτάσεις.",
    "Τηλεχειριστήριο": "Ο απόλυτος έλεγχος, τέλεια συμβατός.",
    "Κεραία": "Κρυστάλλινο σήμα για όλα τα ελεύθερα κανάλια.",
    "Καλώδιο Κεραίας": "Απρόσκοπτη σύνδεση με την κεραία σου.",
    "Μπαταρίες": "Μην ξεμείνεις ποτέ από ενέργεια.",
    "Καλώδιο HDMI": "Αξιόπιστη μεταφορά εικόνας υψηλής ανάλυσης 4K/8K.",
    "Αποθήκευση USB": "Αποθήκευσε τα αγαπημένα σου προγράμματα.",
    "Καθαρισμός": "Κρυστάλλινη εικόνα χωρίς σκόνη και δαχτυλιές.",
    "Εναλλακτική Βάση": "Διαφορετικός τύπος βάσης για μεγαλύτερη ευελιξία.",
    "Εφεδρικό HDMI": "Ένα ακόμα καλώδιο για τις κονσόλες σου.",
    "Εφεδρικό HDMI 2.1": "Premium HDMI 2.1 για 4K/120Hz, eARC και VRR.",
    "Αναβάθμιση Ήχου": "Αναβάθμισε τον ήχο σου χωρίς να ξοδέψεις πολλά.",
    "Μαγνητικό Πλαίσιο": "Δώσε στην The Frame σου το τέλειο διακοσμητικό πλαίσιο.",
}

# ═════════════════════════════════════════════════════════════
# 🟢 VINYL & TURNTABLES CONFIGURATION
# ═════════════════════════════════════════════════════════════

VINYL_SLOTS = [
    (1,  'Αξεσουάρ Μουσικής',   ['MUSIC ACCESSORIES', 'ΒΕΛΟΝΕΣ ΠΙΚΑΠ'], 'ACCESSORY_LOGIC'),
    (2,  'Ηχείο / Έξοδος Ήχου', ['ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ', 'PC SPEAKERS 2.0', 'PC SPEAKERS 1', 'MICRO  Hi-Fi', 'ΗΧΕΙΑ HI-FI', 'AMPLIFIERS', 'SOUNDBARS', 'MULTIROOM SPEAKERS'], 'AUDIO_LOGIC'),
    (3,  'LP Electronica/Pop',  ['LP ELECTRONICA/POP/HIP HOP'],         'LP_LOGIC'),
    (4,  'LP Alternative',      ['LP ALTERNATIVE'],                     'LP_LOGIC'),
    (5,  'Καλώδια Ήχου / USB',  ['ΚΑΛΩΔΙΑ 3.5MM JACK', 'ΚΑΛΩΔΙΑ USB'],  'CABLE_JACK_USB_LOGIC'),
    (6,  'Προστασία Ρεύματος',  ['SURGE PROTECTORS'],                   'SURGE_LOGIC'),
    (7,  'LP Classic Rock',     ['LP CLASSIC ROCK'],                    'LP_LOGIC'),
    (8,  'LP Ελληνικά',         ['LP ΕΛΛΗΝΙΚΑ'],                        'LP_LOGIC'),
    (9,  'Ακουστικά Overhead',  ['OVERHEAD'],                           'HEADPHONE_LOGIC'),
    (10, 'Καλώδια RCA',         ['ΚΑΛΩΔΙΑ RCA'],                        'CABLE_RCA_LOGIC'),
]

VINYL_MARKETING_COPY = {
    "Αξεσουάρ Μουσικής": "Φροντίδα και ανταλλακτικά για το πικάπ σου.",
    "Ηχείο / Έξοδος Ήχου": "Η ιδανική επιλογή ήχου για το setup σου.",
    "LP_GENRE": "Top selling βινύλιο των τελευταίων 30 ημερών.",
    "Καλώδια Ήχου / USB": "Απαραίτητη συνδεσιμότητα για τον εξοπλισμό σου.",
    "Προστασία Ρεύματος": "Προστάτευσε το πικάπ σου από τις υπερτάσεις.",
    "Ακουστικά Overhead": "Για προσωπικές και αναλογικές ακροάσεις.",
    "Καλώδια RCA": "Η κλασική σύνδεση για τον απόλυτο Hi-Fi ήχο.",
}

# 2026 Turntable Performance Pairing (Budget limits for Accessories, Audio, Cables, Surge, Headphones)
TURNTABLE_ACCESSORY_BUDGET = {
    'Entry':   {'audio_cap': 90,  'surge_cap': 20, 'headphone_cap': 50,  'cable_cap': 15},
    'Mid':     {'audio_cap': 200, 'surge_cap': 35, 'headphone_cap': 100, 'cable_cap': 30},
    'Premium': {'audio_cap': 600, 'surge_cap': 60, 'headphone_cap': 250, 'cable_cap': 80}
}

def get_vinyl_tier(price):
    if price >= 280: return 'Premium'
    if price >= 120: return 'Mid'
    return 'Entry'

# ─────────────────────────────────────────────────────────────
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
    "": ["ΣΗΜΕΙΩΜΑΤΑΡΙΑ", "ΤΕΤΡΑΔΙΑ"],
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

# ═══════════════════════════════════════════════════════════════════════════════
# TABLET HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

# Reusable utilities. Lift these into a shared module to reuse across
# Smartphones / Laptops / Floor Care / Peripherals engines.
 
# ────────────────────────────────────────────────────────────
# Column resolver  (handles non-breaking space \xa0 and trailing ≡)
# Public.gr's data export uses both — without this any direct df[col] would
# silently miss columns that have NBSP or the ≡ marker.
# ────────────────────────────────────────────────────────────
 
def _norm_col_name(s):
    return (str(s).replace('\xa0', ' ')
                  .replace('≡', '')
                  .strip()
                  .lower())
 
 
def _col(df, name):
    """Return the actual column name in df matching `name` (NBSP/≡ tolerant),
    or None if absent."""
    target = _norm_col_name(name)
    for c in df.columns:
        if _norm_col_name(c) == target:
            return c
    return None
 
 
def _series(df, name, default=''):
    """Get column as a string Series, defaulting to empty if column missing."""
    c = _col(df, name)
    if c is None:
        return pd.Series(default, index=df.index, dtype=object)
    return df[c].fillna(default).astype(str)
 
 
# ────────────────────────────────────────────────────────────
# Compatibility matching
# ────────────────────────────────────────────────────────────
 
def _compat_mask(pool, model):
    """Match the trigger model against accessory compat fields (BOTH
    'Συμβατές συσκευές' plural and 'Συμβατή συσκευή' singular). Pure
    case-insensitive substring match — no transliteration."""
    if not model:
        return pd.Series(False, index=pool.index)
    pat = re.escape(model)
    mask = pd.Series(False, index=pool.index)
    for col_name in ('Συμβατές συσκευές', 'Συμβατή συσκευή'):
        col = _col(pool, col_name)
        if col:
            mask = mask | pool[col].fillna('').astype(str).str.contains(
                pat, case=False, regex=True, na=False)
    return mask
 
 
# ────────────────────────────────────────────────────────────
# Port matching — separate maskers per hierarchy because each uses a
# different column to express port info.
# ────────────────────────────────────────────────────────────
 
def _port_mask_chargers(pool, trigger_port):
    """WALL CHARGERS — match by Θύρα USB column (values: '2 x USB-A', 'Type-C')."""
    if not trigger_port:
        return pd.Series(False, index=pool.index)
    s = _series(pool, 'Θύρα USB').str.lower()
    tp = trigger_port.lower()
    if 'type-c' in tp or 'usb-c' in tp:
        return s.str.contains('type-c', na=False) | s.str.contains('usb-c', na=False)
    if 'usb-a' in tp or 'micro' in tp or 'lightning' in tp:
        return s.str.contains('usb-a', na=False)
    return pd.Series(False, index=pool.index)
 
 
def _port_mask_cables(pool, trigger_port):
    """ΚΑΛΩΔΙΑ ΔΕΔΟΜΕΝΩΝ — match by Τύπος σύνδεσης column."""
    if not trigger_port:
        return pd.Series(False, index=pool.index)
    s = _series(pool, 'Τύπος σύνδεσης').str.lower()
    tp = trigger_port.lower()
    if 'type-c' in tp or 'usb-c' in tp:
        return s.str.contains('type-c', na=False) | s.str.contains('usb-c', na=False)
    if 'lightning' in tp:
        return s.str.contains('lightning', na=False)
    if 'micro' in tp:
        return s.str.contains('micro', na=False)
    return pd.Series(False, index=pool.index)
 
 
def _port_mask_flash(pool, trigger_port):
    """USB FLASH DISK — match by Σύνδεση column (values: USB-A, USB-C, USB)."""
    if not trigger_port:
        return pd.Series(False, index=pool.index)
    sigma = _series(pool, 'Σύνδεση').str.lower()
    tp = trigger_port.lower()
    if 'type-c' in tp or 'usb-c' in tp:
        return sigma.str.contains('usb-c', na=False)
    return sigma.str.contains('usb-a', na=False)
 
 
# ────────────────────────────────────────────────────────────
# Wattage tier matching
# ────────────────────────────────────────────────────────────
 
def _wattage_pref_mask(pool, ttier):
    """Mask for chargers whose Ισχύς (Watt) tier matches the tablet tier."""
    prefs = WATTAGE_TIER_PREFS.get(ttier, WATTAGE_TIER_PREFS['Mid'])
    s = _series(pool, 'Ισχύς (Watt)')
    if s.eq('').all():
        s = _series(pool, 'Ισχύς')   # APPLE ORIGINAL POWER SUPPLY uses bare 'Ισχύς'
    return s.isin(prefs)
 
 
# ────────────────────────────────────────────────────────────
# Color tokenizer
# ────────────────────────────────────────────────────────────
 
def _color_tokens(trigger_color):
    """Split 'Sky Blue' / 'Black/Gold' into ['sky','blue'] / ['black','gold'].
    Drops transparent/clear tokens — those go through the transparent fallback."""
    if not trigger_color:
        return []
    s = str(trigger_color).lower().strip()
    return [t for t in re.split(r'[\s/\-;,]+', s)
            if t and t not in TRANSPARENT_TOKENS]
 
 
# ────────────────────────────────────────────────────────────
# NB-bag size band matching
# Accepts the 4 formats found in NB BAGS.Μέγεθος:
#   '17"+', '12" - 13.9"', 'Έως 14"', '15.6"'
# ────────────────────────────────────────────────────────────
 
def _size_band_matches(band, tablet_size_inches):
    """True if `tablet_size_inches` falls in the size band string."""
    if not band or tablet_size_inches <= 0:
        return False
    b = band.lower().replace('"', '').strip()
    # "17+"
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*\+\s*$', b)
    if m:
        return tablet_size_inches >= float(m.group(1))
    # "12 - 13.9", "15 - 15.9"
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$', b)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return lo - 0.3 <= tablet_size_inches <= hi + 0.3
    # "έως 11.9", "έως 14"
    m = re.match(r'^\s*έως\s+(\d+(?:\.\d+)?)\s*$', b)
    if m:
        return tablet_size_inches <= float(m.group(1))
    # "15.6", "14"
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*$', b)
    if m:
        v = float(m.group(1))
        return abs(v - tablet_size_inches) <= 1.0
    return False
 
 
def _size_match_mask(pool, tablet_size_inches):
    """Vectorized wrapper around _size_band_matches over the Μέγεθος column."""
    s = _series(pool, 'Μέγεθος')
    return s.apply(lambda b: _size_band_matches(b, tablet_size_inches))

def get_tablet_tier(price):
    """Map a tablet's LIST PRICE (€) to a budget tier string.

    Returns one of: 'Premium' | 'High' | 'Mid' | 'Entry'
    These match the keys in TABLET_ACCESSORY_BUDGET and WATTAGE_TIER_PREFS.
    """
    try:
        p = float(price)
    except (TypeError, ValueError):
        return 'Entry'
    if p >= 900:
        return 'Premium'
    if p >= 500:
        return 'High'
    if p >= 200:
        return 'Mid'
    return 'Entry'
    
# ═════════════════════════════════════════════════════════════
# 🟢 LAPTOPS HELPERS
# ═════════════════════════════════════════════════════════════

 
def parse_screen_size(val):
    """Parse screen size string to float inches. E.g. '15.6\"' -> 15.6"""
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
        
    if 'Music' in available_sheets:
        dm = pd.read_excel(excel_file, sheet_name='Music')
        dm.columns = dm.columns.str.strip()
    else: dm = pd.DataFrame()
        
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
    
    return dp, dm, dh, ds, db, dl, dv, dper, dstat, available_sheets

try:

    df_products, df_music, df_history, df_slots, df_books, df_laptops, df_vacuums, df_peripherals, df_stationery, sheets_loaded = load_all_data()
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

    {
        "key": "TV",
        "label": "Εικόνα\n& Ήχος",
        "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='7' width='20' height='15' rx='2' ry='2'/%3E%3Cpolyline points='17 2 12 7 7 2'/%3E%3C/svg%3E",
    },
]

L2_CHILDREN = {
    "Books":     [{"key": "Kids Books",  "label": "Παιδικά\nΒιβλία",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/%3E%3Cpath d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/%3E%3C/svg%3E"}],
    "Telephony": [
        {"key": "Smartphones", "label": "Smart-\nphones", "icon_svg": "..."},
        {"key": "Tablets", "label": "Tablets", # <--- ΠΡΟΣΘΗΚΗ
         "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='2' width='16' height='20' rx='2' ry='2'/%3E%3Cline x1='12' y1='18' x2='12.01' y2='18'/%3E%3C/svg%3E"}
    ],          
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
                  {"key": "Notebooks", "label": "Τετράδια", "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "",      "label": "Τετράδια",    "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                  {"key": "Notepads",       "label": "Σημειωμ.",    "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'/%3E%3C/svg%3E"},
                 ],
    "SDA":       [{"key": "Floor Care", "label": "Σκούπες",
                   "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 2v8l4-2'/%3E%3Cpath d='M12 10l-4-2'/%3E%3Ccircle cx='12' cy='18' r='4'/%3E%3Cline x1='12' y1='10' x2='12' y2='14'/%3E%3C/svg%3E"}],
    "TV": [
        {"key": "TVs", "label": "Τηλεοράσεις",
            "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='7' width='20' height='15' rx='2' ry='2'/%3E%3Cpolyline points='17 2 12 7 7 2'/%3E%3C/svg%3E"},
        {"key": "Projectors", "label": "Projectors",
            "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='6' width='16' height='12' rx='2' ry='2'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cline x1='2' y1='12' x2='4' y2='12'/%3E%3Cline x1='20' y1='12' x2='22' y2='12'/%3E%3C/svg%3E"},
        {"key": "Turntables", "label": "Πικάπ", 
         "icon_svg": "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23ff5e00' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Ccircle cx='12' cy='12' r='2'/%3E%3Cpath d='M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83'/%3E%3C/svg%3E"}
    ],
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

    # Dynamic CSS targeting exactly the correct row and column!
    icon_css = "<style>\n"
    for i, l1 in enumerate(L1_CATEGORIES):
        row_idx = (i // 2) + 1  
        col_idx = (i % 2) + 1   
        icon_css += f"""
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:nth-of-type({row_idx}) > div:nth-child({col_idx}) button::before {{
            content: ''; display: block; width: 32px; height: 32px;
            background-image: url("data:image/svg+xml,{l1['icon_svg']}");
            background-size: contain; background-repeat: no-repeat; background-position: center;
            position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
        }}
        """
    icon_css += "</style>"
    st.sidebar.markdown(icon_css, unsafe_allow_html=True)

    # Render 2-column grid
    n_l1 = len(L1_CATEGORIES)
    for row_start in range(0, n_l1, 2):
        row_items = L1_CATEGORIES[row_start:row_start + 2]
        cols = st.sidebar.columns(2)
        for col, l1 in zip(cols, row_items):
            with col:
                if st.button(l1["label"], key=f"l1_btn_{l1['key']}", use_container_width=True):
                    st.session_state.nav_level = 2
                    st.session_state.selected_l1 = l1["key"]
                    # Auto-select the first L2 child if there's only one
                    children = L2_CHILDREN.get(l1["key"], [])
                    if len(children) == 1:
                        st.session_state.active_cluster = children[0]["key"]
                    else:
                        st.session_state.active_cluster = None
                    st.rerun()

    sel = None
    trigger = None

# ─────────────────────────────────────────────────────────────
# LEVEL 2 VIEW — Show L2 tiles + product selector + trigger card
# ─────────────────────────────────────────────────────────────
else:
    selected_l1_key = st.session_state.selected_l1
    selected_l1 = next((x for x in L1_CATEGORIES if x["key"] == selected_l1_key), None)
    children = L2_CHILDREN.get(selected_l1_key, [])

    # Breadcrumb row
    label_clean = (selected_l1["label"] if selected_l1 else "").replace("\n", " ")
    st.sidebar.markdown(f'<div class="l2-breadcrumb-label" style="margin-bottom:6px;">‹&nbsp;&nbsp;{label_clean}</div>', unsafe_allow_html=True)
    if st.sidebar.button("↩ Πίσω", key="back_to_l1", use_container_width=True):
        st.session_state.nav_level = 1
        st.session_state.selected_l1 = None
        st.session_state.active_cluster = None
        st.rerun()

    st.sidebar.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Exact row/col CSS targeting for L2
    active_cluster = st.session_state.active_cluster
    border_css = "<style>\n"
    for i, child in enumerate(children):
        row_idx = (i // 2) + 1
        col_idx = (i % 2) + 1
        border = "2px solid #ff5e00" if child["key"] == active_cluster else "1px solid #eaeaea"
        
        border_css += f"""
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:nth-of-type({row_idx}) > div:nth-child({col_idx}) button {{
            border: {border} !important;
        }}
        [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:nth-of-type({row_idx}) > div:nth-child({col_idx}) button::before {{
            content: ''; display: block; width: 32px; height: 32px;
            background-image: url("data:image/svg+xml,{child['icon_svg']}");
            background-size: contain; background-repeat: no-repeat; background-position: center;
            position: absolute; top: 14px; left: 50%; transform: translateX(-50%);
        }}
        """
    border_css += "</style>"
    st.sidebar.markdown(border_css, unsafe_allow_html=True)

    # Render L2 tiles in pairs (Unbreakable version)
    n_l2 = len(children)
    for i, row_start in enumerate(range(0, n_l2, 2)):
        row_items = children[row_start:row_start + 2]
        cols = st.sidebar.columns(2)
        for j, (col, child) in enumerate(zip(cols, row_items)):
            with col:
                btn_key = f"l2_btn_{child['key']}_{i}_{j}"
                if st.button(child["label"], key=btn_key, use_container_width=True):
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
    
    
    elif active_cluster == "Tablets":
        if df_products.empty: st.stop()
        # Fetch by Level 2 or Hierarchy depending on your Excel mapping
        tabs = df_products[df_products['Level 2'].fillna('').astype(str).str.strip().str.upper() == 'TABLETS'].copy()
        if tabs.empty:
            tabs = df_products[df_products['Hierarchy'].fillna('').astype(str).str.strip().str.upper().isin(
                ['TABLETS', 'TABLETS & IPADS', 'IPADS', 'ΤΑΜΠΛΕΤ', 'TABLET PC']
            )].copy()
    
        # ─────────────────────────────────────────────────────────────
        # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
        # ─────────────────────────────────────────────────────────────
        tablet_test_skus = {
            "2004601", "2037260", "2072249", "2100875",
            "2071356", "2066261", "2075971"
        }
        if not tabs.empty:
            t_filtered = tabs[tabs['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(tablet_test_skus)]
            if not t_filtered.empty:
                tabs = t_filtered
        # ─────────────────────────────────────────────────────────────
        if tabs.empty:
            st.sidebar.warning("Δεν βρέθηκαν test Tablets.")
        else:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Tablet</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", tabs['Title'].unique(), label_visibility="collapsed", key="tab_sel")
            trigger = tabs[tabs['Title']==sel].iloc[0] if sel else None
    
    
    elif active_cluster == "Laptops":
        if df_laptops.empty:
            st.sidebar.warning("Sheet 'Laptops' is empty or missing.")
        else:
            laptops = df_laptops[(df_laptops['Level 1']=='IT') & (df_laptops['Level 2'].isin(LAPTOP_L2_VALUES))]
            if laptops.empty:
                laptops = df_laptops[df_laptops['Hierarchy'].fillna('').astype(str).str.upper().str.contains('NOTEBOOK|LAPTOP', regex=True, na=False)]
            
            laptop_test_skus = {
                "2032853", "2077374", "2114170", "2106436", "2076615", 
                "1950043", "1950030", "1993377", "2056517", "1993362"
            }
            if not laptops.empty:
                laptops = laptops[laptops['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(laptop_test_skus)]

            if laptops.empty:
                st.sidebar.warning("Δεν βρέθηκαν test Laptops.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Laptop</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", laptops['Title'].unique(), label_visibility="collapsed", key="lt_sel")
                trigger = laptops[laptops['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "TVs":
        if df_products.empty: st.stop()
        
        # Robust filtering ignores uppercase/lowercase & trailing spaces in Excel!
        lvl2 = df_products['Level 2'].fillna('').astype(str).str.strip().str.upper()
        tvs = df_products[lvl2 == 'TV']
        
        # Ultimate Fallback: Just in case it's in Level 1 or Hierarchy instead of Level 2
        if tvs.empty:
            hier = df_products['Hierarchy'].fillna('').astype(str).str.strip().str.upper()
            tvs = df_products[hier == 'TV']

        # ─────────────────────────────────────────────────────────────
        # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
        # ─────────────────────────────────────────────────────────────
        tv_test_skus = {
            "2027797", "2027771", "2035104", "2089142", "2035099"
        }
        if not tvs.empty:
            t_filtered = tvs[tvs['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(tv_test_skus)]
            if not t_filtered.empty:
                tvs = t_filtered
        # ─────────────────────────────────────────────────────────────

        if tvs.empty:
            st.sidebar.warning("Δεν βρέθηκαν test Τηλεοράσεις.")
        else:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Τηλεόραση</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", tvs['Title'].unique(), label_visibility="collapsed", key="tv_sel")
            trigger = tvs[tvs['Title']==sel].iloc[0] if sel else None
            


    elif active_cluster == "TVs":
        if df_products.empty: st.stop()
        tvs = df_products[df_products['Level 2'] == 'TV']
        if tvs.empty:
            st.sidebar.warning("Δεν βρέθηκαν Τηλεοράσεις.")
        else:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Τηλεόραση</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", tvs['Title'].unique(), label_visibility="collapsed", key="tv_sel")
            trigger = tvs[tvs['Title']==sel].iloc[0] if sel else None

    elif active_cluster == "Projectors":
        if df_products.empty: st.stop()
        # Fetch by Level 2 or Hierarchy depending on your Excel mapping
        projs = df_products[df_products['Level 2'].fillna('').astype(str).str.strip().str.upper() == 'PROJECTORS'].copy()
        if projs.empty:
            projs = df_products[df_products['Hierarchy'].fillna('').astype(str).str.strip().str.upper().isin(['PROJECTORS', 'ΒΙΝΤΕΟΠΡΟΒΟΛΕΙΣ'])].copy()
            
        # ─────────────────────────────────────────────────────────────
        # 🧪 TEST LIST: Restrict the dropdown to specific SKUs
        # ─────────────────────────────────────────────────────────────
        projector_test_skus = {
            "2013266", "1866727", "1903449", "1968623"
        }
        if not projs.empty:
            p_filtered = projs[projs['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(projector_test_skus)]
            if not p_filtered.empty:
                projs = p_filtered
        # ─────────────────────────────────────────────────────────────
        if projs.empty:
            st.sidebar.warning("Δεν βρέθηκαν test Projectors.")
        else:
            st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Projector</p>', unsafe_allow_html=True)
            sel = st.sidebar.selectbox("", projs['Title'].unique(), label_visibility="collapsed", key="proj_sel")
            trigger = projs[projs['Title']==sel].iloc[0] if sel else None



    elif active_cluster == "Turntables":
            if df_products.empty: st.stop()
            
            # FIX: Robust filtering στη στήλη Hierarchy αντί για Level 2
            hier_col = df_products['Hierarchy'].fillna('').astype(str).str.strip().str.upper()
            turntables = df_products[hier_col == 'ΠΙΚΑΠ']
    
            # 🧪 TEST LIST: Περιορισμός στα συγκεκριμένα SKUs
            tt_test_skus = {"1956497", "2106285", "1821326", "1402320", "1873884"}
            
            if not turntables.empty:
                t_filtered = turntables[turntables['Material'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).isin(tt_test_skus)]
                if not t_filtered.empty:
                    turntables = t_filtered
    
            if turntables.empty:
                st.sidebar.warning("Δεν βρέθηκαν test Πικάπ στη στήλη Hierarchy.")
            else:
                st.sidebar.markdown('<p class="sidebar-section">Επιλέξτε Πικάπ</p>', unsafe_allow_html=True)
                sel = st.sidebar.selectbox("", turntables['Title'].unique(), label_visibility="collapsed", key="tt_sel")
                trigger = turntables[turntables['Title']==sel].iloc[0] if sel else None

    
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
                lifestyle = stationery[stationery['Hierarchy'].str.contains('ΣΗΜΕΙΩΜΑΤ', case=False, na=False)].copy()
                lifestyle = lifestyle[lifestyle.apply(lambda r: stationery_matches_gender(r.get('Title',''), r.get('Brand',''), detected_gender), axis=1)]
                if not lifestyle.empty:
                    selected = get_rotated_selection(lifestyle, tm, 'notebook', n=1)
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
            
            discovery_pool['_canonical'] = discovery_pool.apply(lambda r: get_canonical_book_name(r.get('Title', ''), r.get('Τίτλος πρωτοτύπου', '')), axis=1)
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

# ═══════════════════════════════════════════════════════════════════════════════
# SCORING CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
 
SCORE_MODEL_MATCH   = 1_000_000   # Exact model compatibility
SCORE_USB_PORT      =   500_000   # USB port compatibility
SCORE_WATTAGE       =   300_000   # 30W+ charger
SCORE_SD_CARD       =   500_000   # Micro SD (Android)
SCORE_SD_CAPACITY   =   100_000   # 64 / 128 GB capacity
SCORE_OTG_ADAPTER   =   500_000   # OTG/Adapter (iOS)
SCORE_CABLE_LENGTH  =   200_000   # Cable ≥ 2 m
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# TABLET ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

# Orchestrator only. All scoring/filter logic delegates to the helpers above
# and is parametrized by the slot definitions in the configuration section.
 
def run_tablets_engine(trigger, df_products, df_history):
    diag, slot_notes, all_recs = [], {}, []
 
    # ----- Trigger -----
    tm     = trigger['Material']
    tb     = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tmod   = str(trigger.get('Μοντέλο', '')).strip()
    trat   = str(trigger.get('Experts Rating', '')).strip()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))
    ttier  = get_tablet_tier(tprice)
    tos    = str(trigger.get('Λειτουργικό σύστημα', '')).lower()
    tsize  = parse_screen_size(trigger.get('Μέγεθος οθόνης', 0))
    tport  = str(extract_base_port(trigger.get('Θύρα USB', ''))).strip()
    tcolor = str(trigger.get('Χρώμα', '')).strip()
    color_toks = _color_tokens(tcolor)
 
    is_premium    = tb in TABLET_PREMIUM_BRANDS and (
                      ttier == 'Premium' or trat in ('Excellent', 'Top Quality'))
    is_apple_ipad = tb == 'APPLE'
    is_kiddoboo   = tb == 'KIDDOBOO'
 
    diag.append(("0. Trigger",
                 f"Brand={tb}, Tier={ttier}, Model={tmod}",
                 f"OS={tos}, Size={tsize}\", Port={tport}, Color={tcolor or '-'}"))
 
    # ----- Pool prep -----
    c = df_products[df_products['Material'] != tm].copy()
    c['Sales_Tiebreaker'] = pd.to_numeric(c.get('Sum of Sales', 0),
                                          errors='coerce').fillna(0)
    c['_p'] = c['LIST PRICE'].apply(parse_euro_price)
 
    # Pre-classify Apple Originals using structured fields
    apple_hier = ('APPLE ORIGINAL TABLET ACCESSORIES',
                  'APPLE ORIGINAL TABLET BAGS')
    c['_apple_cat'] = ''
    apple_mask = c['Hierarchy'].isin(apple_hier)
    if apple_mask.any():
        c.loc[apple_mask, '_apple_cat'] = (
            c.loc[apple_mask].apply(_apple_orig_categorize, axis=1)
        )
 
    # KB compat check — drives standard-vs-no-kb persona routing
    has_kb_match = False
    if tmod:
        kb_pool = c[c['Hierarchy'] == 'TABLETS KEYBOARDS']
        if not kb_pool.empty:
            has_kb_match = _compat_mask(kb_pool, tmod).any()
    diag.append(("1. KB Compat", f"has_kb_match={has_kb_match}",
                 f"premium={is_premium}"))
 
    # ----- Persona routing -----
    if is_kiddoboo:
        slots, persona = _build_kiddoboo_slots(), 'KIDDOBOO'
    elif is_apple_ipad:
        slots, persona = _build_apple_ipad_slots(), 'IPAD'
    else:
        slots = _build_standard_slots(has_kb_match, is_premium)
        persona = 'STANDARD_PREMIUM' if is_premium else 'STANDARD'
    slots = _renumber(slots)
    diag.append(("2. Persona", persona, f"{len(slots)} slots planned"))
 
    # ----- Slot execution -----
    used_materials  = {tm}
    used_apple_cats = set()
    caps = TABLET_ACCESSORY_BUDGET.get(ttier, TABLET_ACCESSORY_BUDGET['Mid'])
 
    for slot_num, role, hierarchies, logic_key in slots:
        notes = [f"Logic: {logic_key}"]
        pool = c[c['Hierarchy'].isin(hierarchies)].copy()
        pool = pool[~pool['Material'].isin(used_materials)]
        if pool.empty:
            slot_notes[slot_num] = notes + ['EMPTY_POOL']
            continue
 
        pool['Final_Score'] = 0.0
        same_brand = (_series(pool, 'Κατασκευαστής')
                      .str.upper().str.strip() == tb)
        pool.loc[same_brand, 'Final_Score'] += S_BRAND_BOOST
 
        # Always-on universal compat boost (cheap; helps everything)
        if tmod:
            mm = _compat_mask(pool, tmod)
            pool.loc[mm, 'Final_Score'] += S_MODEL_MATCH
 
        base = logic_key.split(':', 1)[0]
 
        # ---- APPLE TARGET (iPad slots 1-4) ----
        if base in ('APPLE_TARGET', 'APPLE_TARGET_STRICT'):
            target_cats = set(logic_key.split(':', 1)[1].split(','))
            in_target = pool['_apple_cat'].isin(target_cats)
            pool.loc[in_target, 'Final_Score'] += S_CATEGORY_TARGET
            already = pool['_apple_cat'].isin(used_apple_cats)
            pool.loc[already, 'Final_Score'] += S_CATEGORY_REPEAT
 
            if base == 'APPLE_TARGET_STRICT' and in_target.any():
                pool = pool[in_target]
                if tmod:
                    mm = _compat_mask(pool, tmod)
                    if mm.any():
                        pool = pool[mm]
                    else:
                        slot_notes[slot_num] = notes + ['NO_MODEL_COMPAT']
                        continue
 
        # ---- TABLET BAG fit ----
        elif base == 'CASE_FIT':
            brand_dev = _series(pool, 'Brand συσκευής σου').str.upper().str.strip()
            tb_match = brand_dev.eq(tb) | brand_dev.eq('UNIVERSAL')
            pool.loc[tb_match, 'Final_Score'] += S_BRAND_STRONG
 
            ttype = _series(pool, 'Τύπος Θήκης').str.lower()
            if is_premium or is_apple_ipad:
                pool.loc[ttype.isin(['folio', 'book cover']),
                         'Final_Score'] += S_CASE_TYPE_PRIMARY
            else:
                pool.loc[ttype.eq('back cover'),
                         'Final_Score'] += S_CASE_TYPE_PRIMARY
 
            if color_toks:
                acc_color = _series(pool, 'Χρώμα').str.lower()
                exact = acc_color.apply(
                    lambda s: any(t in s for t in color_toks))
                transp = acc_color.isin(TRANSPARENT_TOKENS)
                pool.loc[exact, 'Final_Score'] += S_COLOR_EXACT
                pool.loc[transp & ~exact, 'Final_Score'] += S_COLOR_TRANSPARENT
 
        # ---- TABLET KEYBOARD fit (TABLETS KEYBOARDS hierarchy) ----
        elif base == 'KEYBOARD_TABLET_FIT':
            if tmod:
                mm = _compat_mask(pool, tmod)
                if mm.any():
                    pool = pool[mm]
            extra = _series(pool, 'Πρόσθετα χαρακτηριστικά').str.lower()
            pool.loc[extra.str.contains('touchpad', na=False),
                     'Final_Score'] += S_TOUCHPAD_BOOST
 
        # ---- WIRELESS KEYBOARD fit (KEYBOARDS WIRELESS hierarchy) ----
        elif base == 'KEYBOARD_WIRELESS_FIT':
            conn = _series(pool, 'Συνδεσιμότητα').str.lower()
            pool.loc[conn.str.contains('bluetooth', na=False),
                     'Final_Score'] += S_BLUETOOTH_REQ
            if is_premium:
                extra = _series(pool, 'Πρόσθετα χαρακτηριστικά').str.lower()
                pool.loc[extra.str.contains('touchpad', na=False),
                         'Final_Score'] += S_TOUCHPAD_BOOST
 
        # ---- NB BAG size fit ----
        elif base == 'NB_SIZE_FIT':
            if tsize > 0:
                pool.loc[_size_match_mask(pool, tsize),
                         'Final_Score'] += S_SIZE_MATCH
 
        # ---- WALL CHARGER fit ----
        elif base == 'CHARGER_FIT':
            t3 = _series(pool, 'Τύπος3').str.lower()
            wall = t3.str.contains('φορτιστής πρίζας|σετ φόρτισης',
                                    regex=True, na=False)
            if wall.any():
                pool = pool[wall]
            pool.loc[_port_mask_chargers(pool, tport),
                     'Final_Score'] += S_PORT_MATCH
            pool.loc[_wattage_pref_mask(pool, ttier),
                     'Final_Score'] += S_WATTAGE_TIER
 
        # ---- APPLE CHARGER fit (handles MacBook PSU vs iPad charger split) ----
        elif base == 'APPLE_CHARGER_FIT':
            t3 = _series(pool, 'Τύπος3').str.lower()
            ypod = _series(pool, 'Υποδοχές').str.lower()
            is_charger = (t3.str.contains('φορτιστής πρίζας', na=False)
                          | t3.str.contains('σετ φόρτισης', na=False)
                          | ypod.str.contains('usb-c|magsafe',
                                              regex=True, na=False))
            if is_charger.any():
                pool = pool[is_charger]
 
            in_apple = pool['Hierarchy'].isin(
                ['APPLE ORIGINAL POWER SUPPLY',
                 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS',
                 'APPLE ORIGINAL IPHONE CABLE-ADA'])
            pool.loc[in_apple, 'Final_Score'] += S_HIERARCHY_TARGET
            pool.loc[same_brand.reindex(pool.index, fill_value=False),
                     'Final_Score'] += S_BRAND_STRONG
            wattage = _series(pool, 'Ισχύς (Watt)')
            if wattage.eq('').all():
                wattage = _series(pool, 'Ισχύς')
            pool.loc[wattage.isin(['Έως 20 Watt', '21 - 60 Watt']),
                     'Final_Score'] += S_WATTAGE_TIER
            macbook_hi = wattage.str.contains(r'\b(7\d|9\d|1[0-4]\d)\s*W',
                                               regex=True, na=False)
            pool.loc[macbook_hi, 'Final_Score'] -= S_WATTAGE_TIER
 
        # ---- APPLE CABLE fit ----
        elif base == 'APPLE_CABLE_FIT':
            t3 = _series(pool, 'Τύπος3').str.lower()
            is_cable = (t3.str.contains('καλώδιο', na=False)
                        & ~t3.str.contains('φορτιστής', na=False))
            if is_cable.any():
                pool = pool[is_cable]
            in_apple = pool['Hierarchy'].isin(
                ['APPLE ORIGINAL IPHONE CABLE-ADAPTORS',
                 'APPLE ORIGINAL IPHONE CABLE-ADA'])
            pool.loc[in_apple, 'Final_Score'] += S_HIERARCHY_TARGET
            pool.loc[same_brand.reindex(pool.index, fill_value=False),
                     'Final_Score'] += S_BRAND_STRONG
            pool.loc[_port_mask_cables(pool, tport),
                     'Final_Score'] += S_PORT_MATCH
 
        # ---- GENERIC CABLE ----
        elif base == 'CABLE_FIT':
            t3 = _series(pool, 'Τύπος3').str.lower()
            is_cable = (t3.str.contains('καλώδιο', na=False)
                        & ~t3.str.contains('φορτιστής', na=False))
            if is_cable.any():
                pool = pool[is_cable]
            pool.loc[_port_mask_cables(pool, tport),
                     'Final_Score'] += S_PORT_MATCH
 
        # ---- STORAGE fit ----
        elif base == 'STORAGE_FIT':
            if 'android' in tos:
                pool.loc[pool['Hierarchy'] == 'MICRO SD',
                         'Final_Score'] += S_PORT_MATCH
            pool.loc[_port_mask_flash(pool, tport),
                     'Final_Score'] += S_PORT_MATCH
            sigma = _series(pool, 'Σύνδεση').str.lower()
            tp = tport.lower()
            if 'type-c' in tp or 'usb-c' in tp:
                pool.loc[sigma.eq('usb-a'),
                         'Final_Score'] += S_PORT_MISMATCH
            pool.loc[pool['Hierarchy'].eq('ΚΑΛΩΔΙΑ-ADAPTORS'),
                     'Final_Score'] += S_OTG_BONUS
 
        # ---- MOUSE fit ----
        elif base == 'MOUSE_FIT':
            conn = _series(pool, 'Συνδεσιμότητα').str.lower()
            has_bt = conn.str.contains('bluetooth', na=False)
            has_usb_only = (conn.str.contains('usb', na=False)
                            | conn.str.contains('2.4', na=False)) & ~has_bt
            pool.loc[has_bt, 'Final_Score'] += S_BLUETOOTH_REQ
            pool.loc[has_usb_only, 'Final_Score'] += S_USB_RECEIVER_PEN
            if is_apple_ipad and has_bt.any():
                pool = pool[has_bt]   # iPad needs Bluetooth, no USB-receiver mice
 
        # ---- AIRPODS / Bluetooth audio ----
        elif base == 'AIRPODS_BOOST':
            pool.loc[same_brand, 'Final_Score'] += S_AIRPODS_BOOST
 
        # ---- BRAND match (Apple Watch on iPad, etc.) ----
        elif base == 'BRAND_MATCH':
            pool.loc[same_brand, 'Final_Score'] += S_BRAND_STRONG
 
        # ---- SCREEN PROTECTOR fit ----
        elif base == 'SCREEN_PROTECTOR_FIT':
            if tmod:
                mm = _compat_mask(pool, tmod)
                if mm.any():
                    pool = pool[mm]
                else:
                    slot_notes[slot_num] = notes + ['NO_MODEL_COMPAT']
                    continue
 
        # ---- STYLUS fit ----
        elif base == 'STYLUS_FIT':
            if tmod:
                mm = _compat_mask(pool, tmod)
                pool.loc[mm, 'Final_Score'] += S_MODEL_MATCH
            tport_l = tport.lower()
            if 'type-c' in tport_l or 'usb-c' in tport_l:
                stylus_port = _series(pool, 'Θύρα USB').str.lower()
                pool.loc[stylus_port.str.contains('usb-c|type-c',
                                                   regex=True, na=False),
                         'Final_Score'] += S_PORT_MATCH
            pool.loc[~same_brand, 'Final_Score'] += S_UNBRANDED_STYLUS
 
        # GENERIC: brand boost only (already applied above)
 
        # ---- Price-tier penalty ----
        cap = _budget_cap(role, caps)
        pool.loc[pool['_p'] > cap * 1.5, 'Final_Score'] += S_PRICE_PENALTY
 
        if pool.empty:
            slot_notes[slot_num] = notes + ['EMPTY_AFTER_FILTER']
            continue
 
        pool = pool.sort_values(['Final_Score', 'Sales_Tiebreaker'],
                                ascending=[False, False])
        chosen = pool.iloc[0]
 
        if base.startswith('APPLE_TARGET'):
            cat = str(chosen.get('_apple_cat', ''))
            if cat:
                used_apple_cats.add(cat)
                notes.append(f"AppleCat={cat}")
 
        rc = chosen.copy()
        rc['Assigned_Slot']  = slot_num
        rc['Slot_Role']      = role
        rc['Marketing_Copy'] = TABLET_MARKETING_COPY.get(role, "Ιδανική επιλογή.")
        all_recs.append(rc)
        used_materials.add(chosen['Material'])
 
        notes.append(f"score={chosen['Final_Score']:.0f}")
        notes.append(f"brand={str(chosen.get('Κατασκευαστής', ''))[:20]}")
        slot_notes[slot_num] = notes
 
    recs_df = (pd.DataFrame(all_recs).sort_values('Assigned_Slot')
               if all_recs else pd.DataFrame())
    return recs_df, diag, slot_notes, recs_df
 
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
    # Remove laptops/ themselves from candidates
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
    selected_mouse_row = None 
    for slot_num, role, hierarchies, logic_key in LAPTOP_MAINSTREAM_SLOTS:
        notes = [f"Logic: {logic_key}", f"Target: {hierarchies}"]

       # ── 2-in-1 override: skip Cooler slot entirely (useless for convertibles) ──
        if is_2in1 and logic_key == 'STAND_SIZE':
            notes.append("🚫 2-in-1 → skip Cooler (useless for convertibles)")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Skipped (2-in-1)"))
            continue

        # ── NEW RULE: Skip cooler if laptop is smaller than 14" ──
        if logic_key == 'STAND_SIZE' and tscreen > 0 and tscreen < 14.0:
            notes.append("🚫 Small laptop (<14\") → skip Cooler")
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
                # STRICT BAN on gaming pads/brands (HyperX, Razer, Corsair, etc.)
                not_gaming_mask = ~pool['Title'].fillna('').str.lower().str.contains(r'rgb|gaming|hyperx|razer|corsair|steelseries|rog\b|predator|legion', regex=True, na=False)
                pool, note = filter_or_penalize(pool, not_gaming_mask, "Persona: Hard banned gaming/RGB/HyperX pads")
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
            # UPDATED: Mousepad Color Match (reads from winning MOUSE)
            # ========================================================
            color_match_found = False
            
            if selected_mouse_row is not None:
                mouse_title = str(selected_mouse_row.get('Title', '')).lower()
                mouse_attr_color = str(selected_mouse_row.get('Χρώμα', '')).lower()
                combined_mouse_color_text = f"{mouse_title} {mouse_attr_color}"
                
                # Define core colors and their synonyms
                target_colors_map = {
                    'μαύρο': ['μαύρο', 'black', 'γραφίτη', 'γραφίτης', 'graphite', 'midnight'],
                    'λευκό': ['λευκό', 'white', 'άσπρο', 'starlight', 'pale grey'],
                    'γκρι': ['γκρι', 'grey', 'gray', 'silver', 'ασημί'],
                    'ροζ': ['ροζ', 'pink', 'rose'],
                    'μπλε': ['μπλε', 'blue', 'γαλάζιο', 'indigo', 'blue grey'],
                    'κόκκινο': ['κόκκινο', 'red']
                }
                
                detected_color_group = None
                for base_color, synonyms in target_colors_map.items():
                    # Look for any of the synonyms in the mouse's text
                    if any(re.search(rf'\b{re.escape(syn)}\b', combined_mouse_color_text) for syn in synonyms):
                        detected_color_group = synonyms
                        break
                
                if detected_color_group:
                    # Found a color in the mouse, now look for it in the mousepads
                    if 'Χρώμα' in pool.columns:
                        attr_match = pool['Χρώμα'].fillna('').astype(str).str.lower().isin(detected_color_group)
                        title_match = pool['Title'].fillna('').str.lower().str.contains('|'.join(detected_color_group), regex=True, na=False)
                        color_hit = attr_match | title_match
                        
                        # Ensure the color match isn't an ugly wrist pad
                        color_hit = color_hit & ~gel_mask
                        
                        if color_hit.any():
                            # Overrides the flat rate price bands so the colored pad wins
                            pool.loc[color_hit, 'Final_Score'] += 150000
                            color_match_found = True
                            notes.append(f"🎨 Matched Mouse Color ({detected_color_group[0]}): +150k to {color_hit.sum()} mousepads")
                else:
                    notes.append("🎨 No distinct color found in winning Mouse, skipped color matching.")
            
            # Premium Fallback: If no color match was found, boost Logitech pads
            if not color_match_found and (is_apple or laptop_tier >= 3) and not is_gaming:
                logi_pads = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'LOGITECH'
                pool.loc[logi_pads, 'Final_Score'] += 80000
                notes.append("🍎 Premium pad fallback: Boosted Logitech pads")
                # ========================================================

        # ── Logic: Persona-Driven Monitor (20-25% of Laptop Value) ──
        elif logic_key == 'MONITOR_LOGIC':

            # ── NEW RULE: Only suggest monitors 27" and higher ──
            title_sizes = pool['Title'].fillna('').apply(parse_screen_size)
            if 'Μέγεθος οθόνης' in pool.columns:
                col_sizes = pool['Μέγεθος οθόνης'].apply(parse_screen_size)
                pool['_mon_size'] = pd.concat([col_sizes, title_sizes], axis=1).max(axis=1)
            else:
                pool['_mon_size'] = title_sizes
                
            # Filter out monitors < 27" (we keep 0.0 as a fallback so we don't accidentally drop items missing size data)
            size_mask = (pool['_mon_size'] >= 27.0) | (pool['_mon_size'] == 0.0)
            pool, note = filter_or_penalize(pool, size_mask, "Size rule: Exclude monitors under 27\"")
            notes.append(note)

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
                    tech_mask = pool['Τεχνολογία Οθόνης'].fillna('').astype(str).str.lower().str.contains(GOOD_PANEL_PAT, regex=True, na=False)
                # Also check title as fallback — many monitors spell the panel tech in the title
                tech_mask = tech_mask | pool['Title'].fillna('').str.lower().str.contains(GOOD_PANEL_PAT, regex=True, na=False)
                
                if tech_mask.any():
                    b4 = len(pool)
                    pool = pool[tech_mask]
                    notes.append(f"🖼️ Retina laptop → premium panel tech filter (IPS/OLED/MiniLED only): {b4}→{len(pool)}")
                else:
                    notes.append("⚠ Retina laptop but no premium panels found in catalog — keeping all")
                    
            # ── Req 6: OLED laptop → Soft preference for OLED monitors ──
            if trigger_is_oled:
                oled_mon = pool['Title'].fillna('').str.lower().str.contains(r'\boled\b|\bamoled\b|\bqd-oled\b', regex=True, na=False)
                if 'Τεχνολογία Οθόνης' in pool.columns:
                    oled_mon = oled_mon | pool['Τεχνολογία Οθόνης'].fillna('').astype(str).str.lower().str.contains(r'oled|amoled', regex=True, na=False)
                
                if oled_mon.any():
                    # 1. Base boost for being OLED
                    pool.loc[oled_mon, 'Final_Score'] += 150000
                    
                    # 2. Deboost extremely expensive OLEDs (> 60% of the laptop price)
                    # (This stacks on top of the standard overbuy penalty to nuke it completely)
                    extreme_price_threshold = tprice * 0.60
                    extreme_oled = oled_mon & (pool['_p'] > extreme_price_threshold)
                    pool.loc[extreme_oled, 'Final_Score'] -= 400000
                    
                    # 3. Slight deboost for gaming OLEDs if the user's laptop isn't specifically gaming
                    if not is_gaming:
                        gaming_oled = oled_mon & pool['Title'].fillna('').str.lower().str.contains(r'gaming|odyssey|predator|rog|alienware|aorus', regex=True, na=False)
                        pool.loc[gaming_oled, 'Final_Score'] -= 80000
                    
                    notes.append(f"🌈 OLED laptop → Soft Boost to {oled_mon.sum()} OLEDs (+150k), Heavy penalty if >€{extreme_price_threshold:.0f}")
                else:
                    notes.append("⚠ OLED laptop but no OLED monitors found — standard IPS/VA applies")

            vesa_mon = pool['Title'].fillna('').str.lower().str.contains('vesa|ergonomic|pivot', regex=True, na=False)
            pool.loc[vesa_mon, 'Final_Score'] += 10000

            if is_apple:
                usbc_mon = pool['Title'].fillna('').str.lower().str.contains('usb-c|type-c|thunderbolt|mac', regex=True, na=False)
                pool.loc[usbc_mon, 'Final_Score'] += 50000
                if tprice >= 1400:
                    pool.loc[apple_monitors, 'Final_Score'] += 500000
                else:
                    pool.loc[apple_monitors, 'Final_Score'] -= 300000

            elif is_surface:
                usbc_mon = pool['Title'].fillna('').str.lower().str.contains('usb-c|type-c|thunderbolt', regex=True, na=False)
                if usbc_mon.any():
                    pool.loc[usbc_mon, 'Final_Score'] += 50000
                    notes.append("🪟 Surface: USB-C monitor boost (single-cable docking)")



                
        # ── Logic: Office / Headset Ecosystem ──
        elif logic_key == 'OFFICE_HEADSET_LOGIC':
            if is_apple:
                office_software = pool['Hierarchy'].fillna('').str.upper() == 'OFFICE SUITES'
                pool = pool[~office_software]
                notes.append("Brand Ecosystem: Banned Microsoft Office for Mac users")

            # 🪟 Microsoft Surface: boost MS-branded Office & peripherals
            if is_surface:
                ms_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'MICROSOFT'
                office_software = pool['Hierarchy'].fillna('').str.upper() == 'OFFICE SUITES'
                pool.loc[ms_brand | office_software, 'Final_Score'] += 80000
                if (ms_brand | office_software).any():
                    notes.append(f"🪟 Surface Ecosystem: Microsoft brand + Office suites boosted +80k")

            is_headset = ~pool['Hierarchy'].fillna('').str.upper().str.contains('OFFICE')
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)

            if is_headset.any():
                # ══════════════════════════════════════════════════════
                # SIZE-BASED HIERARCHY + TYPE FILTER (HARD RULE)
                #   <15": Bluetooth hierarchy  OR  Overhead hierarchy + ON EAR type
                #   ≥15": Overhead hierarchy + OVER EAR type
                # Office Suites are preserved regardless (they aren't headsets).
                # ══════════════════════════════════════════════════════
                hier_upper = pool['Hierarchy'].fillna('').str.upper()
                is_bluetooth_hier = hier_upper.str.contains('BLUETOOTH')
                is_overhead_hier  = hier_upper.str.contains('OVERHEAD')
                is_office         = hier_upper.str.contains('OFFICE')

                if 'Τύπος ακουστικών' in pool.columns:
                    type_col = pool['Τύπος ακουστικών'].fillna('').str.upper()
                else:
                    type_col = pd.Series('', index=pool.index)

                is_onear  = is_overhead_hier & type_col.str.contains('ON EAR')
                is_overear = is_overhead_hier & type_col.str.contains('OVER EAR')

                if tscreen > 0:
                    # Build the two rule masks up front
                    under15_mask = is_bluetooth_hier | is_onear   # <15" rule
                    over15_mask  = is_overear                      # ≥15" rule

                    if tscreen < 15:
                        primary_mask, primary_label   = under15_mask, "<15\" rule: Bluetooth OR Overhead+ON-EAR"
                        fallback_mask, fallback_label = over15_mask,  "fallback to Overhead+OVER-EAR"
                    else:
                        primary_mask, primary_label   = over15_mask,  "≥15\" rule: Overhead+OVER-EAR"
                        # ≥15" fallback = the <15" rule itself (On-Ear OR Bluetooth)
                        # — consistent with what a 14.9" laptop would get, instead of
                        # leaving the pool unfiltered.
                        fallback_mask, fallback_label = under15_mask, "fallback to Bluetooth OR Overhead+ON-EAR"

                    # ========================================================
                    # NEW: Protect Apple audio from being wiped out by the size filter
                    apple_protect = (pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'APPLE') | \
                                    pool['Title'].fillna('').str.lower().str.contains(r'airpods|earpods', regex=True, na=False)
                    # ========================================================

                    
                    # Cascade: primary → fallback → skip
                    b4 = len(pool)
                    primary_keep = pool[primary_mask | is_office]
                    if not primary_keep[primary_mask].empty:
                        pool = primary_keep
                        notes.append(f"🎧 {primary_label}: {b4}→{len(pool)}")
                    else:
                        fallback_keep = pool[fallback_mask | is_office]
                        if not fallback_keep[fallback_mask].empty:
                            pool = fallback_keep
                            notes.append(f"🎧 {primary_label} empty → {fallback_label}: {b4}→{len(pool)}")
                        else:
                            notes.append(f"⚠ Both primary and fallback headset rules empty — no filter applied")

                    # Recompute masks on filtered pool for downstream boosts
                    hier_upper = pool['Hierarchy'].fillna('').str.upper()
                    is_bluetooth_hier = hier_upper.str.contains('BLUETOOTH')
                    is_overhead_hier  = hier_upper.str.contains('OVERHEAD')
                    is_office         = hier_upper.str.contains('OFFICE')
                    is_headset        = ~is_office
                    if 'Τύπος ακουστικών' in pool.columns:
                        type_col = pool['Τύπος ακουστικών'].fillna('').str.upper()
                    else:
                        type_col = pd.Series('', index=pool.index)
                    is_onear   = is_overhead_hier & type_col.str.contains('ON EAR')
                    is_overear = is_overhead_hier & type_col.str.contains('OVER EAR')
                    is_earbud  = is_bluetooth_hier
                    is_overhead = is_overhead_hier
                else:
                    is_earbud = is_bluetooth_hier
                    is_overhead = is_overhead_hier

                # ── Persona boosts (all on top of the filtered pool) ──
                if is_gaming:
                    gaming_mask = pool['Title'].fillna('').str.lower().str.contains(
                        r'gaming|razer|corsair|steelseries|hyperx|logitech g\b|astro|asus rog|rog delta|kraken|cloud ii|arctis|blackshark',
                        regex=True, na=False
                    )
                    pool.loc[is_headset & gaming_mask, 'Final_Score'] += 250000
                    pool.loc[is_headset & gaming_mask & is_overhead, 'Final_Score'] += 50000
                    notes.append(f"🎮 Gaming: Boosted gaming headsets +250k ({(is_headset & gaming_mask).sum()} items)")
                elif 'Προτεινόμενη χρήση' in pool.columns:
                    if is_premium or is_apple:
                        prem_use = pool['Προτεινόμενη χρήση'].fillna('').str.lower().str.contains('premium|επαγγελματική', regex=True, na=False)
                        pool.loc[is_headset & prem_use, 'Final_Score'] += 50000
                        notes.append("Persona: Boosted Premium/Professional headsets")
                    else:
                        standard_use = pool['Προτεινόμενη χρήση'].fillna('').str.lower().str.contains('ομιλία|καθημερινή', regex=True, na=False)
                        pool.loc[is_headset & standard_use, 'Final_Score'] += 50000
                        notes.append("Persona: Boosted standard Voice/Daily headsets")
                else:
                    notes.append("Persona: Boost skipped ('Προτεινόμενη χρήση' column missing from candidates)")

                apple_hp = pd.Series(False, index=pool.index)
                
                # Apple ecosystem — HARD PREFER Apple-branded headphones (AirPods family)
                # and color-match the laptop color when possible.
                if is_apple:
                    # First, expand search to APPLE HEADPHONES hierarchy — these are
                    # the AirPods listings and they should dominate the slot for Apple users.
                    apple_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'APPLE'
                    airpods_title = pool['Title'].fillna('').str.lower().str.contains(
                        r'airpods',
                        regex=True, na=False
                    )
                    apple_hp_hier = hier_upper.str.contains('APPLE HEADPHONES|APPLE ORIGINAL HEADPHONES', regex=True, na=False)
                    apple_hp = (apple_brand | airpods_title | apple_hp_hier) & is_headset

                    if apple_hp.any():
                        # ========================================================
                        # SUPER HARD boost — force Apple earbuds to the absolute top (+500k)
                        # ========================================================
                        pool.loc[apple_hp, 'Final_Score'] += 500000
                        notes.append(f"🍎 Apple HEADPHONES hard-boost +500k ({apple_hp.sum()} items)")


                        # ========================================================
                        # NEW: Ensure budget Macs get standard AirPods instead of Pros
                        if tprice < 1200:
                            pro_apple = apple_hp & (pool['_p'] > 180)
                            pool.loc[pro_apple, 'Final_Score'] -= 150000
                            if pro_apple.any():
                                notes.append(f"🍎 Apple: <€1200 laptop → Preferred standard AirPods over Pro (-150k to {pro_apple.sum()} items)")
                        # ========================================================

                        
                        # Color match: if laptop has a Χρώμα, boost same-color headphones
                        tlaptop_color = str(trigger.get('Χρώμα', '')).strip()
                        if tlaptop_color and tlaptop_color.lower() not in ('nan', 'n/a', '', 'none'):
                            if 'Χρώμα' in pool.columns:
                                color_match_mask = apple_hp & (
                                    pool['Χρώμα'].fillna('').astype(str).str.strip().str.lower() == tlaptop_color.lower()
                                )
                                if color_match_mask.any():
                                    pool.loc[color_match_mask, 'Final_Score'] += 150000
                                    notes.append(f"🎨 Color match ({tlaptop_color}): +150k to {color_match_mask.sum()} Apple headphones")
                                else:
                                    # Fall back to title-based color match
                                    color_title = apple_hp & pool['Title'].fillna('').str.lower().str.contains(
                                        re.escape(tlaptop_color.lower()), regex=True, na=False
                                    )
                                    if color_title.any():
                                        pool.loc[color_title, 'Final_Score'] += 100000
                                        notes.append(f"🎨 Color match via title ({tlaptop_color}): +100k to {color_title.sum()}")
                    else:
                        # Fallback to premium audio brands only if no Apple headphones exist
                        premium_overhead = pool['Title'].fillna('').str.lower().str.contains(
                            r'wh-1000xm|wh1000xm|quietcomfort|qc\d|momentum \d|bose 700|audio-technica',
                            regex=True, na=False
                        )
                        pool.loc[is_headset & premium_overhead, 'Final_Score'] += 100000
                        if (is_headset & premium_overhead).any():
                            notes.append(f"🍎 Apple fallback: Premium audio brands +100k ({(is_headset & premium_overhead).sum()} items)")
                            
                # Headset Sane Price Tiering — stricter for budget laptops
                if tprice >= 2000:
                    pass
                elif tprice >= 1000:
                    # Added & ~apple_hp so Apple earbuds don't get penalized
                    pool.loc[is_headset & (pool['_p'] > 250) & ~apple_hp, 'Final_Score'] -= 100000
                elif tprice > 0:
                    # Sub-€1000 laptop: cap headsets at ~15% of laptop price
                    max_hs_price = max(50, tprice * 0.15)
                    # Added & ~apple_hp so Apple earbuds don't get penalized
                    pool.loc[is_headset & (pool['_p'] > max_hs_price) & ~apple_hp, 'Final_Score'] -= 200000
                    notes.append(f"Price Tiering: Hard penalty (-200k) for standard headsets >€{max_hs_price:.0f} (Apple HPs exempt)")
 


                    
 
        # ── Logic: Cooler / Stand Size Match ──
        # Coolers are printed with a supported size. A 15.6" cooler is too small
        # for a 16" laptop (overhangs) and ridiculous for a 13" laptop (wasted space).
        elif logic_key == 'STAND_SIZE':
            # 🚫 EXCLUDE monitor mounts/arms/desk-mounts — they live in the same
            # hierarchy (ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ) but are NOT laptop stands. Titles like
            # "Βάση Οθόνης Επιτραπέζια με Βραχίονα" (monitor desk mount with arm)
            # or SBOX LCD-352 (monitor arm 17"-32") should never appear here.
            title_lower = pool['Title'].fillna('').str.lower()
            monitor_mount_mask = title_lower.str.contains(
                r'βάση οθόν|monitor (arm|mount|stand)|βραχίον|lcd arm|desk mount|wall mount|επιτοίχι',
                regex=True, na=False
            )
            b4 = len(pool)
            pool = pool[~monitor_mount_mask]
            if b4 > len(pool):
                notes.append(f"🚫 Excluded monitor mounts/arms: {b4}→{len(pool)}")

            if tscreen > 0:
                size_col = None
                for candidate_col in ['Μέγεθος', 'Μέγεθος οθόνης']:
                    if candidate_col in pool.columns:
                        size_col = candidate_col
                        break

                # Compute effective size: max of field value AND title-parsed size.
                # Catches products where Μέγεθος=0 but title says "15.6 inch" — we
                # want the title size to count so they can be correctly filtered.
                title_size = pool['Title'].fillna('').apply(parse_screen_size)
                if size_col:
                    field_size = pool[size_col].apply(parse_screen_size)
                    pool['_acc_size'] = pd.concat([field_size, title_size], axis=1).max(axis=1)
                else:
                    pool['_acc_size'] = title_size

                # Coolers for laptops: size must be within reasonable fit range.
                # Tightened from +2.0 to +1.5 so a 15.6" cooler can't win on a 12" laptop.
                strict_fit = pool[(pool['_acc_size'] >= tscreen - 0.5) & (pool['_acc_size'] <= tscreen + 1.5)]
                if not strict_fit.empty:
                    pool = strict_fit
                    notes.append(f"Cooler strict size fit {tscreen}\" (-0.5/+1.5\"): {len(pool)}")
                else:
                    loose_fit = pool[(pool['_acc_size'] >= tscreen - 1.0) & (pool['_acc_size'] <= tscreen + 3.0)]
                    if not loose_fit.empty:
                        pool = loose_fit
                        notes.append(f"Cooler loose size fit {tscreen}\" (-1.0/+3.0\"): {len(pool)}")
                    else:
                        # Only truly sizeless (universal) pass — products that claim a specific
                        # size via title but don't match are NOT eligible.
                        sizeless = pool[pool['_acc_size'] == 0]
                        if not sizeless.empty:
                            pool = sizeless
                            notes.append(f"⚠ No cooler size match for {tscreen}\", kept {len(pool)} sizeless (universal)")

            # Gaming laptops benefit from active (fan) coolers; others lean to passive stands
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)
            if is_apple:
                # 🍎 Hard ban active fan coolers for MacBooks
                active_cooling_mask = pool['Title'].fillna('').str.lower().str.contains('cooler|fan|cooling|ανεμιστήρ', regex=True, na=False)
                b4_apple_coolers = len(pool)
                pool = pool[~active_cooling_mask]
                if b4_apple_coolers > len(pool):
                    notes.append(f"🍎 Apple: Hard banned active fan coolers ({b4_apple_coolers}→{len(pool)})")
                
                # Boost passive stands massively
                stand_mask = pool['Title'].fillna('').str.lower().str.contains('stand|βάση|aluminum|αλουμίνιο|ergonomic', regex=True, na=False)
                pool.loc[stand_mask, 'Final_Score'] += 200000
                notes.append("Premium/Apple: Passive ergonomic stand boost (+200k)")
            elif is_gaming:
                fan_mask = pool['Title'].fillna('').str.lower().str.contains('fan|cooler|ψύξη|rgb', regex=True, na=False)
                pool.loc[fan_mask, 'Final_Score'] += 40000
                notes.append("Gaming: Active cooler (fan) boost")
            elif is_premium:
                stand_mask = pool['Title'].fillna('').str.lower().str.contains('stand|βάση|aluminum|αλουμίνιο|ergonomic', regex=True, na=False)
                pool.loc[stand_mask, 'Final_Score'] += 40000
                notes.append("Premium: Passive ergonomic stand boost")


        # ── Logic: Storage (SSD for premium, HDD for budget) ──
        # A 1TB portable HDD on a €2849 MacBook Pro is embarrassing. Premium
        # laptops should pair with portable SSDs (speed + form factor match),
        # budget laptops with HDDs or high-capacity flash.
        elif logic_key == 'STORAGE_LOGIC':
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)

            # Cheap-trap: no €10 USB sticks with a €2k laptop
            pool, trap_note = apply_cheap_trap(pool, tprice, 'STORAGE')
            if trap_note: notes.append(trap_note)

            is_ssd = pool['Title'].fillna('').str.lower().str.contains(r'\bssd\b|portable ssd|nvme|t7|t5|sandisk extreme', regex=True, na=False)
            is_hdd = pool['Title'].fillna('').str.lower().str.contains(r'\bhdd\b|hard drive|elements|my passport|canvio', regex=True, na=False)

            if laptop_tier >= 3:
                # Premium/Pro: SSDs only. If catalog has none, penalise HDDs
                # (-150k) instead of filtering — flash drives at least win over HDDs.
                pool, note = filter_or_penalize(pool, is_ssd, f"Tier {laptop_tier}: SSD-only")
                notes.append(note)
                # Recompute is_ssd/is_hdd on possibly-filtered pool
                is_ssd = pool['Title'].fillna('').str.lower().str.contains(r'\bssd\b|portable ssd|nvme|t7|t5|sandisk extreme', regex=True, na=False)
                pool.loc[pool['_p'] >= 100, 'Final_Score'] += 100000
                notes.append("Tier 3+: Boost ≥€100 SSDs (speed + capacity match)")
            elif laptop_tier == 2:
                # Mid-range: prefer SSD but don't ban HDD
                pool.loc[is_ssd, 'Final_Score'] += 80000
                pool.loc[is_hdd, 'Final_Score'] -= 20000
                notes.append("Tier 2: SSD preferred over HDD")
            else:
                # Budget: HDDs fine, large flash drives fine
                pool.loc[(pool['_p'] >= 25) & (pool['_p'] <= 60), 'Final_Score'] += 40000
                notes.append("Tier 1: Value storage (€25–€60 range)")

            # Apple users: boost Mac-compatible portable SSDs only (not HDDs!)
            # LaCie makes BOTH the "Mobile Drive" (HDD) and the "Rugged/Mobile SSD",
            # so we only match LaCie products whose title contains SSD indicators.
            if is_apple:
                lacie_ssd = pool['Title'].fillna('').str.lower().str.contains(r'lacie', regex=True, na=False) & is_ssd
                other_mac_ssd = pool['Title'].fillna('').str.lower().str.contains(
                    r'samsung t7|samsung t9|sandisk extreme (portable )?ssd',
                    regex=True, na=False
                )
                mac_ssd_mask = lacie_ssd | other_mac_ssd
                pool.loc[mac_ssd_mask, 'Final_Score'] += 50000
                if mac_ssd_mask.any():
                    notes.append(f"🍎 Apple: Mac-friendly SSDs boosted +50k ({mac_ssd_mask.sum()} items)")

        # ── GENERIC: just sales + availability ──
        # logic_key == 'GENERIC' — no extra filtering needed
 
        # ══════════════════════════════════════════════════════
        # PICK BEST ITEM
        # ══════════════════════════════════════════════════════
        if pool.empty:
            notes.append("❌ No items after logic")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Empty after logic"))
            continue
 
        pool = pool.sort_values('Final_Score', ascending=False)
 
        # Hierarchy cap: max 2 per hierarchy across all slots
        chosen = None
        for _, row in pool.iterrows():
            h = row['Hierarchy']
            if used_hierarchies_count.get(h, 0) < 2:
                chosen = row
                break
 
        if chosen is None:
            notes.append("❌ Hierarchy cap blocks all")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 0, "Hier cap"))
            continue
 
        row_copy = chosen.copy()
        row_copy['Assigned_Slot'] = slot_num
        row_copy['Slot_Role'] = role
        # --- NEW: Tier-Aware "Performance Pairing" Copy ---
        if logic_key == 'MONITOR_LOGIC':
            if laptop_tier == 4:   row_copy['Marketing_Copy'] = "4K/Pro panel — built to match your workstation's color & speed."
            elif laptop_tier == 3: row_copy['Marketing_Copy'] = "QHD/144Hz+ — unlock your GPU, no screen tearing."
            elif laptop_tier == 2: row_copy['Marketing_Copy'] = "144Hz IPS — perfect pairing for your AI-ready laptop."
            else:                  row_copy['Marketing_Copy'] = "Entry FHD — extra workspace at the right price."
        elif logic_key == 'MOUSE_LOGIC':
            if laptop_tier == 4:   row_copy['Marketing_Copy'] = "Top-tier sensor — keeps up with your machine's response time."
            elif laptop_tier == 3: row_copy['Marketing_Copy'] = "8K+ DPI — cursor as smooth as your high-refresh screen."
            elif laptop_tier == 2: row_copy['Marketing_Copy'] = "High-DPI sensor — matched to your laptop's display speed."
            else:                  row_copy['Marketing_Copy'] = "Reliable wireless — clean, no-fuss daily driver."
        elif logic_key == 'CHARGER_PORT':
            if tb and str(chosen.get('Κατασκευαστής','')).strip().upper() == tb:
                row_copy['Marketing_Copy'] = f"Original {tb.title()} — guaranteed fit and full wattage."
            else:
                row_copy['Marketing_Copy'] = "Compatible PD charger — matches your laptop's port and wattage."
        elif logic_key == 'BAG_SIZE' or logic_key == 'SLEEVE_SIZE':
            if laptop_tier >= 3: row_copy['Marketing_Copy'] = "Premium protection sized exactly to your laptop."
            else:                row_copy['Marketing_Copy'] = "Right-sized carry, comfortable every day."
        elif logic_key == 'MOUSEPAD_LOGIC':
            row_copy['Marketing_Copy'] = "Smooth glide, stable base — ideal for any setup."
        else:
            row_copy['Marketing_Copy'] = LAPTOP_MARKETING_COPY.get(role, "Ιδανική επιλογή!")
        row_copy['Item_Rank'] = 1
        all_recs.append(row_copy)
        used_materials.add(chosen['Material'])
        used_hierarchies_count[chosen['Hierarchy']] = used_hierarchies_count.get(chosen['Hierarchy'], 0) + 1
        notes.append(f"✅ {str(chosen.get('Title',''))[:60]}")
        slot_notes[slot_num] = notes
        if logic_key == 'MOUSE_LOGIC':
            selected_mouse_row = chosen
        diag.append((f"Slot {slot_num} ({role})", 1, f"Score: {chosen.get('Final_Score', 0):.0f}"))
 
    diag.append(("TOTAL", len(all_recs), f"out of {len(LAPTOP_MAINSTREAM_SLOTS)}"))
 
    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        return recs_df, diag, slot_notes, recs_df
    return pd.DataFrame(), diag, slot_notes, pd.DataFrame()
 






# ═══════════════════════════════════════════════════════════════
# 🟢 FLOOR CARE ENGINE — "Perfect Fit" Ecosystem
# ═══════════════════════════════════════════════════════════════

def run_floor_care_engine(trigger, df_products, df_history):
    diag = []
    slot_notes = {}
    all_recs = []

    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tmodel = str(trigger.get('Μοντέλο', '')).strip()
    thier = str(trigger.get('Hierarchy', '')).strip().upper()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))

    _tt_lower = tt.lower()
    is_robot = 'ρομπότ' in thier.lower() or 'robot' in _tt_lower
    is_bagged = False
    if 'Τύπος σκούπας' in trigger.index:
        vac_type = str(trigger.get('Τύπος σκούπας', '')).lower()
        is_bagged = 'με σακούλα' in vac_type or 'bagged' in vac_type
    if not is_bagged:
        is_bagged = 'με σακούλα' in _tt_lower or 'bagged' in _tt_lower

    is_pet = False
    if 'Κατάλληλη για κατοικίδια' in trigger.index:
        pet_val = str(trigger.get('Κατάλληλη για κατοικίδια', '')).lower()
        is_pet = pet_val in ('ναι', 'yes', 'true', '1')
    if not is_pet:
        is_pet = 'pet' in _tt_lower or 'κατοικίδι' in _tt_lower

    is_stick = 'stick' in thier.lower() or 'stick' in _tt_lower

    diag.append(("0. Trigger", f"Brand={tb}, €{tprice:.0f}",
                 f"Model={tmodel}, Robot={is_robot}, Bagged={is_bagged}, Pet={is_pet}, Stick={is_stick}"))

    # ── Build candidate pool ──
    c = df_products[df_products['Material'] != tm].copy()
    trigger_hiers_upper = {h.upper().strip() for h in FLOOR_CARE_TRIGGER_HIERARCHIES}
    b4 = len(c)
    c = c[~c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(trigger_hiers_upper)]
    diag.append(("1a. Excl vacuums", len(c), f"Removed {b4 - len(c)}"))

    if 'CW Stock Units' in c.columns:
        stv = pd.to_numeric(c['CW Stock Units'], errors='coerce').fillna(0)
        pct = (stv > 0).sum() / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c = c[stv > 0]
            diag.append(("1b. Stock", len(c), f"Applied ({pct:.0%})"))
        else:
            diag.append(("1b. Stock", len(c), f"⚠ SKIPPED ({pct:.0%})"))

    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0

    used_materials = {tm}
    slot_num = 0

    # ══════════════════════════════════════════════════════════
    # PHASE 1: MODEL-MATCHED ACCESSORIES (show ALL)
    # Match trigger.Μοντέλο against accessory.Συμβατό μοντέλο
    # AND verify brand via Για μάρκες ηλεκτρικής σκούπας
    # ══════════════════════════════════════════════════════════
    p1_notes = ["=== PHASE 1: Model-matched accessories ==="]
    model_matched = pd.DataFrame()

    if tmodel and tmodel.lower() not in ('n/a', 'nan', '', '0'):
        model_mask = pd.Series(False, index=c.index)
        for mcol in ['Συμβατό μοντέλο', 'Συμβατό μοντέλο2']:
            if mcol in c.columns:
                col_match = c[mcol].fillna('').astype(str).str.upper().str.contains(
                    re.escape(tmodel.upper()), regex=True, na=False
                )
                model_mask |= col_match
                p1_notes.append(f"  {mcol}: {col_match.sum()} matches for \'{tmodel}\'")

        brand_mask = pd.Series(True, index=c.index)
        brand_col = 'Για μάρκες ηλεκτρικής σκούπας'
        if brand_col in c.columns and tb:
            brand_mask = c[brand_col].fillna('').astype(str).str.upper().str.contains(
                re.escape(tb), regex=True, na=False
            )
            brand_empty = c[brand_col].fillna('').astype(str).str.strip() == ''
            brand_mask = brand_mask | brand_empty
            p1_notes.append(f"  Brand filter ({tb}): {brand_mask.sum()} pass")

        mfr_match = c['Κατασκευαστής'].fillna('').astype(str).str.upper().str.strip() == tb
        brand_mask = brand_mask | mfr_match

        combined = model_mask & brand_mask
        model_matched = c[combined].copy()
        p1_notes.append(f"  Combined (model AND brand): {len(model_matched)} items")
    else:
        p1_notes.append(f"  ⚠ No model on trigger (\'{tmodel}\') — skipping")

    if not model_matched.empty:
        model_matched['Final_Score'] = 0.0
        if 'AVAILABILITY' in model_matched.columns:
            model_matched.loc[model_matched['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
        model_matched['Final_Score'] += model_matched['Sales_Tiebreaker'].fillna(0) * 0.1
        model_matched = model_matched.sort_values('Final_Score', ascending=False)

        for _, row in model_matched.iterrows():
            if row['Material'] in used_materials:
                continue
            slot_num += 1
            rc = row.copy()
            rc['Assigned_Slot'] = slot_num
            eidos = str(row.get('Είδος', '')).strip()
            role = eidos if eidos and eidos.lower() not in ('nan', '') else 'Αξεσουάρ'
            rc['Slot_Role'] = f"🎯 {role}"
            rc['Marketing_Copy'] = f"Απόλυτα συμβατό με {tb.title()} {tmodel}."
            rc['Item_Rank'] = 1
            all_recs.append(rc)
            used_materials.add(row['Material'])

        p1_notes.append(f"✅ Added {slot_num} model-matched accessories")
    else:
        p1_notes.append("❌ No model-matched accessories found")
        # Universal fallback: scent sticks / pearls
        hier_col = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
        scent_pool = c[hier_col.str.contains('ΕΞΑΡΤΗΜΑΤΑ', na=False)]
        if 'Είδος' in scent_pool.columns and not scent_pool.empty:
            scent_mask = scent_pool['Είδος'].fillna('').str.contains(
                r'Αρωματικ|sticks|Πέρλες|pearls', case=False, regex=True, na=False
            )
            scent_items = scent_pool[scent_mask]
            scent_items = scent_items[~scent_items['Material'].isin(used_materials)]
            if not scent_items.empty:
                scent_items = scent_items.copy()
                scent_items['Final_Score'] = 0.0
                if 'AVAILABILITY' in scent_items.columns:
                    scent_items.loc[scent_items['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
                scent_items['Final_Score'] += scent_items['Sales_Tiebreaker'].fillna(0) * 0.1
                best = scent_items.sort_values('Final_Score', ascending=False).iloc[0]
                slot_num += 1
                rc = best.copy()
                rc['Assigned_Slot'] = slot_num
                rc['Slot_Role'] = '↩ Αρωματικό (Universal)'
                rc['Marketing_Copy'] = 'Φρεσκάδα σε κάθε σκούπισμα.'
                rc['Item_Rank'] = 1
                all_recs.append(rc)
                used_materials.add(best['Material'])
                p1_notes.append(f"↩ Universal fallback: scent → slot {slot_num}")

    slot_notes[0] = p1_notes
    diag.append(("Phase 1", slot_num, f"{len(model_matched)} matches"))

    # ══════════════════════════════════════════════════════════
    # PHASE 2: COMPANION DEVICES (fixed slots)
    # ══════════════════════════════════════════════════════════
    COMPANIONS = [
        ('Σκουπάκι',       ['Ηλεκτρικά Σκουπάκια', 'ΣΚΟΥΠΑΚΙΑ']),
        ('Ατμοκαθαριστής', ['Ατμοκαθαριστές', 'ΑΤΜΟΚΑΘΑΡΙΣΤΕΣ']),
        ('Σκούπα Στάχτης', ['Σκούπες Στάχτης', 'ΣΚΟΥΠΕΣ ΣΤΑΧΤΗΣ']),
        ('Pet Care',       ['PET CARE']),
    ]

    for comp_role, comp_hiers in COMPANIONS:
        slot_num += 1
        notes = [f"Companion: {comp_role}"]

        # 🚫 Pet Care ONLY for pet-friendly triggers
        if comp_role == 'Pet Care' and not is_pet:
            notes.append("🚫 Trigger is NOT pet-friendly → skipping Pet Care slot")
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({comp_role})", 0, "Skipped (no pet)"))
            continue

        hier_upper = [h.upper().strip() for h in comp_hiers]
        pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(hier_upper)].copy()

        if pool.empty:
            hier_col = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
            mask = pd.Series(False, index=c.index)
            for hk in hier_upper:
                if hk: mask |= hier_col.str.contains(re.escape(hk), regex=True, na=False)
            pool = c[mask].copy()
            if not pool.empty: notes.append(f"⚠ Substring fallback: {len(pool)}")

        notes.append(f"Pool: {len(pool)}")

        # 🧹 Stick vacuums: handhelds are redundant (stick IS a handheld).
        # Only show same-brand handheld (ecosystem sell) or skip entirely.
        if comp_role == 'Σκουπάκι' and is_stick and not pool.empty and tb:
            same_brand_mask = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
            brand_pool = pool[same_brand_mask]
            if not brand_pool.empty:
                pool = brand_pool
                notes.append(f"🧹 Stick trigger → same-brand handhelds only ({tb}): {len(pool)}")
            else:
                notes.append(f"🧹 Stick trigger → no {tb} handhelds → skipping slot")
                slot_notes[slot_num] = notes
                diag.append((f"Slot {slot_num} ({comp_role})", 0, "Skipped (stick, no brand match)"))
                continue

        pool = pool[~pool['Material'].isin(used_materials)]

        # ↩ Universal fallback: if companion pool is empty, try universal
        # accessories (Εξαρτήματα) as a last resort rather than showing nothing
        if pool.empty:
            hier_col = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
            universal_pool = c[hier_col.str.contains('ΕΞΑΡΤΗΜΑΤΑ', na=False)].copy()
            if 'Είδος' in universal_pool.columns and not universal_pool.empty:
                uni_mask = universal_pool['Είδος'].fillna('').str.contains(
                    r'Universal|Ακροφύσιο|Nozzle|Αρωματικ|sticks|Πέρλες',
                    case=False, regex=True, na=False
                )
                universal_pool = universal_pool[uni_mask]
            universal_pool = universal_pool[~universal_pool['Material'].isin(used_materials)]
            if not universal_pool.empty:
                pool = universal_pool
                notes.append(f"↩ Universal fallback: {len(pool)} accessories")
            else:
                notes.append("❌ Empty (no companions, no universal fallback)")
                slot_notes[slot_num] = notes
                diag.append((f"Slot {slot_num} ({comp_role})", 0, "Empty"))
                continue

        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
        pool['Final_Score'] += pool['Sales_Tiebreaker'].fillna(0) * 0.1
        if tb:
            same = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
            pool.loc[same, 'Final_Score'] += 50000
            if same.any(): notes.append(f"Brand bonus ({tb}): {same.sum()}")
        if is_pet and comp_role == 'Pet Care':
            pool['Final_Score'] += 30000
            notes.append("🐾 Pet trigger boost")
        if is_robot and comp_role == 'Ατμοκαθαριστής':
            pool['Final_Score'] += 40000
            notes.append("🤖 Robot → steam companion")

        pool = pool.sort_values('Final_Score', ascending=False)
        chosen = pool.iloc[0]
        rc = chosen.copy()
        rc['Assigned_Slot'] = slot_num
        rc['Slot_Role'] = comp_role
        rc['Marketing_Copy'] = FLOOR_CARE_MARKETING_COPY.get(comp_role, "Ιδανική επιλογή!")
        rc['Item_Rank'] = 1
        all_recs.append(rc)
        used_materials.add(chosen['Material'])
        notes.append(f"✅ {str(chosen.get('Title',''))[:60]}")
        slot_notes[slot_num] = notes
        diag.append((f"Slot {slot_num} ({comp_role})", 1, f"Score: {chosen.get('Final_Score',0):.0f}"))

    diag.append(("TOTAL", len(all_recs), f"Phase1={slot_num - len(COMPANIONS)} + Phase2={len(COMPANIONS)}"))

    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        return recs_df, diag, slot_notes, recs_df
    return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ═════════════════════════════════════════════════════════════
# 🟢 PERIPHERALS ENGINE — All IT Peripheral Clusters
# Config-driven: each cluster is a dict of slot definitions
# ═════════════════════════════════════════════════════════════

# ── Trigger detection ──
PERIPHERAL_TRIGGERS = {
    "Mouse":           {"hierarchies": {"MOUSE WIRELESS", "MOUSE WIRED", "APPLE ORIGINAL WIRELESS MOUSE"}},
    "Keyboard":        {"hierarchies": {"KEYBOARDS WIRELESS", "KEYBOARDS WIRED", "APPLE ORIGINAL WIRELESS KEYBOARD"}},
    "Gaming Mouse":    {"hierarchies": {"GAMING MOUSE"}},
    "Gaming Keyboard": {"hierarchies": {"GAMING KEYBOARDS"}},
}

# ── Slot configs per cluster ──
# (role, hierarchies, flags)
# flags keys:
#   title_boost/title_hide: [str] — keyword boost/penalty
#   title_include: [str] — HARD filter: only keep candidates whose title matches (use when boost isn't enough)
#   eidos_include: [str] — filter pool to these Είδος values (OR title match)
#   eidos_boost: [str] — +80k to items with these Είδος values
#   eidos_exclude: [str] — hard-filter OUT items with these Είδος values
#   typos_include: [str] — filter pool to these Τύπος values (OR title match)
#   typos_boost: [str] — +80k to items with these Τύπος values
#   typos_exclude: [str] — hard-filter OUT items with these Τύπος values
#   allow_kids_theme: bool — skip the global kid-theme penalty (use for kids-specific slots)
#   brand_match: bool — same brand as trigger +80k
#   connectivity_mirror: bool — match wired/wireless
#   wrist_rest_only/xxl_only: bool — filter to specific pad types
#   apple_force: str — force hierarchy for Apple
#   skip_if: str — skip slot condition ('no_battery')
#   fallback_hier: [str] — fallback if primary empty
#   silent_match/ergo_match/rgb_match: bool — attribute matching
#   dpi_pad_size: bool — DPI-based pad size selection
#   sensor_surface: bool — laser→hard, optical→cloth
#   button_kb_size: bool — button count → keyboard size
#   vesa_match: bool — VESA mount matching
#   cable_port_match: str — match cable to trigger port column
#   cable_length_boost: bool — prefer 1.5-2m cables
#   ups_min_va: int — minimum UPS VA
#   ink_model_match: bool — match ink cartridge to printer
#   toner_model_match: bool — match toner to printer
#   paper_weight_max/paper_weight_min: int — paper weight filter
#   resolution_match: bool — match webcam to monitor resolution
#   usb_version_match: bool — match USB speed
#   port_count_storage: bool — port count → storage capacity
#   hub_cable_type: bool — match cable to hub input type
#   powered_hub_only: bool — only for powered hubs
#   exclude_if_has_feature: str — hide if trigger already has this

MOUSE_SLOTS = [
    ("Mouse Pad",           ['MOUSE PADS'],                   {'title_hide': ['Gel', 'Wrist', 'Μαξιλαράκι']}),
    ("Keyboard",            ['KEYBOARDS WIRELESS', 'KEYBOARDS WIRED'], {'connectivity_mirror': True, 'brand_match': True, 'apple_force': 'APPLE ORIGINAL WIRELESS KEYBOARD', 'silent_match': True, 'ergo_match': True}),
    # --- SLOT 3: DYNAMIC ---
    ("Batteries",           ['ΑΛΚΑΛΙΚΕΣ'],                    {'skip_if_wired': True, 'title_hide': ['CR', 'Button', 'Coin', 'Λιθίου'], 'title_boost': ['AA', 'AAA']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'skip_if_wireless': True}),
    # -----------------------
    ("Overhead Headset",    ['OVERHEAD', 'GAMING AUDIO', 'PC HEADSET/MICROPHONE'], {'brand_boost': True, 'color_match_all': True}),
    ("Wrist Rest",          ['MOUSE PADS'],                   {'wrist_rest_only': True}),
    ("Cleaning",            ['CLEANING PRODUCTS'],            {'title_include': ['Αέρας', 'Σπρέι', 'Spray', 'Compressed air']}),
    ("Desk Lamp",           ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],            {'title_boost': ['Desk', 'Γραφείου'], 'title_hide': ['Ceiling', 'Bulb']}),
    ("Mouse Pad 2",         ['MOUSE PADS'],                   {'title_hide': ['Gel', 'Wrist', 'Μαξιλαράκι']}),
    ("Monitor Riser",       ['ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],              {'title_boost': ['Riser', 'Stand']}),
]

KEYBOARD_SLOTS = [
    # SWAPPED: Mouse Pad now Slot 1
    ("Desk Mat",            ['MOUSE PADS'],                   {'xxl_only': True}),
    # SWAPPED: Mouse now Slot 2
    ("Mouse",               ['MOUSE WIRELESS', 'MOUSE WIRED', 'APPLE ORIGINAL WIRELESS MOUSE'], {'connectivity_mirror': True, 'brand_match': True, 'apple_force': 'APPLE ORIGINAL WIRELESS MOUSE', 'silent_match': True, 'ergo_match': True}),
    # Slot 3 remains Dynamic (Batteries/Hub)
    ("Batteries",           ['ΑΛΚΑΛΙΚΕΣ'],                    {'skip_if_wired': True, 'title_hide': ['CR', 'Button', 'Coin', 'Λιθίου'], 'title_boost': ['AA', 'AAA']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'skip_if_wireless': True}),
    # Remaining slots
    ("Cleaning",            ['CLEANING PRODUCTS'],            {'title_include': ['Αέρας', 'Σπρέι', 'Spray']}),
    ("PC Headset",          ['PC HEADSET/MICROPHONE', 'OVERHEAD'], {}),
    ("PC Speakers",         ['PC SPEAKERS 2.0', 'PC SPEAKERS 1'], {}),
    ("Desk Lamp",           ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],            {'title_boost': ['Desk', 'Γραφείου']}),
    ("Wrist Rest",          ['MOUSE PADS'],                   {'wrist_rest_only': True}),
    ("Monitor Riser",       ['ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],              {'title_boost': ['Riser', 'Stand']}),
]

GAMING_MOUSE_SLOTS = [
    ("Gaming Pad",          ['GAMING MOUSE PADS'],            {'title_hide': ['Gel', 'Wrist'], 'brand_match': True}),
    ("Gaming Keyboard",     ['GAMING KEYBOARDS'],             {'brand_match': True, 'rgb_match': True, 'connectivity_mirror': True}),
    # Slot 3: Dynamic Batteries/Hub
    ("Batteries",           ['ΑΛΚΑΛΙΚΕΣ'],                    {'skip_if_wired': True, 'title_hide': ['CR', 'Button', 'Coin', 'Λιθίου'], 'title_boost': ['AA', 'AAA']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'skip_if_wireless': True}),
    # Mid Slots
    ("Gaming Headset",      ['GAMING AUDIO'],                 {'brand_match': True}),
    ("Αξεσουάρ Streaming",  ['STREAMING ACCESSORIES'],        {'eidos_include': ['Capture Card', 'Ring Light', 'Mic Arm']}),
    ("Cleaning Product",    ['CLEANING PRODUCTS'],            {'title_include': ['Αέρας', 'Σπρέι', 'Spray', 'Compressed air']}),
    # NEW SLOT 8: Strict Smart Lighting
    ("Smart Lighting",      ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],            {'eidos_include': ['Ταινίες LED', 'Πλακίδια'], 'title_boost': ['Strip', 'Λωρίδα Φωτισμού', 'Ταινία LED']}),
    # NEW SLOTS 9 & 10: Furniture
    ("Gaming Chair",        ['GAMING CHAIRS'],                {'price_limit_furniture': True}),
    ("Gaming Desk",         ['GAMING DESKS'],                 {'price_limit_furniture': True}),
]

GAMING_KEYBOARD_SLOTS = [
    ("Gaming Mousepad",     ['GAMING MOUSE PADS'],            {'brand_match': True, 'title_hide': ['Gel', 'Wrist']}),
    ("Gaming Mouse",        ['GAMING MOUSE'],                 {'brand_match': True, 'rgb_match': True, 'connectivity_mirror': True}),
    # Slot 3: Dynamic Batteries/Hub
    ("Batteries",           ['ΑΛΚΑΛΙΚΕΣ'],                    {'skip_if_wired': True, 'title_hide': ['CR', 'Button', 'Coin', 'Λιθίου'], 'title_boost': ['AA', 'AAA']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'skip_if_wireless': True}),
    # Mid Slots
    ("Gaming Headset",      ['GAMING AUDIO', 'OVERHEAD'],     {'brand_match': True}),
    ("Αξεσουάρ Streaming",  ['STREAMING ACCESSORIES'],        {'eidos_include': ['Capture Card', 'Ring Light', 'Mic Arm']}),
    ("Cleaning Product",    ['CLEANING PRODUCTS'],            {'title_include': ['Αέρας', 'Σπρέι', 'Spray', 'Compressed air']}),
    # NEW SLOT 8: Strict Smart Lighting
    ("Smart Lighting",      ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],            {'eidos_include': ['Ταινίες LED', 'Πλακίδια'], 'title_boost': ['Strip', 'RGB', 'LED']}),
    # NEW SLOTS 9 & 10: Furniture
    ("Gaming Chair",        ['GAMING CHAIRS'],                {'price_limit_furniture': True}),
    ("Gaming Desk",         ['GAMING DESKS'],                 {'price_limit_furniture': True}),
]



# ── Monitor sub-personas (detected from Χρήση or hierarchy) ──
MONITOR_GAMING_SLOTS = [
    ("Gaming Mouse",        ['GAMING MOUSE'],                 {'brand_match': True}),
    ("Gaming Keyboard",     ['GAMING KEYBOARDS'],             {'brand_match': True}),
    ("Gaming Mousepad",     ['GAMING MOUSE PADS'],            {'brand_match': True}),
    ("Gaming Headset",      ['GAMING AUDIO'],                 {'brand_match': True}),
    ("Gaming Chair",        ['GAMING CHAIRS'],                {}),
    ("Smart Lighting",      ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],             {'title_boost': ['Strip', 'LED', 'Bias', 'Backlight', 'RGB', 'Ταινία', 'Λεντοταινία'], 'title_hide': ['Ceiling', 'Bulb', 'Λάμπα', 'Λαμπτήρας', 'E27', 'E14', 'Οροφής', 'Επιτραπέζιο', 'Desk', 'Γραφείου']}),
    ("Steering Wheel",      ['STEERING WHEELS', 'GAMING WHEELS'], {}),
    ("Gaming Desk",         ['GAMING DESKS'],                 {}),
    ("UPS",                 ['LINE INTERACTIVE'],             {}),
    ("Video Cable",         ['DISPLAY-PORT CABLES', 'GAMING HDMI CABLES', 'MONITOR CABLES'], {}),
]

MONITOR_PRO_SLOTS = [
    ("Ergonomic Mouse",     ['MOUSE WIRELESS'],               {'ergo_match': True, 'brand_match': True, 'title_hide': ['Gaming', 'RGB']}),
    ("Wireless Keyboard",   ['KEYBOARDS WIRELESS'],           {'brand_match': True, 'title_hide': ['Gaming', 'RGB']}),
    ("USB-C Cable",         ['USB CABLES'],                   {'cable_port_match': 'USB-C', 'title_boost': ['Thunderbolt', 'USB-C']}),
    ("Webcam",              ['PC WEB CAMS'],                  {'resolution_match': True}),
    ("Monitor Arm",         ['ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],               {'vesa_match': True, 'title_boost': ['Heavy', 'UltraWide'], 'title_hide': ['CPU', 'Υπολογιστή', 'Riser', 'Drawer']}),
    ("ScreenBar",           ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],            {'title_boost': ['ScreenBar', 'Monitor Light', 'Desk', 'Γραφείου'], 'usage_hide': ['Εξωτερική', 'Εξωτερικού χώρου', 'TV']}),
    ("USB-C Hub",           ['USB HUB DEVICES', 'DOCKING STATIONS LAPTOP'], {'title_boost': ['USB-C', 'Thunderbolt', 'Dock']}),
    ("PC Speakers",         ['PC SPEAKERS 2.0'],              {}),
    ("Screen Cleaner",      ['CLEANING PRODUCTS'],            {}),
    ("UPS",                 ['LINE INTERACTIVE'],    {}),
]

MONITOR_MAINSTREAM_SLOTS = [
    ("Keyboard x Mouse Set", ['DESKTOP KEYBOARDS', 'MOUSE WIRELESS'], {'title_boost': ['Set', 'Combo', 'Desktop'], 'persona_match': ['Γραφείο', 'Υπολογιστής', 'Mac']}),
    ("Speakers 2.0",         ['SPEAKERS'],                     {'title_boost': ['2.0'], 'title_hide': ['2.1', '5.1', 'Subwoofer', 'Soundbar']}),
    ("Mousepad",             ['MOUSE PADS'],                   {'title_hide': ['Gaming', 'RGB']}),
    ("Headphones",           ['OVERHEAD'],                     {'title_hide': ['Gaming', 'RGB']}),
    ("Webcam",               ['WEB CAMERAS'],                  {}),
    ("USB Hub",              ['USB HUB'],                      {}),
    ("USB Stick",            ['USB FLASH'],                    {}),
    ("Screen Cleaner",       ['SCREEN CLEANER'],               {}),
    ("Printer",              ['PRINTERS'],                     {}),
    ("UPS",                  ['LINE INTERACTIVE'],             {}),
]



# ═════════════════════════════════════════════════════════════
# 🟢 STATIONERY ENGINE — Writing & Correction + Arts & Crafts
# Config-driven: reuses peripherals engine infrastructure
# (STATIONERY_TRIGGERS and STATIONERY_CLUSTERS defined at top of file)
# ═════════════════════════════════════════════════════════════

# ── Slot configs ──

PENS_SLOTS = [
    ("Alt Color Pen 1",   ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'match_pen_variant': True}),
    ("Alt Color Pen 2",   ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'match_pen_variant': True}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'Medium', 'Standard'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας', 'Ριζόχαρτο']}),
    ("Correction",        ['ΓΟΜΕΣ', 'ΔΙΟΡΘΩΤΙΚΑ'],                        {'match_writing_type': True, 'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Ταινία', 'Roller']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                    {'title_boost': ['Pastel', '4-pack', '6-pack'], 'title_hide': ['Whiteboard', 'Πίνακα', 'CD-DVD', 'Ανεξίτηλ']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {'title_boost': ['Zipper', 'Φερμουάρ', 'Simple', 'Basic']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['3x3', 'Small', 'Square', 'Yellow']}),
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Μηχανικό Μολύβι', 'Απλό Μολύβι'], 'title_boost': ['HB', '2B', 'Set', 'Pack']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ', 'ΟΡΓΑΝΑ ΜΕΤΡΗΣΗΣ'],      {'title_boost': ['Ruler', 'Χάρακας', '15cm', '20cm', '30cm'], 'title_hide': ['Compass', 'Protractor', 'Set']}),
    ("Specialty Pen",     ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'title_boost': ['Fountain', 'Πένα', 'Fine liner', 'Fineliner', 'Calligraphy', 'Erasable', 'Metal', 'Luxury', 'Premium', 'Καλλιγραφίας']}),
]

PENCILS_SLOTS = [
    ("Matching Accessory",['ΜΟΛΥΒΙΑ', 'ΞΥΣΤΡΕΣ'],                         {'match_writing_type': True}),
    ("Sharpener",         ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Βαρελάκι', 'Κλασική', 'Με γόμα'], 'title_boost': ['Metal', 'Dual', 'Μεταλλική', 'Διπλή'], 'title_hide': ['Ηλεκτρική']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Λευκή', 'Soft', 'Μαλακή', 'Staedtler', 'Faber'], 'title_hide': ['Ταινία', 'Υγρό', 'Διορθωτικ']}),
    ("Alt Pencils",       ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μηχανικό Μολύβι', 'Με Γόμα'], 'title_boost': ['Set', 'Σετ', 'HB', '2B', '4B', '6B', 'Pack']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {'title_boost': ['Large', 'Μεγάλη', 'Compartment', 'Θήκες', 'Zipper', 'Φερμουάρ']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'title_boost': ['Black', 'Blue', 'Μαύρο', 'Μπλε']}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων', 'Σχεδίου'], 'title_boost': ['A4', 'A5', 'Lined', 'Γραμμές', 'Καρέ'], 'title_hide': ['Ακουαρέλας', 'Ιχνογραφίας', 'Πολυγράφου', 'Κολάζ', 'Ριζόχαρτο']}),
    ("Mechanical Lead",   ['ΜΟΛΥΒΙΑ'],                                    {'typos_include': ['Μύτες για Μηχανικό Μολύβι'], 'title_boost': ['0.5', '0.7', 'HB', '2B']}),
    ("Geometric Tools",   ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ', 'ΟΡΓΑΝΑ ΜΕΤΡΗΣΗΣ'],      {'title_boost': ['Ruler', 'Χάρακας', '15cm', '20cm', '30cm'], 'title_hide': ['Compass', 'Protractor', 'Set']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                    {'title_boost': ['Pastel', '4-pack', 'Soft'], 'title_hide': ['Permanent', 'Whiteboard', 'Neon']}),
]

MARKERS_SLOTS = [
    # Default fallback: used only for truly generic "ΜΑΡΚΑΔΟΡΟΙ" triggers without clear type in title.
    # Most triggers get routed to HIGHLIGHTERS / WHITEBOARD / PERMANENT / WRITING / DRAWING variants above.
    ("Alt Color Marker 1",['ΜΑΡΚΑΔΟΡΟΙ'], {'match_marker_variant': True}),
    ("Alt Color Marker 2",['ΜΑΡΚΑΔΟΡΟΙ'], {'match_marker_variant': True}),
    ("Coloring Pad 1",    ['ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ', 'COLORING BOOKS'], {'match_coloring_activity': True, 'match_nib_type': True}),
    ("Coloring Pad 2",    ['ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ', 'COLORING BOOKS'], {'match_coloring_activity': True, 'match_nib_type': True}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'match_nib_type': True, 'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A4', 'A5', 'Lined', 'Γραμμές'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας', 'Ριζόχαρτο']}),
    ("Alt Markers",       ['ΜΑΡΚΑΔΟΡΟΙ'], {'match_nib_type': True, 'title_boost': ['Pastel', 'Neon', '12-pack', 'Extended']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],           {'title_boost': ['Black', 'Blue', '0.7mm']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ', 'ΣΕΛΙΔΟΔΕΙΚΤΕΣ'], {'title_boost': ['Arrow', 'Flag', 'Index', 'Σημάδια']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {'title_boost': ['Wide', 'Large', 'Compartment', 'Φαρδιά']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'title_boost': ['Tape', 'Roller']}),
]

# ── Highlighters-specific slots (ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ) ──
# Used when trigger hierarchy = ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ (most highlighters are multi-packs).
# Priority: alt highlighter packs first (brand match), then study-accessories.
HIGHLIGHTERS_SLOTS = [
    ("Alt Color Marker 1",['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'], {'match_marker_variant': True}),
    ("Alt Highlighter Pack",['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'], {'title_boost': ['Pastel', 'Neon', '4-pack', '6-pack', '4 Τεμάχια', '6 Τεμάχια', 'Set'], 'title_hide': ['Permanent', 'Whiteboard', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Alt Nib Style",     ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'], {'match_nib_type': True, 'title_boost': ['Mini', 'Pocket', 'Soft', 'Light'], 'title_hide': ['Permanent', 'Whiteboard', 'Πίνακα']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ', 'ΣΕΛΙΔΟΔΕΙΚΤΕΣ'], {'eidos_boost': ['Σελιδοδείκτες'], 'title_boost': ['Index', 'Flag', 'Σημάδια', 'Tabs']}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'], {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A4', 'A5', 'Lined', 'Γραμμές'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας', 'Ριζόχαρτο']}),
    ("Pen",               ['ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'title_boost': ['Black', 'Blue', 'Erasable', '0.7']}),
    ("Pencil",            ['ΜΟΛΥΒΙΑ'], {'typos_boost': ['Μηχανικό Μολύβι', 'Απλό Μολύβι'], 'title_boost': ['HB', '2B', 'Mechanical']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'], {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Roller']}),
    ("Eraser",            ['ΓΟΜΕΣ'], {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Λευκή', 'Soft']}),
]

# ── Whiteboard Markers-specific slots (ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ) ──
# Key insight from user: show other whiteboard markers + ΒΟΗΘΗΤΙΚΑ ΠΑΡΟΥΣΙΑΣΗΣ first.
WHITEBOARD_MARKERS_SLOTS = [
    ("Alt Whiteboard 1",  ['ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ'], {'match_marker_variant': True}),
    ("Alt Whiteboard 2",  ['ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ'], {'match_nib_type': True, 'title_boost': ['Set', 'Pack', 'Πακέτο', '4 Τεμάχια', '6 Τεμάχια']}),
    ("Whiteboard Eraser", ['ΒΟΗΘΗΤΙΚΑ ΠΑΡΟΥΣΙΑΣΗΣ'], {'title_include': ['Σβήστρα', 'Σβηστήρα', 'Γόμα Πίνακα', 'Σπόγγος', 'Σπογγάκι', 'Eraser', 'Whiteboard eraser']}),
    ("Whiteboard Cleaner",['ΒΟΗΘΗΤΙΚΑ ΠΑΡΟΥΣΙΑΣΗΣ'], {'title_include': ['Cleaner', 'Spray', 'Καθαριστικό', 'Καθαρισμός', 'Υγρό', 'Whiteboard fluid']}),
    ("Presentation Acc.", ['ΒΟΗΘΗΤΙΚΑ ΠΑΡΟΥΣΙΑΣΗΣ'], {'title_include': ['Magnet', 'Μαγνήτ', 'Pointer', 'Δείκτης', 'Pin', 'Flipchart', 'Chart']}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'], {'eidos_boost': ['Σημειώσεων'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
    ("Permanent Marker",  ['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ'], {'title_boost': ['Ανεξίτηλος', 'Permanent', 'Fine', 'Medium'], 'title_hide': ['Γραφής', 'Twin', 'Writing']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'], {'title_boost': ['Large', 'Μεγάλο']}),
    ("Pen",               ['ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ'], {'title_boost': ['Black', 'Blue']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
]

# ── Writing Markers slots (Μαρκαδόροι Γραφής — fine-tip writing/drawing markers like Pilot Twin) ──
# These are typically fine-tip black/blue markers for writing, often filed under ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ
# but they're NOT whiteboard or highlighter — they're writing markers.
WRITING_MARKERS_SLOTS = [
    ("Alt Writing Color 1",['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ', 'ΜΑΡΚΑΔΟΡΟΙ'], {'match_marker_variant': True, 'eidos_boost': ['Μαρκαδόροι Γραφής'], 'title_boost': ['Γραφής', 'Fine', 'Twin'], 'title_hide': ['Πίνακα', 'Υπογράμμισης', 'Ζωγραφικής', 'Whiteboard', 'Highlighter', 'Board marker']}),
    ("Alt Writing Color 2",['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ', 'ΜΑΡΚΑΔΟΡΟΙ'], {'match_marker_variant': True, 'eidos_boost': ['Μαρκαδόροι Γραφής'], 'title_boost': ['Γραφής', 'Fine', 'Twin'], 'title_hide': ['Πίνακα', 'Υπογράμμισης', 'Ζωγραφικής', 'Whiteboard', 'Highlighter', 'Board marker']}),
    ("Fine Pen Companion",['ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ'], {'typos_boost': ['Gel', 'Υγρής Μελάνης', 'Fine'], 'title_boost': ['Fine', 'Black', 'Blue', '0.5', '0.7']}),
    ("More Writing Markers",['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ', 'ΜΑΡΚΑΔΟΡΟΙ'], {'eidos_boost': ['Μαρκαδόροι Γραφής'], 'title_boost': ['Γραφής', 'Fine', 'Twin', 'Dual'], 'title_hide': ['Πίνακα', 'Υπογράμμισης', 'Ζωγραφικής', 'Whiteboard', 'Highlighter']}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'], {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'A4', 'Lined', 'Γραμμές'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας', 'Ριζόχαρτο']}),
    ("Permanent Marker",  ['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ'], {'title_boost': ['Ανεξίτηλος', 'Permanent', 'CD', 'DVD'], 'title_hide': ['Πίνακα']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ', 'ΣΕΛΙΔΟΔΕΙΚΤΕΣ'], {'title_boost': ['Flag', 'Arrow', 'Index']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'], {'title_boost': ['Pastel', '4-pack', '6-pack']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'], {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Roller']}),
]

# ── Permanent Markers-specific slots (ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ) ──
# NOTE: Data mixes writing markers (Μαρκαδόρος Γραφής) into this hierarchy.
# We hide "Γραφής" titles to keep TRUE permanent markers in alt slots.
PERMANENT_MARKERS_SLOTS = [
    ("Alt Permanent 1",   ['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ'], {'match_marker_variant': True, 'title_boost': ['Ανεξίτηλος', 'Permanent'], 'title_hide': ['Γραφής', 'Twin', 'Fine writing']}),
    ("Alt Permanent 2",   ['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ'], {'match_nib_type': True, 'title_boost': ['Ανεξίτηλος', 'Permanent', 'Fine', 'Medium', 'Chisel', 'Λεπτή', 'Μεσαία'], 'title_hide': ['Γραφής', 'Twin']}),
    ("CD/DVD Marker",     ['ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ'], {'title_boost': ['CD', 'DVD', 'Ultra fine', '0.4', '0.7']}),
    ("Label Maker",       ['ΒΟΗΘΗΤΙΚΑ ΠΑΡΟΥΣΙΑΣΗΣ', 'ΕΤΙΚΕΤΕΣ'], {'title_boost': ['Label', 'Ετικέτα', 'Sticker', 'Αυτοκόλλητ']}),
    ("Whiteboard Marker", ['ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ'], {}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'], {'eidos_boost': ['Σημειώσεων'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'], {}),
    ("Pen",               ['ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ'], {'title_boost': ['Black', 'Blue']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'], {'title_boost': ['Tape']}),
]

SHARPENERS_SLOTS = [
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Με Γόμα'], 'title_boost': ['HB', '2B', 'School', 'Student', 'Σχολικά'], 'title_hide': ['Μηχανικό']}),
    ("Alt Sharpener",     ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Βαρελάκι', 'Με γόμα', 'Με Μανιβέλα'], 'title_boost': ['Dual', 'Double', 'Container', 'Δοχείο']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Λευκή', 'Soft', 'Pencil', 'Μολυβιού'], 'title_hide': ['Ταινία', 'Υγρό', 'Διορθωτικ']}),
    ("Colored Pencils",   ['ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ'],                        {'eidos_boost': ['Κλασσικές Ξυλομπογιές'], 'title_boost': ['12', '18', '24', 'Kids', 'Παιδικά']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'Lined', 'Grid', 'Καρέ'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],          {'typos_boost': ['Gel'], 'title_boost': ['Black', 'Blue', 'Μαύρο', 'Μπλε']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ'],                          {'title_boost': ['Ruler', 'Χάρακας', '30cm']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Roller', 'Ταινία']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', '3x3', 'Yellow', 'Κίτρινο']}),
]

ERASERS_SLOTS = [
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μηχανικό Μολύβι', 'Με Γόμα'], 'title_boost': ['HB', '2B', 'School', 'Student']}),
    ("Sharpener",         ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Βαρελάκι', 'Με γόμα', 'Κλασική'], 'title_boost': ['Dual', 'Container', 'Metal', 'Διπλή', 'Δοχείο']}),
    ("Alt Eraser",        ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['Precision', 'Mechanical', 'Pen-style', 'Ακριβείας'], 'title_hide': ['Ταινία', 'Υγρό']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία', 'Διορθωτικό Υγρό', 'Διορθωτικό Στυλό'], 'title_boost': ['Tape', 'Roller', 'Ταινία']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'Lined', 'Grid'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],          {'typos_boost': ['Gel'], 'title_boost': ['Black', 'Blue', 'Μαύρο', 'Μπλε']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ'],                          {'title_boost': ['Ruler', 'Χάρακας', '30cm']}),
    ("Colored Pencils",   ['ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ'],                        {}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', '3x3', 'Yellow']}),
]

CORRECTION_SLOTS = [
    ("Alt Correction",    ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία', 'Διορθωτικό Υγρό', 'Διορθωτικό Στυλό'], 'title_boost': ['Tape', 'Roller', 'Ταινία']}),
    ("Correction Refill", ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_include': ['Ανταλλακτικά'], 'title_boost': ['Refill', 'Ανταλλακτικό']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'typos_boost': ['Gel', 'Υγρής Μελάνης'], 'title_boost': ['Black', 'Blue', '0.7mm', 'Medium']}),
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Μηχανικό Μολύβι', 'Με Γόμα'], 'title_boost': ['HB', '2B', 'Mechanical', 'Μηχανικό']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Soft', 'Λευκή', 'Μαλακή'], 'title_hide': ['Ταινία', 'Υγρό', 'Διορθωτικ']}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A4', 'A5', 'Lined', 'Γραμμές'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας', 'Ριζόχαρτο', 'Κολάζ']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                    {'title_boost': ['Pastel', '4-pack', '6-pack'], 'title_hide': ['Whiteboard', 'Permanent', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {'title_boost': ['Simple', 'Zipper', 'Compact']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', '3x3', 'Yellow', 'Κίτρινο']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ'],                          {'title_boost': ['Ruler', 'Χάρακας', '30cm', 'Transparent']}),
]

PENCIL_CASES_SLOTS = [
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'typos_boost': ['Gel', 'Διαρκείας']}),
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μηχανικό Μολύβι', 'Με Γόμα'], 'title_boost': ['HB', '2B', 'Pack', 'School']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Soft', 'Small', 'Λευκή', 'Μικρή'], 'title_hide': ['Ταινία', 'Υγρό', 'Διορθωτικ']}),
    ("Sharpener",         ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Βαρελάκι', 'Κλασική', 'Με γόμα'], 'title_boost': ['Compact', 'Dual', 'Container', 'Μικρή', 'Με δοχείο']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                    {'title_boost': ['4-pack', 'Basic', 'Compact']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ', 'ΟΡΓΑΝΑ ΜΕΤΡΗΣΗΣ'],      {'title_boost': ['15cm', '20cm', 'Flexible', 'Εύκαμπτος']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτικό Στυλό', 'Διορθωτική Ταινία'], 'title_boost': ['Pen', 'Compact', 'Mini', 'Στυλό', 'Μίνι']}),
    ("Colored Pencils",   ['ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ'],                        {'eidos_boost': ['Κλασσικές Ξυλομπογιές'], 'title_boost': ['12', '24', 'Set']}),
    ("Alt Case",          ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'Lined', 'Grid', 'Καρέ'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
]

GEOMETRIC_TOOLS_SLOTS = [
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Μηχανικό Μολύβι', 'Απλό Μολύβι'], 'title_boost': ['HB', '2B', '4B', 'Technical', 'Τεχνικά', 'Set']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Λευκή', 'Precision', 'Ακριβείας'], 'title_hide': ['Ταινία', 'Υγρό']}),
    ("Sharpener",         ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Βαρελάκι', 'Κλασική'], 'title_boost': ['Metal', 'Dual', 'Premium', 'Μεταλλική']}),
    ("Drawing Pad",       ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ', 'ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'eidos_boost': ['Μιλιμετρέ', 'Σχεδίου', 'Μπλοκ σχεδίου', 'Ημιλογαριθμικό', 'Λογαριθμικό', 'Χαρτογραφίας'], 'title_boost': ['Grid', 'Graph', 'Καρέ', 'Μιλιμετρέ', 'Technical']}),
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],          {'typos_boost': ['Gel', 'Fine'], 'title_boost': ['0.5mm', '0.7mm', 'Fine', 'Technical', 'Λεπτή μύτη']}),
    ("Alt Tools",         ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ', 'ΟΡΓΑΝΑ ΣΧΕΔΙΑΣΗΣ', 'ΟΡΓΑΝΑ ΜΕΤΡΗΣΗΣ'], {'title_boost': ['Set', 'Compass', 'Protractor', 'Σετ', 'Διαβήτης']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'],           {}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                   {'title_boost': ['Pastel', '4-pack', 'Thin', 'Λεπτή']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Precision', 'Ταινία', 'Ακριβείας']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', 'Flag', 'Arrow', 'Σημάδια']}),
]

STATIONERY_SETS_SLOTS = [
    ("Notebook",          ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ'],                  {'eidos_boost': ['Σημειώσεων'], 'title_boost': ['A5', 'Lined', 'Grid', 'Γραμμές', 'Καρέ'], 'title_hide': ['Ιχνογραφίας', 'Πολυγράφου', 'Ακουαρέλας']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΜΟΛΥΒΟΘΗΚΕΣ'], {}),
    ("Refill Pens",       ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],          {'typos_boost': ['Gel', 'Ανταλλακτικά'], 'title_boost': ['Blue', 'Black', '10-pack', 'Μπλε', 'Μαύρο', 'Refill']}),
    ("Refill Pencils",    ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μύτες για Μηχανικό Μολύβι'], 'title_boost': ['HB', '2B', '12-pack', 'School']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                   {'title_boost': ['Pastel', '4-pack', '6-pack']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Roller', 'Compact']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', '3x3', 'Assorted', 'Ποικιλία']}),
    ("Geometric Tools",   ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ', 'ΟΡΓΑΝΑ ΣΧΕΔΙΑΣΗΣ'],     {'title_boost': ['Ruler', 'Set', '30cm', 'Χάρακας']}),
    ("Eraser/Sharpener",  ['ΓΟΜΕΣ', 'ΞΥΣΤΡΕΣ'],                          {'eidos_boost': ['Γόμα', 'Βαρελάκι']}),
    ("Alt Set",           ['ΣΕΤ ΧΑΡΤΙΚΩΝ', 'ΣΕΤ ΖΩΓΡΑΦΙΚΗΣ'],           {}),
]

PAINTS_SLOTS = [
    ("Brushes",           ['ΠΙΝΕΛΑ'],                                     {'match_art_medium': True, 'eidos_boost': ['Ακουαρέλας', 'Ακρυλικού', 'Λαδιού', 'Νερού', 'Σετ'], 'title_boost': ['Set', 'Σετ', 'Assorted', 'Round', 'Flat', 'Ποικιλία']}),
    ("Canvas/Paper",      ['ΚΑΜΒΑΔΕΣ', 'ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'match_art_medium': True, 'eidos_boost': ['Ακουαρέλας', 'Ζωγραφικής', 'Καμβάς', 'Λαδιού', 'Μπλοκ σχεδίου'], 'title_boost': ['Stretched', 'Τελαρωμένος', 'Set', 'Pack']}),
    ("Water Cup",         ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Water', 'Brush cleaner', 'Νερού', 'Καθαρισμού', 'Double']}),
    ("Palette",           ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Palette', 'Παλέτα', 'Mixing', 'Plastic', 'Πλαστική']}),
    ("Alt Paints",        ['ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ'],                        {'typos_boost': ['Ακουαρέλα', 'Ακρυλικό', 'Ακρυλικά Χρώματα', 'Λαδιού', 'Νερομπογιά', 'Τέμπερα'], 'title_boost': ['Professional', 'Artist', 'Large', 'Μεγάλο', 'Επαγγελματικό']}),
    ("Easel",             ['ΚΑΒΑΛΕΤΑ'],                                   {'title_boost': ['Table', 'Desktop', 'Portable', 'Επιτραπέζιο', 'Φορητό']}),
    ("Sketch Pencil",     ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι'], 'title_boost': ['HB', '2B', 'Sketch', 'Drawing', 'Σκίτσου']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['Kneaded', 'Putty', 'Art', 'Ζύμης', 'Πλαστική'], 'title_hide': ['Ταινία', 'Υγρό']}),
    ("Paint Accessories", ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Sponge', 'Σφουγγάρι', 'Palette knife', 'Σπάτουλα', 'Roller']}),
    ("Apron",             ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Apron', 'Smock', 'Kids', 'Waterproof', 'Παιδική', 'Αδιάβροχη']}),
]

BRUSHES_SLOTS = [
    ("Paints",            ['ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ'],                        {'match_art_medium': True, 'typos_boost': ['Ακουαρέλα', 'Ακρυλικό', 'Ακρυλικά Χρώματα', 'Λαδιού', 'Νερομπογιά', 'Τέμπερα']}),
    ("Canvas/Paper",      ['ΚΑΜΒΑΔΕΣ', 'ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'match_art_medium': True, 'eidos_boost': ['Ακουαρέλας', 'Καμβάς', 'Λαδιού', 'Ζωγραφικής']}),
    ("Brush Cleaner",     ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Water', 'Brush cleaner', 'Soap', 'Νερού', 'Double']}),
    ("Brush Case",        ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ', 'ΘΗΚΕΣ ΜΕΤΑΦΟΡΑΣ'], {'title_boost': ['Brush holder', 'Brush case', 'Roll', 'Θήκη πινέλων', 'Bamboo', 'Ρολό']}),
    ("Palette",           ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Palette', 'Παλέτα', 'Plastic', 'Tear-off', 'Αποσπώμενη']}),
    ("Alt Brushes",       ['ΠΙΝΕΛΑ'],                                     {'eidos_boost': ['Flat', 'Round', 'Ακουαρέλας', 'Ακρυλικού', 'Λαδιού', 'Σετ', 'Βεντάλια', 'Rigger', 'Flibert']}),
    ("Sketch Pencil",     ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι'], 'title_boost': ['2B', '4B', 'Sketch', 'Drawing']}),
    ("Easel",             ['ΚΑΒΑΛΕΤΑ'],                                   {'title_boost': ['Table', 'Desktop', 'Portable', 'Επιτραπέζιο']}),
    ("Paint Accessories", ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Palette knife', 'Sponge', 'Σπάτουλα', 'Σφουγγάρι']}),
    ("Apron",             ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Apron', 'Artist', 'Painter', 'Waterproof']}),
]

COLORED_PENCILS_ART_SLOTS = [
    ("Drawing Paper",     ['ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'match_art_medium': True, 'eidos_boost': ['Σχεδίου', 'Μπλοκ σχεδίου', 'Ζωγραφικής', 'Ακουαρέλας'], 'title_boost': ['Sketch', 'Drawing', 'Student', 'Σχεδίου', 'A4', 'A5']}),
    ("Sharpener",         ['ΞΥΣΤΡΕΣ'],                                    {'eidos_boost': ['Κλασική', 'Με γόμα', 'Βαρελάκι'], 'title_boost': ['Metal', 'Dual', 'Container', 'Μεταλλική', 'Δοχείο']}),
    ("Eraser",            ['ΓΟΜΕΣ', 'ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],            {'eidos_boost': ['Γόμα'], 'title_boost': ['Kneaded', 'Putty', 'Precision', 'Ζύμης', 'Ακριβείας'], 'title_hide': ['Ταινία', 'Υγρό']}),
    ("Art Case",          ['ΘΗΚΕΣ ΜΕΤΑΦΟΡΑΣ', 'ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ'],        {'title_boost': ['Art case', 'Portfolio', 'Large', 'Professional']}),
    ("Sketch Pencil",     ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μηχανικό Μολύβι'], 'title_boost': ['Sketch', 'Drawing', 'HB', '2B', '4B', '6B', 'Set']}),
    ("Alt Colored",       ['ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ', 'ΚΗΡΟΜΠΟΓΙΕΣ-ΠΑΣΤΕΛ'],  {'eidos_boost': ['Κλασσικές Ξυλομπογιές', 'Ξυλομπογιές Ακουαρέλας', 'Ξυλομπογιές Κραγιόν', 'Μισό - Μισό']}),
    ("Crayons/Pastels",   ['ΚΗΡΟΜΠΟΓΙΕΣ-ΠΑΣΤΕΛ'],                        {'eidos_boost': ['Κηρομπογιά', 'Κραγιόν', 'Λαδοπαστέλ']}),
    ("Fine Liners",       ['ΜΑΡΚΑΔΟΡΟΙ', 'ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ'],      {'title_boost': ['Fine liner', 'Micron', '0.1mm', '0.3mm', '0.5mm'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Fixative",          ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ', 'ACCESSORIES ΧΕΙΡΟΤΕΧΝΙΑΣ'], {'title_boost': ['Fixative', 'Portfolio', 'Storage', 'Folder']}),
    ("Markers",           ['ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ', 'ACCESSORIES ΧΕΙΡΟΤΕΧΝΙΑΣ'], {}),
]

DRAWING_MARKERS_SLOTS = [
    ("Marker Paper",      ['ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'match_art_medium': True, 'eidos_boost': ['Μπλοκ σχεδίου', 'Σχεδίου', 'Ζωγραφικής'], 'title_boost': ['Marker', 'Bristol', 'Bleedproof', 'Mixed media', 'Μαρκαδόρων', 'Smooth']}),
    # Adult drawing markers often live under ΜΑΡΚΑΔΟΡΟΙ (Copic, Winsor & Newton, etc.)
    # Exclude highlighters/whiteboard/permanent so we only pick art markers.
    ("Alt Markers",       ['ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ', 'ΜΑΡΚΑΔΟΡΟΙ'],        {'title_boost': ['Copic', 'Sketch', 'Brush', 'Dual', 'Twin', 'Art', 'Illustration', 'Winsor'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ', 'Whiteboard', 'Permanent', 'Highlighter', 'CD', 'DVD']}),
    ("Fine Liners",       ['ΜΑΡΚΑΔΟΡΟΙ', 'ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ'],       {'title_boost': ['Fine liner', 'Micron', '0.1mm', '0.3mm', '0.5mm', 'Σχεδίου'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ', 'Whiteboard']}),
    ("Colored Pencils",   ['ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ', 'ΚΗΡΟΜΠΟΓΙΕΣ-ΠΑΣΤΕΛ'],  {'typos_boost': ['Ακρυλικό', 'Κάρβουνο'], 'title_boost': ['24', '36', '48', 'Professional', 'Artist']}),
    ("Blending/Extra",    ['ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ', 'ΜΑΡΚΑΔΟΡΟΙ', 'ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'], {'title_boost': ['Blender', 'Colorless', 'Ανάμειξης', 'Άχρωμος'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Marker Case",       ['ΘΗΚΕΣ ΜΕΤΑΦΟΡΑΣ', 'ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ'],        {'title_boost': ['Marker case', 'Elastic', 'Roll', 'Art case']}),
    ("Sketch Pencil",     ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Μηχανικό Μολύβι', 'Απλό Μολύβι'], 'title_boost': ['HB', '2B', 'Mechanical', 'Sketch']}),
    ("White Gel Pen",     ['ΣΤΥΛΟ GEL', 'ΜΑΡΚΑΔΟΡΟΙ'],                   {'title_boost': ['White', 'Metallic', 'Gel pen', 'Paint marker', 'Gold', 'Silver'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Portfolio",         ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ', 'ACCESSORIES ΧΕΙΡΟΤΕΧΝΙΑΣ'], {'title_boost': ['Portfolio', 'Storage', 'Art folder']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['Kneaded', 'Precision', 'Mechanical', 'Ζύμης'], 'title_hide': ['Ταινία', 'Υγρό']}),
]

ART_PAPER_SLOTS = [
    ("Art Supplies",      ['ΧΡΩΜΑΤΑ ΖΩΓΡΑΦΙΚΗΣ', 'ΧΡΩΜΑΤΙΣΤΑ ΜΟΛΥΒΙΑ', 'ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ'], {'match_art_medium': True, 'typos_boost': ['Ακουαρέλα', 'Ακρυλικό', 'Ακρυλικά Χρώματα', 'Λαδιού', 'Νερομπογιά', 'Τέμπερα']}),
    ("Brushes",           ['ΠΙΝΕΛΑ'],                                     {'match_art_medium': True, 'eidos_boost': ['Ακουαρέλας', 'Ακρυλικού', 'Λαδιού', 'Νερού', 'Σετ'], 'title_boost': ['Set', 'Σετ', 'Assorted']}),
    ("Palette",           ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Palette', 'Παλέτα', 'Mixing']}),
    ("Water Cup",         ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Water cup', 'Brush cleaner', 'Νερού']}),
    ("Sketch Pencil",     ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Απλό Μολύβι', 'Μηχανικό Μολύβι'], 'title_boost': ['2B', '4B', 'Sketch', 'Drawing', 'HB']}),
    ("Alt Paper",         ['ΜΠΛΟΚ-ΧΑΡΤΙΑ', 'ΧΑΡΤΙΑ - ΜΠΛΟΚ', 'ΜΠΛΟΚ - ΧΑΡΤΙΑ ΖΩΓΡΑΦΙΚΗΣ'], {'eidos_boost': ['Ακουαρέλας', 'Ζωγραφικής', 'Σχεδίου', 'Μπλοκ σχεδίου', 'Ριζόχαρτο', 'Κολάζ']}),
    ("Eraser",            ['ΓΟΜΕΣ', 'ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],            {'eidos_boost': ['Γόμα'], 'title_boost': ['Kneaded', 'Putty', 'Precision', 'Masking'], 'title_hide': ['Ταινία', 'Υγρό']}),
    ("Detail Tools",      ['ΜΑΡΚΑΔΟΡΟΙ', 'ΠΙΝΕΛΑ'],                       {'title_boost': ['Fine', 'Detail', 'Liner', 'Small', '0.1mm', '0.3mm'], 'title_hide': ['Υπογράμμισης', 'Πίνακα', 'Ανεξίτηλ']}),
    ("Fixative",          ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ'],                     {'title_boost': ['Portfolio', 'Storage', 'Folder', 'Φάκελος', 'Fixative']}),
    ("Accessories",       ['ACCESSORIES ΖΩΓΡΑΦΙΚΗΣ', 'ACCESSORIES ΧΕΙΡΟΤΕΧΝΙΑΣ'], {'title_boost': ['Sponge', 'Palette knife', 'Scissors', 'Σπάτουλα']}),
]

NOTEBOOKS_SLOTS = [
    ("Pen",               ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'],          {'typos_boost': ['Gel', 'Υγρής Μελάνης'], 'title_boost': ['Blue', 'Black', 'Red', 'Multi-color', '4-pack', '6-pack', '10-pack', 'Μπλε', 'Μαύρο']}),
    ("Pencil",            ['ΜΟΛΥΒΙΑ'],                                    {'typos_boost': ['Μηχανικό Μολύβι', 'Απλό Μολύβι'], 'title_boost': ['HB', '2B', 'School', 'Pack', '12-pack', 'Σχολικά']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                   {'title_boost': ['Pastel', 'Neon', 'Bright', '4-pack', '6-pack', 'Φωτεινά']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Small', '3x3', 'Flag', 'Arrow', 'Colorful', 'Χρωματιστά']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία'], 'title_boost': ['Tape', 'Roller', 'Pen', 'Compact']}),
    ("Pencil Case",       ['ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ', 'ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ'],    {'title_boost': ['Colorful', 'Fun', 'Simple', 'Zipper', 'School', 'Σχολική']}),
    ("Bookmarks",         ['ΣΕΛΙΔΟΔΕΙΚΤΕΣ', 'POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'], {'eidos_boost': ['Σελιδοδείκτες'], 'title_boost': ['Bookmark', 'Σελιδοδείκτης', 'Magnetic', 'Μαγνητικός']}),
    ("Ruler",             ['ΓΕΩΜΕΤΡΙΚΑ ΟΡΓΑΝΑ'],                          {'title_boost': ['15cm', '20cm', '30cm', 'Transparent', 'Flexible', 'Διάφανος']}),
    ("Sharpener/Eraser",  ['ΞΥΣΤΡΕΣ', 'ΓΟΜΕΣ'],                          {'eidos_boost': ['Γόμα', 'Βαρελάκι', 'Κλασική'], 'title_boost': ['Dual', 'Container', 'Colorful', 'White', 'Soft']}),
    ("More Notebooks",    ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ'],                              {'title_boost': ['Different color', 'Pack', 'Set', 'Grid', 'Ruled', 'Καρέ', 'Dot', 'Blank']}),
]

NOTEPADS_SLOTS = [
    ("Pro Pen",           ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL', 'ΣΤΥΛΟ ΔΙΑΡΚΕΙΑΣ'], {'typos_boost': ['Gel', 'Διαρκείας', 'Υγρής Μελάνης'], 'title_boost': ['Black', 'Blue', '0.7mm', 'Premium', 'Professional', 'Executive', 'Μαύρο', 'Μπλε'], 'title_hide': ['Multi-color', 'Glitter', 'Kids', 'Παιδικό']}),
    ("Mechanical Pencil", ['ΜΟΛΥΒΙΑ'],                                    {'typos_include': ['Μηχανικό Μολύβι', 'Μύτες για Μηχανικό Μολύβι'], 'title_boost': ['Mechanical', '0.5mm', '0.7mm', 'Professional', 'Executive', 'Μηχανικό']}),
    ("Highlighter",       ['ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ'],                   {'title_boost': ['Pastel', 'Subtle', 'Classic', 'Yellow', '4-pack'], 'title_hide': ['Neon', 'Glitter', 'Kids']}),
    ("Sticky Notes",      ['POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'],               {'title_boost': ['Yellow', 'Classic', '3x3', 'Professional', 'Lined'], 'title_hide': ['Fun shapes', 'Colorful', 'Kids']}),
    ("Correction",        ['ΔΙΟΡΘΩΤΙΚΑ'],                                 {'eidos_boost': ['Διορθωτική Ταινία', 'Διορθωτικό Στυλό'], 'title_boost': ['Tape', 'Roller', 'Professional', 'Ταινία']}),
    ("Desk Organizer",    ['ΜΟΛΥΒΟΘΗΚΕΣ'],                               {'title_boost': ['Desk organizer', 'Pen holder', 'Professional', 'Metal', 'Γραφείου']}),
    ("Page Flags",        ['ΣΕΛΙΔΟΔΕΙΚΤΕΣ', 'POST-IT-ΧΑΡΤΑΚΙΑ ΣΗΜΕΙΩΣΕΩΝ'], {'eidos_boost': ['Σελιδοδείκτες'], 'title_boost': ['Flag', 'Arrow', 'Index', 'Bookmark', 'Professional']}),
    ("Dividers",          ['ΔΙΑΧΩΡΙΣΤΙΚΑ'],                               {'title_boost': ['File divider', 'Folder', 'Tabbed', 'Professional']}),
    ("More Notepads",     ['ΣΗΜΕΙΩΜΑΤΑΡΙΑ', 'ΤΕΤΡΑΔΙΑ', 'ΗΜΕΡΟΛΟΓΙΑ', 'ORGANISER'], {'title_boost': ['A4', 'A5', 'Professional', 'Hardcover', 'Spiral', 'Perforated', 'Αποσπώμενο']}),
    ("Eraser",            ['ΓΟΜΕΣ'],                                      {'eidos_boost': ['Γόμα'], 'title_boost': ['White', 'Soft', 'Λευκή']}),
]

STATIONERY_CLUSTER_SLOTS = {
    "Pens":               PENS_SLOTS,
    "Pencils":            PENCILS_SLOTS,
    "Markers":            MARKERS_SLOTS,
    "Sharpeners":         SHARPENERS_SLOTS,
    "Erasers":            ERASERS_SLOTS,
    "Correction":         CORRECTION_SLOTS,
    "Pencil Cases":       PENCIL_CASES_SLOTS,
    "Geometric Tools":    GEOMETRIC_TOOLS_SLOTS,
    "Stationery Sets":    STATIONERY_SETS_SLOTS,
    "Paints":             PAINTS_SLOTS,
    "Brushes":            BRUSHES_SLOTS,
    "Colored Pencils Art": COLORED_PENCILS_ART_SLOTS,
    "Drawing Markers":    DRAWING_MARKERS_SLOTS,
    "Art Paper":          ART_PAPER_SLOTS,
    "Notebooks":          NOTEBOOKS_SLOTS,
    "Notepads":           NOTEPADS_SLOTS,
}

# ── Printer sub-personas (Inkjet vs Laser) ──
PRINTER_INKJET_SLOTS = [
    ("Ink Cartridge 1",     ['INK CATRIDGES', 'COMPATIBLE INK CARTRIDGES'], {'ink_model_match': True, 'brand_match': True}),
    ("Ink Cartridge 2",     ['INK CATRIDGES', 'COMPATIBLE INK CARTRIDGES'], {'ink_model_match': True, 'brand_match': True}),
    ("Ink Cartridge 3",     ['INK CATRIDGES', 'COMPATIBLE INK CARTRIDGES'], {'ink_model_match': True, 'brand_match': True}),
    ("Ink Cartridge 4",     ['INK CATRIDGES', 'COMPATIBLE INK CARTRIDGES'], {'ink_model_match': True, 'brand_match': True}),
    ("A4 Paper",            ['INKJET PAPER', 'COPIERS PAPER'],{'paper_weight_max': 90}),
    ("Photo Paper",         ['SPECIAL PAPERS'],               {'paper_weight_min': 150, 'title_boost': ['Gloss', 'Matte', 'Photo']}),
    ("USB Printer Cable",   ['USB CABLES'],                   {'title_boost': ['USB-B', 'Printer', 'Type-B']}),
    ("Surge Protector",     ['LINE INTERACTIVE'],                          {}),
    ("Cleaning",            ['CLEANING PRODUCTS'],            {}),
    ("Cleaning 2",          ['CLEANING PRODUCTS'],            {}),
]

PRINTER_LASER_SLOTS = [
    ("Toner",               ['TONER CATRIDGES', 'COMPATIBLE TONERS'], {'toner_model_match': True, 'brand_match': True}),
    ("Drum Unit",           ['DRUMS CATRIDGES'],              {'brand_match': True}),
    ("A4 Paper",            ['LASER PAPERS', 'COPIERS PAPER'],{}),
    ("Network Cable",       ['NETWORK CABLES'],               {'title_boost': ['Cat6', 'Cat 6']}),
    ("Shredder",            ['ΚΑΤΑΣΤΡΟΦΕΙΣ ΕΓΓΡΑΦΩΝ'],        {}),
    ("UPS",                 ['ΜΠΑΤΑΡΙΕΣ UPS'],                          {'ups_min_va': 1000}),
    ("Laminator",           ['ΠΛΑΣΤΙΚΟΠΟΙΗΤΕΣ'],              {}),
    ("A3 Paper",            ['LASER PAPERS', 'COPIERS PAPER'],{'title_boost': ['A3']}),
    ("Cleaning",            ['CLEANING PRODUCTS'],            {}),
    ("Calculator",          ['CALCULATORS'],                  {}),
]

# ── Webcam ──
# Reorder: Microphone is the highest-value co-purchase for a webcam → slot 1.
# TRIPODS hierarchy removed from Webcam Mount — DSLR tripods aren't webcam clips.
# Lighting slots use title_include to avoid ceiling/bulb false-positives (Λάμπα, Λαμπτήρας).
WEBCAM_SLOTS = [
    ("Microphone",          ['PC MICROPHONES'],               {'brand_match': True, 'price_match_trigger': True, 'title_boost': ['USB', 'Condenser', 'Streaming', 'Podcast', 'Desktop', 'Επιτραπέζιο'], 'title_hide': ['Gaming RGB', 'Lavalier', 'Wireless lav']}),
    ("Overhead Headset",    ['OVERHEAD', 'PC HEADSET/MICROPHONE', 'BLUETOOTH'], {'brand_boost': True, 'color_match_all': True, 'title_boost': ['Overhead', 'Over-Ear', 'Noise Cancelling', 'Teams', 'Zoom', 'Conference'], 'title_hide': ['Earbuds', 'In-Ear', 'Neckband', 'Lavalier']}),
    ("Webcam Mount",        ['ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],               {'title_include': ['Webcam', 'Camera mount', 'Clip', 'Monitor Mount', 'Επιτραπέζι', 'Επιτοίχι', 'Clamp'], 'title_hide': ['Τρίποδο', 'Tripod', 'DSLR', 'Heavy Duty', 'CPU', 'Υπολογιστή', 'Riser', 'Drawer', 'Laptop', 'Notebook', 'Cooler', 'VESA']}),
    ("USB Extension",       ['USB CABLES'],                   {'title_boost': ['Extension', 'Extender', '3m', '5m'], 'title_hide': ['DisplayPort', 'Charging', 'HDMI']}),
    ("Lens Cleaner",        ['CLEANING PRODUCTS'],            {'title_include': ['Lens', 'Camera', 'Screen', 'Microfiber', 'Wipes', 'Optical', 'Σπρέι', 'Αέρας']}),
    ("Desk Lamp",           ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ', 'ΦΩΤΙΣΤΙΚΑ'], {'title_include': ['Desk', 'Γραφείου', 'Table', 'Επιτραπέζιο', 'Φωτιστικό', 'ScreenBar', 'Monitor Light'], 'title_hide': ['Ceiling', 'Bulb', 'Strip', 'Οροφής', 'Λάμπα', 'Λαμπτήρας', 'E27', 'E14', 'Ταινία', 'Λεντοταινία', 'Smart Bulb', 'Γιρλάντα', 'String Light', 'Outdoor', 'Εξωτερικ', 'Bedside', 'Κρεβατ']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'title_boost': ['Desk Mount', 'Clamp', 'USB-A', 'USB-C']}),
    ("Cable Organizer",     ['ACCESSORIES', 'USB CABLES'],    {'title_include': ['Cable', 'Organizer', 'Velcro', 'Clip', 'Οργάνωσης', 'Συγκράτησης']}),
    ("PC Speakers",         ['PC SPEAKERS 2.0', 'PC SPEAKERS 1'], {'brand_match': True, 'title_boost': ['Desktop', 'USB Powered', 'Compact', '2.0'], 'title_hide': ['Soundbar', '5.1', 'Subwoofer', 'Gaming RGB']}),
    ("Privacy Cover",       ['ACCESSORIES', 'CLEANING PRODUCTS'], {'title_include': ['Privacy', 'Cover', 'Shutter', 'Κάλυμμα', 'Κάλυμμα Κάμερας', 'Webcam cover', 'Privacy Shield']}),
]

# Gaming-webcam variant: Razer Kiyo, Logitech G StreamCam, etc.
# Differences from WEBCAM_SLOTS: gaming audio instead of office headset, streaming accessories emphasis.
WEBCAM_GAMING_SLOTS = [
    ("Microphone",          ['PC MICROPHONES'],               {'brand_match': True, 'price_match_trigger': True, 'title_boost': ['Streaming', 'USB', 'Condenser', 'Blue Yeti', 'Razer Seiren', 'HyperX QuadCast'], 'title_hide': ['Lavalier', 'Wireless lav']}),
    ("Gaming Headset",      ['GAMING AUDIO', 'OVERHEAD'],     {'brand_boost': True, 'color_match_all': True, 'title_boost': ['Gaming', 'Razer', 'Logitech G', 'HyperX', 'SteelSeries', 'Corsair', 'Astro'], 'title_hide': ['Earbuds', 'In-Ear', 'Lavalier']}),
    ("Webcam Mount",        ['ΒΑΣΕΙΣ ΓΡΑΦΕΙΟΥ'],               {'title_include': ['Webcam', 'Camera mount', 'Clip', 'Monitor Mount', 'Επιτραπέζι', 'Επιτοίχι', 'Clamp'], 'title_hide': ['Τρίποδο', 'Tripod', 'DSLR', 'Heavy Duty', 'CPU', 'Υπολογιστή', 'Riser', 'Drawer', 'Laptop', 'Notebook', 'Cooler', 'VESA']}),
    ("Streaming Accessories",['STREAMING ACCESSORIES'],       {'eidos_include': ['Capture Card', 'Gaming Αξεσουάρ', 'Green Screen', 'Mic Arm', 'Stream Controller', 'Stream Deck', 'Streaming Kit', 'Βραχίονας μικροφώνου', 'Ηχοαπορροφητικά Πάνελ', 'Κάρτα καταγραφής βίντεο']}),
    ("USB Extension",       ['USB CABLES'],                   {'title_boost': ['Extension', 'Extender', '3m', '5m'], 'title_hide': ['DisplayPort', 'Charging', 'HDMI']}),
    ("Lens Cleaner",        ['CLEANING PRODUCTS'],            {'title_include': ['Lens', 'Camera', 'Screen', 'Microfiber', 'Wipes', 'Optical', 'Σπρέι', 'Αέρας']}),
    ("Smart Lighting",      ['ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'],             {'title_boost': ['Strip', 'LED', 'Bias', 'Backlight', 'RGB', 'Ταινία', 'Λεντοταινία'], 'title_hide': ['Ceiling', 'Bulb', 'Λάμπα', 'Λαμπτήρας', 'E27', 'E14', 'Οροφής', 'Γιρλάντα', 'String Light', 'Outdoor', 'Bedside']}),
    ("USB Hub",             ['USB HUB DEVICES'],              {'title_boost': ['Desk Mount', 'Clamp', 'USB-A', 'USB-C']}),
    ("PC Speakers",         ['PC SPEAKERS 2.0', 'PC SPEAKERS 1'], {'brand_boost': True, 'title_boost': ['Gaming', 'RGB', 'Desktop', '2.0'], 'title_hide': ['Soundbar', '5.1', 'Subwoofer']}),
    ("Headset Stand",       ['GAMING HEADSET STANDS', 'PORTABLE ACCESSORIES'], {'title_boost': ['Stand', 'Hanger', 'Βάση Ακουστικών']}),
]

# ── USB Hub ──
USB_HUB_SLOTS = [
    ("USB Cable 1",         ['USB CABLES'],                   {'hub_cable_type': True}),
    ("USB Cable 2",         ['USB CABLES'],                   {'title_boost': ['USB-C to USB-A', 'Type-C to USB-A', 'USB-A to USB-C']}),
    ("USB Cable 3",         ['USB CABLES'],                   {}),
    ("Power Supply",        ['DESKTOP POWER SUPPLIERS'],      {'powered_hub_only': True}),
    ("Cable Organizer",     ['CLEANING PRODUCTS'],            {}),
    ("USB Flash Drive",     ['USB FLASH DISK'],               {'port_count_storage': True, 'usb_version_match': True}),
    ("External Storage",    ['EXTERNAL HDD USB', 'EXTERNAL SSD USB'], {'port_count_storage': True, 'usb_version_match': True}),
    ("Card Reader",         ['CARD READERS'],                 {'exclude_if_has_feature': 'SD'}),
    ("USB Gadget",          ['USB INPUT/OUTPUT DEVICES'],     {}),
    ("Cleaning/Case",       ['CLEANING PRODUCTS', 'NB ACCESSORIES'], {}),
]

# Map cluster key → slot list
PERIPHERAL_CLUSTER_SLOTS = {
    "Mouse":            MOUSE_SLOTS,
    "Keyboard":         KEYBOARD_SLOTS,
    "Gaming Mouse":     GAMING_MOUSE_SLOTS,
    "Gaming Keyboard":  GAMING_KEYBOARD_SLOTS,
    "Monitors":         None,  # Detected dynamically from Χρήση
    "Printers":         None,  # Detected dynamically from Hierarchy
    "Webcam":           WEBCAM_SLOTS,
    "USB Hub":          USB_HUB_SLOTS,
}

def get_peripheral_budget(anchor_price, category):
    """
    Returns (min_price, max_price) based on the anchor product price and category.
    Implements the custom segment logic and 0.5x to 2.5x guardrails.
    """
    # Budget Tier
    if anchor_price < 20:
        if category == 'KEYBOARD': return (15, 25)
        if category == 'MOUSE': return (10, 20)
        if category == 'HEADSET': return (15, 30)
        if category == 'MOUSEPAD': return (5, 10)
        return (5, anchor_price * 0.30) # 30% rule for general accessories
        
    # Sweet Spot Tier
    elif anchor_price < 80:
        if category == 'KEYBOARD': return (40, 70)
        if category == 'MOUSE': return (30, 60)
        if category == 'HEADSET': return (40, 80)
        if category == 'MOUSEPAD': return (15, 25)
        return (10, anchor_price * 0.30)
        
    # High-End Tier
    elif anchor_price < 150:
        if category == 'KEYBOARD': return (120, 180)
        if category == 'MOUSE': return (80, 130)
        if category == 'HEADSET': return (100, 150)
        if category == 'MOUSEPAD': return (30, 50)
        return (15, anchor_price * 0.30)
        
    # Ultra/Pro Tier (>= 150)
    else:
        if category == 'KEYBOARD': return (200, 350)
        if category == 'MOUSE': return (150, 300)
        if category == 'HEADSET': return (200, 400)
        if category == 'MOUSEPAD': return (50, 100)
        return (25, anchor_price * 0.50) # Loosened 30% rule for flagship buyers

# ── Stationery premium brands ──
STATIONERY_PREMIUM_BRANDS = {
    'LEGAMI', 'FABER-CASTELL', 'FABER CASTELL', 'MOLESKINE', 'MOSES',
    'STABILO', 'COOLBEE', 'MAPED', 'OOLY', 'POSCA', 'BAN.DO', 'BANDO',
}

def get_stationery_budget(anchor_price, role_lower):
    """
    Stationery pricing. Products are €0.50-€30.
    We don't scale accessories to trigger price — a €1 pen buyer
    still needs a €5 notebook. Instead, we set sensible bands per role.
    """
    if 'case' in role_lower or 'κασετίνα' in role_lower:
        return (3, 15)
    elif 'notebook' in role_lower or 'notepad' in role_lower:
        return (1, 8)
    elif 'easel' in role_lower or 'καβαλέτ' in role_lower:
        return (10, 40)
    elif 'canvas' in role_lower or 'καμβά' in role_lower:
        return (3, 15)
    elif 'brush' in role_lower and 'case' not in role_lower:
        return (2, 12)
    elif 'paint' in role_lower or 'χρώμα' in role_lower:
        return (2, 15)
    elif 'set' in role_lower or 'σετ' in role_lower:
        return (3, 20)
    else:
        return (0.5, 6)
def get_gaming_furniture_budget(trigger_price):
    """
    Logic for Gaming Chairs/Desks based on the price of the Mouse/Keyboard.
    Prevents suggesting 'SecretLab' tier chairs to 'Budget' mouse buyers.
    """
    if trigger_price < 40:
        # Entry peripherals -> Entry furniture
        return (80, 160)
    elif trigger_price < 90:
        # Mid-tier peripherals -> Mid furniture
        return (150, 280)
    else:
        # Pro/High-end peripherals -> Premium furniture
        return (250, 600)
        
def get_monitor_peripheral_budget(monitor_price, category):
    """
    Returns (min_price, max_price) for peripherals recommended alongside monitors.
    """
    # Budget monitor (<€100)
    if monitor_price < 100:
        if category == 'KEYBOARD': return (20, 50)
        if category == 'MOUSE': return (15, 40)
        if category == 'HEADSET': return (20, 50)
        if category == 'MOUSEPAD': return (5, 15)
        if category == 'CHAIR': return (80, 150)
        if category == 'DESK': return (50, 120)
        if category == 'WHEEL': return (50, 150)
        if category == 'UPS': return (40, 80)
        if category == 'WEBCAM': return (20, 45)
        if category == 'HUB': return (15, 30)
        if category == 'PRINTER': return (60, 120)
        if category == 'SPEAKERS': return (15, 40)
        return (5, 25)
    # Mid-range (€100-€250)
    elif monitor_price < 250:
        if category == 'KEYBOARD': return (40, 80)
        if category == 'MOUSE': return (30, 60)
        if category == 'HEADSET': return (40, 80)
        if category == 'MOUSEPAD': return (10, 25)
        if category == 'CHAIR': return (120, 250)
        if category == 'DESK': return (80, 180)
        if category == 'WHEEL': return (100, 300)
        if category == 'UPS': return (60, 120)
        if category == 'WEBCAM': return (40, 80)
        if category == 'HUB': return (25, 50)
        if category == 'PRINTER': return (100, 200)
        if category == 'SPEAKERS': return (30, 70)
        return (10, 40)
    # High-end (€250-€400)
    elif monitor_price < 400:
        if category == 'KEYBOARD': return (80, 150)
        if category == 'MOUSE': return (50, 100)
        if category == 'HEADSET': return (80, 150)
        if category == 'MOUSEPAD': return (20, 40)
        if category == 'CHAIR': return (150, 350)
        if category == 'DESK': return (120, 250)
        if category == 'WHEEL': return (200, 500)
        if category == 'UPS': return (80, 200)
        if category == 'WEBCAM': return (70, 150)
        if category == 'HUB': return (40, 100)
        if category == 'PRINTER': return (180, 400)
        if category == 'SPEAKERS': return (60, 150)
        return (15, 60)
    # Premium (€400+)
    else:
        if category == 'KEYBOARD': return (120, 250)
        if category == 'MOUSE': return (80, 150)
        if category == 'HEADSET': return (100, 200)
        if category == 'MOUSEPAD': return (30, 60)
        if category == 'CHAIR': return (200, 600)
        if category == 'DESK': return (150, 400)
        if category == 'WHEEL': return (300, 1000)
        if category == 'UPS': return (100, 300)
        return (25, 100)
        
def run_peripherals_engine(trigger, df_products, df_history, cluster_key):
    diag = []
    slot_notes = {}
    all_recs = []

    tm = trigger['Material']
    tt = str(trigger.get('Title', '')) # <--- ΠΡΟΣΘΕΣΕ ΑΥΤΟ
    _tt_lower = tt.lower()
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    thier = str(trigger.get('Hierarchy', '')).strip().upper()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))
    tcolor = str(trigger.get('Χρώμα Γραφής', trigger.get('Χρώμα', ''))).strip()

    # --- ΒΗΜΑ Α: THEME DETECTION (Universal για όλα τα Stationery) ---
    theme_keywords = ['frozen', 'spiderman', 'mickey', 'minnie', 'cars', 'disney', 'marvel', 'nba', 'santoro', 'barbie', 'hello kitty', 'princess', 'unicorn', 'λουλούδια', 'space']
    active_theme = next((w for w in theme_keywords if w in _tt_lower), None)

    # --- ΒΗΜΑ Β: SCHOOL LIST DETECTION (Μόνο για Τετράδια) ---
    trigger_grades = set()
    trigger_type = None
    if cluster_key in ["Notebooks", "Notepads"] or "ΤΕΤΡΑΔΙ" in _tt_lower.upper():
        for item_type, info in NOTEBOOK_CATALOG_LOGIC.items():
            if any(kw in _tt_lower for kw in info['keywords']):
                trigger_grades = info['grades']
                trigger_type = item_type
                break

    # Αν βρήκαμε ότι είναι σχολικό τετράδιο, αλλάζουμε τη δομή των slots δυναμικά
    if trigger_grades:
        diag.append(("School Mode", "Enabled", f"Trigger: {trigger_type} for Grades: {trigger_grades}"))
        # Slots: 5 slots για άλλα τετράδια της λίστας, 5 slots για συνοδευτικά
        slots = [
            ("Τετράδιο Λίστας 1", ['ΤΕΤΡΑΔΙΑ', 'ΣΗΜΕΙΩΜΑΤΑΡΙΑ'], {'school_list_mode': True}),
            ("Τετράδιο Λίστας 2", ['ΤΕΤΡΑΔΙΑ', 'ΣΗΜΕΙΩΜΑΤΑΡΙΑ'], {'school_list_mode': True}),
            ("Τετράδιο Λίστας 3", ['ΤΕΤΡΑΔΙΑ', 'ΣΗΜΕΙΩΜΑΤΑΡΙΑ'], {'school_list_mode': True}),
            ("Τετράδιο Λίστας 4", ['ΤΕΤΡΑΔΙΑ', 'ΣΗΜΕΙΩΜΑΤΑΡΙΑ'], {'school_list_mode': True}),
            ("Τετράδιο Λίστας 5", ['ΤΕΤΡΑΔΙΑ', 'ΣΗΜΕΙΩΜΑΤΑΡΙΑ'], {'school_list_mode': True}),
            ("Κασετίνα", ['ΣΧΟΛΙΚΕΣ ΚΑΣΕΤΙΝΕΣ', 'ΚΑΣΕΤΙΝΕΣ-ΘΗΚΕΣ'], {'brand_match': True}),
            ("Μολύβια", ['ΜΟΛΥΒΙΑ'], {'brand_match': True}),
            ("Στυλό", ['ΣΤΥΛΟ ΥΓΡΗΣ ΜΕΛΑΝΗΣ', 'ΣΤΥΛΟ GEL'], {'brand_match': True}),
            ("Γόμα/Ξύστρα", ['ΓΟΜΕΣ', 'ΞΥΣΤΡΕΣ'], {}),
            ("Μαρκαδόροι", ['ΜΑΡΚΑΔΟΡΟΙ'], {}),
        ]
    else:
        # Standard slots από το config
        slots = PERIPHERAL_CLUSTER_SLOTS.get(cluster_key, [])

    # Connectivity
    is_wireless = 'WIRELESS' in thier or 'ΑΣΥΡΜΑΤ' in tt.upper()
    # Wired detection: hierarchy OR connection-tech attribute OR title keywords
    # Many gaming mice/kbs have hierarchy 'GAMING MOUSE' (no WIRED token) but are actually wired
    _tconn = str(trigger.get('Τεχνολογία σύνδεσης', '')).lower()
    is_wired = (
        ('WIRED' in thier and not is_wireless)
        or ('ενσύρματ' in _tconn and not is_wireless)
        or ('wired' in _tconn and not is_wireless)
        or ('ενσύρματ' in tt.lower() and not is_wireless)
    )
    is_apple = tb == 'APPLE' or 'APPLE' in thier

    # Features
    _tt_lower = tt.lower()
    is_silent = str(trigger.get('Αθόρυβο', '')).lower() in ('ναι', 'yes', 'true') or 'silent' in _tt_lower
    is_ergo = str(trigger.get('Εργονομικό', '')).lower() in ('ναι', 'yes', 'true')
    has_rgb = 'rgb' in str(trigger.get('Πρόσθετα χαρακτηριστικά', '')).lower() or 'rgb' in _tt_lower
    no_battery = is_wired or is_apple

    # ── Kid/whimsical theme detection ──
    KID_THEME_RE = r'kitty|kawaii|\bmeow\b|πεταλούδα|ladybug|παγωτό|γκλίτερ|glitter|unicorn|μονόκερος|teddy|\bkids\b|παιδικ|princess|πριγκίπισσα|disney|sparkle|σπάρκλ|rainbow|donut|cupcake|kawai|cute pet|μικροί ζωγράφο|fairy|νεράιδ|pixel|\bmaxi\b|\bjumbo\b'
    trigger_is_kid_theme = bool(re.search(KID_THEME_RE, _tt_lower))
    _kid_brand_set = {'GIOTTO', 'CARIOCA', 'CRAYOLA', 'FIBRAPEN', 'MILAN'}
    if not trigger_is_kid_theme and tb in _kid_brand_set:
        trigger_is_kid_theme = True

    # Gaming mouse deep attributes
    dpi_str = str(trigger.get('Ανάλυση κίνησης', ''))
    button_count = 0
    try:
        button_count = int(trigger.get('Αριθμός κουμπιών', 0))
    except: pass
    sensor_type = str(trigger.get('Τύπος Αισθητήρα', '')).lower()

    # Monitor attributes
    tusage = str(trigger.get('Χρήση', trigger.get('Προτεινόμενη χρήση', ''))).lower()
    tports = str(trigger.get('Θύρες', trigger.get('Βύσμα(τα)', ''))).lower()
    tvesa = str(trigger.get('Πρότυπο VESA', trigger.get('Συμβατότητα VESA', ''))).strip()
    tinches = parse_screen_size(trigger.get('Ιντσες', trigger.get('Μέγεθος οθόνης', '')))
    tres = str(trigger.get('Ανάλυση Οθόνης', '')).lower()

    # Dedicated port columns (new — takes priority over old Θύρες)
    _port_na = {'', 'nan', 'n/a', '0', '-', 'none'}
    t_hdmi_raw = str(trigger.get('HDMI', '')).strip()
    t_dp_raw   = str(trigger.get('Display Port', '')).strip()
    t_usb_raw  = str(trigger.get('USB', '')).strip()
    has_hdmi = t_hdmi_raw.lower() not in _port_na
    has_dp   = t_dp_raw.lower() not in _port_na
    has_usb  = t_usb_raw.lower() not in _port_na
    # Fallback: if dedicated columns are all empty, parse old Θύρες
    if not has_hdmi and not has_dp and not has_usb and tports:
        has_hdmi = 'hdmi' in tports
        has_dp   = 'displayport' in tports or 'display port' in tports or 'dp ' in tports
        has_usb  = 'usb-c' in tports or 'type-c' in tports or 'usb c' in tports

    # Printer attributes
    tink = str(trigger.get('Αναλώσιμο υλικό', '')).strip()
    ttech = str(trigger.get('Τεχνολογία', '')).lower()
    is_laser = 'laser' in thier.lower() or 'laser' in ttech

    # Hub attributes
    hub_input = str(trigger.get('Συμβατή συσκευή', '')).lower()
    hub_ports_str = str(trigger.get('Αριθμός Θυρών', trigger.get('Αριθμός θυρών8', '')))
    hub_expansion = str(trigger.get('Θύρες επέκτασης', '')).lower()
    hub_power = str(trigger.get('Τροφοδοσία', trigger.get('Τροφοδοσία15', ''))).lower()
    hub_interface = str(trigger.get('Interface', '')).lower()
    do_color_match = tcolor and tcolor.lower() not in ('', 'nan', 'n/a', '0')
    
    
    # ── Determine slot config ──
    monitor_persona = None  # Used by usage_filter flag
    if cluster_key == "Monitors":
        # Primary: Χρήση column
        is_gaming_monitor = 'gaming' in tusage
        is_pro_monitor = 'business' in tusage or 'professional' in tusage or 'επαγγελματικ' in tusage
        
        # Fallback: if Χρήση is empty, detect from hardware signals
        if not is_gaming_monitor and not is_pro_monitor and tusage in ('', 'nan', 'n/a'):
            textra = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
            textra2 = str(trigger.get('Πρόσθετα χαρακτηριστικά', '')).lower()
            all_signals = f"{textra} {textra2} {_tt_lower} {thier.lower()}"
            gaming_keywords = ['gaming', 'freesync', 'g-sync', 'gsync', 'adaptive sync',
                               '144hz', '165hz', '240hz', '360hz', '500hz']
            is_gaming_monitor = any(kw in all_signals for kw in gaming_keywords)
            
            # Hardware fallback: DisplayPort → strong gaming signal
            if not is_gaming_monitor and has_dp:
                is_gaming_monitor = True
                diag.append(("0a. Gaming Fallback", "✅", "Has DisplayPort → Gaming"))
            elif is_gaming_monitor:
                diag.append(("0a. Gaming Fallback", "✅", "Detected from Extra/Πρόσθετα/Title/Hierarchy"))
        
        if is_gaming_monitor:
            slots = MONITOR_GAMING_SLOTS
            persona = "Gaming"
        elif is_pro_monitor:
            slots = MONITOR_PRO_SLOTS
            persona = "Professional"
        else:
            slots = MONITOR_MAINSTREAM_SLOTS
            persona = "Mainstream"
        monitor_persona = persona
        diag.append(("0. Monitor Persona", persona, f"Usage='{tusage}'"))
        port_info = f"HDMI={'✅'+t_hdmi_raw if has_hdmi else '❌'}, DP={'✅'+t_dp_raw if has_dp else '❌'}, USB={'✅'+t_usb_raw if has_usb else '❌'}"
        diag.append(("0b. Monitor Ports", port_info, f"Res={tres}"))
    elif cluster_key == "Printers":
        if is_laser:
            slots = PRINTER_LASER_SLOTS
            persona = "Laser"
        else:
            slots = PRINTER_INKJET_SLOTS
            persona = "Inkjet"
        diag.append(("0. Printer Persona", persona, f"Hierarchy='{thier}'"))
    elif cluster_key == "Webcam":
        # Webcam sub-cluster: gaming brands → gaming-variant slot list (gaming audio, streaming, RGB).
        _gaming_webcam_brands = {'RAZER', 'LOGITECH G', 'CORSAIR', 'HYPERX', 'ASUS ROG', 'ROCCAT', 'ELGATO'}
        _webcam_title_lower = tt.lower()
        is_gaming_webcam = (
            tb in _gaming_webcam_brands
            or 'gaming' in _webcam_title_lower
            or 'streamcam' in _webcam_title_lower
            or 'kiyo' in _webcam_title_lower  # Razer Kiyo
        )
        if is_gaming_webcam:
            slots = WEBCAM_GAMING_SLOTS
            diag.append(("0. Webcam Persona", "Gaming", f"Brand={tb}, Title='{tt[:50]}'"))
        else:
            slots = WEBCAM_SLOTS
            diag.append(("0. Webcam Persona", "Standard", f"Brand={tb}"))
    else:
        slots = PERIPHERAL_CLUSTER_SLOTS.get(cluster_key, [])

    diag.append(("0. Trigger", f"Brand={tb}, €{tprice:.0f}",
                 f"Cluster={cluster_key}, Wireless={is_wireless}, Apple={is_apple}"))
    
    # ── Build candidate pool ──
    c = df_products[df_products['Material'] != tm].copy()

    # =====================================================================
    # 🚫 HARD FILTER: Exclude smart bulbs! Require 'Είδος' == 'Φωτιστικά'
    # =====================================================================
    if 'Είδος' in c.columns:
        is_smart_lighting = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip() == 'ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ'
        is_fotistika = c['Είδος'].fillna('').astype(str).str.upper().str.contains('ΦΩΤΙΣΤΙΚ', na=False)
        b4_bulbs = len(c)
        # Drop rows that are in 'ΕΞΥΠΝΟΣ ΦΩΤΙΣΜΟΣ' but are NOT 'Φωτιστικά'
        c = c[~(is_smart_lighting & ~is_fotistika)]
        if b4_bulbs > len(c):
            diag.append(("1a. No Bulbs Filter", len(c), f"Removed {b4_bulbs - len(c)} items (Kept only Φωτιστικά)"))
    # =====================================================================

    if 'CW Stock Units' in c.columns:
        stv = pd.to_numeric(c['CW Stock Units'], errors='coerce').fillna(0)
        pct = (stv > 0).sum() / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c = c[stv > 0]
            diag.append(("1b. Stock", len(c), f"({pct:.0%})"))

    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0

    # Apple ban for non-Apple
    if not is_apple and cluster_key in ("Mouse", "Keyboard", "Gaming Mouse", "Gaming Keyboard"):
        b4 = len(c)
        c = c[c['Κατασκευαστής'].fillna('').astype(str).str.strip().str.upper() != 'APPLE']
        if b4 > len(c):
            diag.append(("1c. Apple ban", len(c), f"-{b4 - len(c)}"))
            
    used_materials = {tm}
    
    # --- NEW: CO-PURCHASE HISTORY LOGIC ---
    tcust = df_history[df_history['Material']==tm]['customerEmail'].unique() if not df_history.empty else []
    bw = df_history[(df_history['customerEmail'].isin(tcust))&(df_history['Material']!=tm)] if not df_history.empty else pd.DataFrame()
    fdf = bw['Material'].value_counts().reset_index() if not bw.empty else pd.DataFrame(columns=['NID', 'Frequency'])
    
    if not fdf.empty:
        fdf.columns = ['NID', 'Frequency']
        c = c.merge(fdf, left_on='Material', right_on='NID', how='left')
        c['Frequency'] = c['Frequency'].fillna(0).astype(int)
        c['History_Score'] = c['Frequency'].apply(lambda f: HISTORY_BOOST if f >= HISTORY_FREQ_MIN else 0)
    else:
        c['Frequency'] = 0
        c['History_Score'] = 0
# --------------------------------------

    for idx, (role, hierarchies, flags) in enumerate(slots, start=1):
        notes = [f"Slot {idx}: {role}"]
        
        # ── 1. SKIP CONDITIONS (ΔΙΑΤΗΡΗΣΗ ΛΕΙΤΟΥΡΓΙΚΟΤΗΤΑΣ) ──
        # Μπαταρίες αν το trigger είναι Wired
        if flags.get('skip_if_wired') and is_wired:
            diag.append((f"Slot {idx} ({role})", 0, "Skipped (Wired trigger)"))
            continue

        # Hub αν το trigger είναι Wireless
        if flags.get('skip_if_wireless') and is_wireless:
            diag.append((f"Slot {idx} ({role})", 0, "Skipped (Wireless trigger)"))
            continue
            
        # No-battery skip
        skip = flags.get('skip_if', '')
        if skip == 'no_battery' and no_battery:
            fb = flags.get('fallback_hier')
            if fb:
                hierarchies = fb
                notes.append(f"↩ No-battery fallback")
            else:
                diag.append((f"Slot {idx} ({role})", 0, "Skipped (No battery)"))
                continue

        # Powered hub check
        if flags.get('powered_hub_only'):
            if 'εξωτερική' not in hub_power and 'external' not in hub_power:
                diag.append((f"Slot {idx} ({role})", 0, "Skipped (bus-powered)"))
                continue

        # Feature exclusion (π.χ. SD slot)
        excl_feat = flags.get('exclude_if_has_feature', '')
        if excl_feat and excl_feat.lower() in hub_expansion:
            diag.append((f"Slot {idx} ({role})", 0, f"Skipped (has {excl_feat})"))
            continue

        # Apple walled garden
        if is_apple and 'apple_force' in flags:
            hierarchies = [flags['apple_force']]

        # ── 2. BUILD POOL (ΠΡΕΠΕΙ ΝΑ ΓΙΝΕΙ ΕΔΩ - ΠΡΙΝ ΤΑ SCORES) ──
        hier_upper = [h.upper().strip() for h in hierarchies]
        pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(hier_upper)].copy()
        
        if pool.empty:
            hier_col = c['Hierarchy'].fillna('').astype(str).str.upper().str.strip()
            mask = pd.Series(False, index=c.index)
            for hk in hier_upper:
                if hk: mask |= hier_col.str.contains(re.escape(hk), regex=True, na=False)
            pool = c[mask].copy()

        pool = pool[~pool['Material'].isin(used_materials)]

        if pool.empty:
            diag.append((f"Slot {idx} ({role})", 0, "Empty"))
            continue

        # ── 3. INITIAL SCORING ──
        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
        pool['Final_Score'] += pool['Sales_Tiebreaker'].fillna(0) * 0.1
        if 'History_Score' in pool.columns:
            pool['Final_Score'] += pool['History_Score']

        # ── 4. THEMED BOOST (FROZEN / SPIDERMAN κτλ) ──
        if active_theme and cluster_key in STATIONERY_CLUSTERS:
            theme_mask = pool['Title'].fillna('').str.lower().str.contains(active_theme)
            if theme_mask.any():
                pool.loc[theme_mask, 'Final_Score'] += 1500000 
                notes.append(f"✨ Theme Match ({active_theme}): Forced to top")

        # ── 5. SCHOOL LIST LOGIC (NOTEBOOKS) ──
        if flags.get('school_list_mode') and trigger_grades:
            for item_type, info in NOTEBOOK_CATALOG_LOGIC.items():
                if item_type == trigger_type: continue
                item_mask = pd.Series(False, index=pool.index)
                for kw in info['keywords']:
                    item_mask |= pool['Title'].fillna('').str.lower().str.contains(kw)
                if not item_mask.any(): continue
                if info['grades'].intersection(trigger_grades):
                    pool.loc[item_mask, 'Final_Score'] += (800000 + (info['rank'] * 50000))
                else:
                    pool.loc[item_mask, 'Final_Score'] -= 500000

        # ── 6. PRICING & TIER LOGIC (Η ΥΠΑΡΧΟΥΣΑ ΛΟΓΙΚΗ ΣΟΥ) ──
        if 'LIST PRICE' in pool.columns and tprice > 0:
            pool['_p'] = pool['LIST PRICE'].apply(parse_euro_price)

            if flags.get('price_limit_furniture'):
                min_p, max_p = get_gaming_furniture_budget(tprice)
                in_band = (pool['_p'] >= min_p) & (pool['_p'] <= max_p)
                pool.loc[in_band, 'Final_Score'] += 200000
                pool.loc[pool['_p'] > (max_p * 1.5), 'Final_Score'] -= 300000
                notes.append(f"Furniture Tier: €{min_p}-{max_p}")
                            
            # Identify the category for the current slot
            r_lower = role.lower()
            if cluster_key in STATIONERY_CLUSTERS:
                cat_key = 'STATIONERY'
            elif 'keyboard' in r_lower: cat_key = 'KEYBOARD'
            elif 'mouse' in r_lower and 'pad' not in r_lower: cat_key = 'MOUSE'
            elif 'headset' in r_lower or 'headphones' in r_lower: cat_key = 'HEADSET'
            elif 'pad' in r_lower or 'mat' in r_lower: cat_key = 'MOUSEPAD'
            elif 'chair' in r_lower: cat_key = 'CHAIR'
            elif 'wheel' in r_lower: cat_key = 'WHEEL'
            elif 'desk' in r_lower: cat_key = 'DESK'
            elif 'ups' in r_lower: cat_key = 'UPS'
            # --- NEW CATEGORIES ---
            elif 'webcam' in r_lower: cat_key = 'WEBCAM'
            elif 'hub' in r_lower: cat_key = 'HUB'
            elif 'stick' in r_lower or 'flash' in r_lower: cat_key = 'STORAGE'
            elif 'cleaner' in r_lower: cat_key = 'CLEANER'
            elif 'printer' in r_lower: cat_key = 'PRINTER'
            elif 'speakers' in r_lower: cat_key = 'SPEAKERS'
            else: cat_key = 'ACCESSORY'

            # Use cluster-specific pricing
            if cluster_key == "Monitors":
                min_p, max_p = get_monitor_peripheral_budget(tprice, cat_key)
            elif cluster_key in STATIONERY_CLUSTERS:
                min_p, max_p = get_stationery_budget(tprice, r_lower)
            else:
                min_p, max_p = get_peripheral_budget(tprice, cat_key)

            # price_match_trigger: override budget to ±50% of trigger price.
            # Used for co-purchase slots where the accessory should sit in the same
            # quality/price tier as the trigger (e.g. pricey webcam → pricey microphone).
            if flags.get('price_match_trigger') and tprice > 0:
                min_p = tprice * 0.5
                max_p = tprice * 1.6
                notes.append(f"Price-match-trigger override: €{min_p:.0f}-€{max_p:.0f} (trigger €{tprice:.0f})")
            
            # Find items in the sweet spot band
            in_band = (pool['_p'] >= min_p) & (pool['_p'] <= max_p)
            pool.loc[in_band, 'Final_Score'] += 150000
            
            # Apply penalties for breaking the tier bounds
            overbuy = pool['_p'] > max_p
            underbuy = pool['_p'] < min_p
            
            if cluster_key in STATIONERY_CLUSTERS:
                # Soft penalties for stationery — these are cheap items
                pool.loc[overbuy, 'Final_Score'] -= 60000
                pool.loc[underbuy, 'Final_Score'] -= 20000
            else:
                # Heavy penalty for upselling too aggressively
                pool.loc[overbuy, 'Final_Score'] -= 200000
                # Moderate penalty for showing cheap gear to premium buyers
                pool.loc[underbuy, 'Final_Score'] -= 80000 
            
            notes.append(f"Pricing [{cat_key}]: Target €{min_p:.0f}-€{max_p:.0f} (Anchor: €{tprice:.0f}). In band: {in_band.sum()}")

        # ── Universal Brand Boost & Color Match ──
        
        # 1. Brand Tiebreaker (+30k) & Flag Boost (+80k)
        if tb:
            target_brands = pool['Κατασκευαστής'].fillna('').str.strip().str.upper()
            
            if tb in ['LOGITECH', 'LOGITECH G']:
                is_same_brand = target_brands.isin(['LOGITECH', 'LOGITECH G'])
            else:
                is_same_brand = target_brands == tb
                
            pool.loc[is_same_brand, 'Final_Score'] += 30000
            
            # --- NEW: Dynamic Brand Loyalty for Stationery ---
            # Guarantees the same brand wins over generic premium brands
            if cluster_key in STATIONERY_CLUSTERS:
                pool.loc[is_same_brand, 'Final_Score'] += 100000
                if is_same_brand.any():
                    notes.append(f"Stationery Brand Match ({tb}): +100k points to {is_same_brand.sum()} items")
            # -----------------------------------------------
            
            # Reduced from 250k to 80k to let high sales win if the lead is significant
            if flags.get('brand_match'):
                pool.loc[is_same_brand, 'Final_Score'] += 80000
                if is_same_brand.any():
                    notes.append(f"Brand Match ({tb}): +80k points to {is_same_brand.sum()} items")

            # brand_boost: softer version — same-brand is preferred but not enforced.
            # Use this for slots where cross-brand is acceptable (e.g. Headset slot on Mouse cluster).
            if flags.get('brand_boost'):
                pool.loc[is_same_brand, 'Final_Score'] += 40000
                if is_same_brand.any():
                    notes.append(f"Brand Boost ({tb}): +40k to {is_same_brand.sum()} items (soft)")

        # color_match_all: boost candidates whose Χρώμα matches the trigger color,
        # regardless of slot role (overrides the default "keyboard/pad/mat only" filter).
        # Used for slots like Headset where color coordination matters (pink mouse → pink headphones).
        if flags.get('color_match_all') and do_color_match and 'Χρώμα' in pool.columns and tcolor:
            target_colors = pool['Χρώμα'].fillna('').astype(str).str.strip().str.upper()
            trigger_color_upper = tcolor.upper()
            synonyms = [trigger_color_upper]
            if trigger_color_upper in ['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'GREY', 'GRAY', 'ΓΚΡΙ']:
                synonyms.extend(['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'ΓΚΡΙ', 'GREY', 'GRAY'])
            elif trigger_color_upper in ['BLACK', 'ΜΑΥΡΟ']:
                synonyms.extend(['BLACK', 'ΜΑΥΡΟ'])
            elif trigger_color_upper in ['WHITE', 'ΛΕΥΚΟ']:
                synonyms.extend(['WHITE', 'ΛΕΥΚΟ'])
            elif trigger_color_upper in ['PINK', 'ΡΟΖ']:
                synonyms.extend(['PINK', 'ΡΟΖ'])
            elif trigger_color_upper in ['BLUE', 'ΜΠΛΕ']:
                synonyms.extend(['BLUE', 'ΜΠΛΕ', 'INDIGO'])
            elif trigger_color_upper in ['RED', 'ΚΟΚΚΙΝΟ']:
                synonyms.extend(['RED', 'ΚΟΚΚΙΝΟ'])
            # Match by attribute OR title
            attr_match = target_colors.isin(synonyms)
            title_match = pool['Title'].fillna('').str.upper().str.contains('|'.join(synonyms), regex=True, na=False)
            color_hit = attr_match | title_match
            if color_hit.any():
                pool.loc[color_hit, 'Final_Score'] += 120000
                notes.append(f"🎨 Color match-all ({tcolor}): +120k to {color_hit.sum()} items")

        # 2. Color Tiebreaker (+200k) - Eligible for Keyboards and Mousepads/Mats
        r_lower = role.lower()
        is_color_eligible = 'keyboard' in r_lower or 'pad' in r_lower or 'mat' in r_lower or 'rest' in r_lower
        
        if do_color_match and is_color_eligible and 'Χρώμα' in pool.columns:
            target_colors = pool['Χρώμα'].fillna('').astype(str).str.strip().str.upper()
            trigger_color_upper = tcolor.upper()
            
            color_synonyms = [trigger_color_upper]
            if trigger_color_upper in ['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'GREY', 'GRAY', 'ΓΚΡΙ']:
                color_synonyms.extend(['GRAPHITE', 'ΓΡΑΦΙΤΗΣ', 'ΓΚΡΙ', 'GREY', 'GRAY'])
            elif trigger_color_upper in ['BLACK', 'ΜΑΥΡΟ']:
                color_synonyms.extend(['BLACK', 'ΜΑΥΡΟ'])
            elif trigger_color_upper in ['WHITE', 'ΛΕΥΚΟ', 'ΑΣΠΡΟ', 'PALE GREY']:
                color_synonyms.extend(['WHITE', 'ΛΕΥΚΟ', 'ΑΣΠΡΟ', 'PALE GREY'])
            elif trigger_color_upper in ['ROSE', 'ΡΟΖ', 'PINK']:
                color_synonyms.extend(['ROSE', 'ΡΟΖ', 'PINK'])
                
            is_same_color = target_colors.apply(lambda x: any(syn in x or x in syn for syn in color_synonyms if syn))
            
            # Massive buff: Color overrides price bands!
            pool.loc[is_same_color, 'Final_Score'] += 200000
            
            if is_same_color.any():
                notes.append(f"Color Match ({tcolor}): Boosted {is_same_color.sum()} Keyboards/Pads (+200k)")

        # =====================================================================
        # 📚 ΑΥΣΤΗΡΗ ΛΟΓΙΚΗ ΣΧΟΛΙΚΩΝ ΛΙΣΤΩΝ (STATIONERY)
        # =====================================================================
        if cluster_key in STATIONERY_CLUSTERS:
            _tt_lower = str(trigger.get('Title', '')).lower()
            
            # --- ΒΗΜΑ 1: Character / Theme Match (π.χ. Frozen) ---
            # Υψηλότερη προτεραιότητα από όλα
            theme_keywords = ['frozen', 'spiderman', 'mickey', 'minnie', 'cars', 'disney', 'marvel', 'nba', 'santoro', 'barbie', 'hello kitty']
            active_theme = next((w for w in theme_keywords if w in _tt_lower), None)

            if active_theme:
                theme_mask = pool['Title'].fillna('').str.lower().str.contains(active_theme)
                pool.loc[theme_mask, 'Final_Score'] += 1000000 # Massive boost για theme match
                notes.append(f"✨ Theme Set ({active_theme}): Forced to top")

            # --- ΒΗΜΑ 2: Notebook Grade Logic ---
            # Εντοπισμός σε ποιες τάξεις ανήκει το trigger προϊόν
            trigger_grades = set()
            for item_type, info in NOTEBOOK_CATALOG_LOGIC.items():
                if any(kw in _tt_lower for kw in info['keywords']):
                    trigger_grades = info['grades']
                    notes.append(f"🔍 Trigger recognized as: {item_type} (Valid for: {trigger_grades})")
                    break

            if trigger_grades:
                # Εφαρμογή φίλτρου τάξης σε όλο το pool
                for item_type, info in NOTEBOOK_CATALOG_LOGIC.items():
                    # Φτιάχνουμε μάσκα για το συγκεκριμένο είδος τετραδίου στο pool
                    item_mask = pd.Series(False, index=pool.index)
                    for kw in info['keywords']:
                        item_mask |= pool['Title'].fillna('').str.lower().str.contains(kw)
                    
                    if not item_mask.any():
                        continue

                    # ΕΛΕΓΧΟΣ: Υπάρχει κοινή τάξη μεταξύ trigger και υποψήφιου;
                    common_grades = info['grades'].intersection(trigger_grades)
                    
                    if common_grades:
                        # Αν υπάρχει κοινή τάξη, δώσε boost βάσει του Rank (συχνότητα εμφάνισης)
                        # Προσθέτουμε +500k για να σιγουρέψουμε ότι θα βγουν πάνω από άσχετα είδη
                        boost_val = 500000 + (info['rank'] * 20000)
                        pool.loc[item_mask, 'Final_Score'] += boost_val
                        # notes.append(f"✅ {item_type}: Boosted via list overlap")
                    else:
                        # ΑΥΣΤΗΡΟΣ ΑΠΟΚΛΕΙΣΜΟΣ: Αν δεν υπάρχει ΚΑΜΙΑ κοινή τάξη
                        # (π.χ. βλέπει τετράδιο Α' Δημοτικού, κρύβουμε της ΣΤ')
                        pool.loc[item_mask, 'Final_Score'] -= 800000
                        # notes.append(f"🚫 {item_type}: Penalized (No grade overlap)")
            
            # --- ΒΗΜΑ 3: Backfill / Global Frequency ---
            # Αν κάποια τετράδια δεν έχουν βαθμολογηθεί ακόμα, δώσε boost βάσει rank 
            # για να γεμίσουν τα κενά slots με τα πιο "απαραίτητα" τετράδια γενικά.
            for item_type, info in NOTEBOOK_CATALOG_LOGIC.items():
                item_mask = pd.Series(False, index=pool.index)
                for kw in info['keywords']:
                    item_mask |= pool['Title'].fillna('').str.lower().str.contains(kw)
                pool.loc[item_mask, 'Final_Score'] += (info['rank'] * 5000)

        # =====================================================================
                
        # 3. Sub-Series / Ecosystem Match (e.g., Logitech MX)
        # Pad the title with spaces to ensure we match the isolated word "mx"
        if ' mx ' in f" {_tt_lower} ":
            is_mx = pool['Title'].fillna('').str.lower().str.contains(r'\bmx\b', regex=True, na=False)
            
            # Massive boost to force the MX product to the top of its slot
            pool.loc[is_mx, 'Final_Score'] += 100000 
            
            if is_mx.any():
                notes.append(f"Sub-series Match (MX): Boosted {is_mx.sum()} items (+100k)")
         # ── Exact Eidos Match (Ταυτοποίηση βάσει 'Είδος') ──
        if flags.get('match_eidos'):
            t_eidos = str(trigger.get('Είδος', '')).strip().lower()
            
            if t_eidos and t_eidos not in ['nan', 'n/a', 'none', '0', '']:
                p_eidos = pool['Είδος'].fillna('').astype(str).str.strip().str.lower()
                is_same_eidos = p_eidos == t_eidos
                
                b4_eidos = len(pool)
                pool = pool[is_same_eidos]
                notes.append(f"Eidos Match ({t_eidos}): {b4_eidos} → {len(pool)}")
            else:
                notes.append("⚠ Missing 'Είδος' on trigger. Skipping slot.")
                pool = pool.head(0)  # Αν δεν ξέρουμε το είδος, αδειάζουμε το pool για να μην φέρουμε άσχετα
                
        # ── Connectivity mirror ──
        if flags.get('connectivity_mirror'):
            pool_hier = pool['Hierarchy'].fillna('').str.upper()
            if is_wireless:
                w_mask = pool_hier.str.contains('WIRELESS')
                pool, note = filter_or_penalize(pool, w_mask, "Connectivity: wireless")
                notes.append(note)
            elif is_wired:
                w_mask = pool_hier.str.contains('WIRED') | (~pool_hier.str.contains('WIRELESS'))
                pool, note = filter_or_penalize(pool, w_mask, "Connectivity: wired")
                notes.append(note)

        # ── Brand match ──
        if flags.get('brand_match') and tb:
            same = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
            pool.loc[same, 'Final_Score'] += 80000
            if same.any(): notes.append(f"Brand ({tb}): {same.sum()}")

        # ── Apple filter ──
        if is_apple and 'apple_force' in flags:
            am = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == 'APPLE'
            if am.any():
                pool = pool[am]
                notes.append(f"🍎 Apple-only: {len(pool)}")

        # ── Title boost/hide ──
        if flags.get('title_boost'):
            pat = '|'.join(flags['title_boost'])
            m = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            pool.loc[m, 'Final_Score'] += 60000

        if flags.get('title_hide'):
            pat = '|'.join(flags['title_hide'])
            m = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            pool.loc[m, 'Final_Score'] -= 100000

        # ── Kid/whimsical theme penalty ──
        # For adult/professional triggers, heavily penalize Kawaii-Meow-Glitter-Unicorn candidates
        # so a Pilot ballpoint doesn't recommend a "Μπλοκ Σημειώσεων Παγωτό Γκλίτερ" notebook.
        # EXCEPTION: if candidate brand matches the trigger brand, keep it (same-brand siblings are
        # often legitimate, e.g. Legami-trigger → Legami-Kawaii is expected).
        # Slots can also override globally by setting flags['allow_kids_theme']=True.
        if not trigger_is_kid_theme and not flags.get('allow_kids_theme') and not cluster_key.startswith("Kids"):
            kid_mask = pool['Title'].fillna('').str.lower().str.contains(KID_THEME_RE, regex=True, na=False)
            if kid_mask.any():
                # Don't penalize same-brand candidates
                if tb and 'Κατασκευαστής' in pool.columns:
                    same_brand_mask = pool['Κατασκευαστής'].fillna('').astype(str).str.strip().str.upper() == tb
                    penalize_mask = kid_mask & ~same_brand_mask
                else:
                    penalize_mask = kid_mask
                if penalize_mask.any():
                    pool.loc[penalize_mask, 'Final_Score'] -= 150000
                    notes.append(f"Kids-theme penalty: -150k to {penalize_mask.sum()} items")

        # ── Title include (hard filter — used for slots where boost isn't enough) ──
        if flags.get('title_include'):
            pat = '|'.join(flags['title_include'])
            m = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            if m.any():
                b4 = len(pool)
                pool = pool[m]
                notes.append(f"Title include ({pat}): {b4} → {len(pool)}")
            else:
                notes.append(f"⚠ Title include ({pat}) would empty pool, slot will be empty")
                pool = pool.head(0)

        # ── Pen Variant Match (Same Brand, Same Variant, Different Color) ──
        if flags.get('match_pen_variant'):
            if tb and do_color_match:
                target_brands = pool['Κατασκευαστής'].fillna('').str.strip().str.upper()
                
                na_vals = ['nan', 'n/a', 'none', '0', '#n/a', 'μη διαθέσιμη πληροφορία', 'null', '']
                mm_regex = r'(\d+(?:[\.,]\d+)?(?:-\d+(?:[\.,]\d+)?)?\s*mm)'
                
                t_tip_raw = str(trigger.get('Πάχος Μύτης', '')).strip().lower()
                t_nib_raw = str(trigger.get('Τύπος Μύτης', '')).strip().lower()
                t_mm, t_text = '', ''
                
                for source in [t_tip_raw, t_nib_raw, _tt_lower]:
                    if source not in na_vals:
                        match = re.search(mm_regex, source)
                        if match:
                            t_mm = match.group(1).replace(' ', '').replace(',', '.')
                            break
                if not t_mm:
                    for source in [t_nib_raw, t_tip_raw]:
                        if source not in na_vals:
                            t_text = re.sub(mm_regex, '', source).strip()
                            if t_text: break
                            
                p_tip = pool['Πάχος Μύτης'].fillna('').astype(str).str.lower().str.strip()
                p_nib = pool['Τύπος Μύτης'].fillna('').astype(str).str.lower().str.strip()
                p_title = pool['Title'].fillna('').astype(str).str.lower()
                
                p_mm = p_tip.str.extract(mm_regex, expand=False).fillna(
                       p_nib.str.extract(mm_regex, expand=False)).fillna(
                       p_title.str.extract(mm_regex, expand=False)).fillna('').str.replace(' ', '').str.replace(',', '.')
                
                p_text = p_nib.replace(na_vals, '').where(p_nib.replace(na_vals, '') != '', p_tip.replace(na_vals, ''))
                
                if t_mm: is_same_variant = p_mm == t_mm
                elif t_text: is_same_variant = p_text.apply(lambda x: t_text in x or x in t_text if x else False)
                else: is_same_variant = pd.Series(True, index=pool.index)
                
                color_col = 'Χρώμα Γραφής' if 'Χρώμα Γραφής' in pool.columns else 'Χρώμα'
                color_na_vals = ['#N/A', 'ΜΗ ΔΙΑΘΕΣΙΜΗ ΠΛΗΡΟΦΟΡΙΑ', 'NULL', 'NAN', 'N/A', 'NONE', '0']
                
                pool_colors = pool.get(color_col, pd.Series('', index=pool.index)).fillna('').astype(str).str.strip().str.upper().replace(color_na_vals, '')
                pool_colors_clean = pool_colors.str.replace('Ύ', 'Υ').str.replace('Ά', 'Α').str.replace('Έ', 'Ε').str.replace('Ί', 'Ι').str.replace('Ό', 'Ο').str.replace('Ή', 'Η').str.replace('Ώ', 'Ω')
                trigger_color_clean = tcolor.upper().replace('Ύ', 'Υ').replace('Ά', 'Α').replace('Έ', 'Ε').replace('Ί', 'Ι').replace('Ό', 'Ο').replace('Ή', 'Η').replace('Ώ', 'Ω')
                
                candidate_titles_clean = p_title.str.upper().str.replace('Ύ', 'Υ').str.replace('Ά', 'Α').str.replace('Έ', 'Ε').str.replace('Ί', 'Ι').str.replace('Ό', 'Ο').str.replace('Ή', 'Η').str.replace('Ώ', 'Ω')
                
                has_col_diff = (pool_colors_clean != '') & (~pool_colors_clean.str.contains(trigger_color_clean, regex=False, na=False))
                has_title_diff = (pool_colors_clean == '') & (~candidate_titles_clean.str.contains(trigger_color_clean, regex=False, na=False))
                is_diff_color = has_col_diff | has_title_diff
                
                is_same_brand = target_brands == tb
                
                # --- CASCADE FALLBACK LOGIC ---
                b4_var = len(pool)
                strict_mask = is_same_brand & is_same_variant & is_diff_color
                
                if not pool[strict_mask].empty:
                    pool = pool[strict_mask]
                    notes.append(f"Pen Variant (Strict: Brand+Tip+Color): {b4_var} → {len(pool)}")
                elif not pool[is_same_brand & is_diff_color].empty:
                    pool = pool[is_same_brand & is_diff_color]
                    notes.append(f"Pen Variant (Fallback 1: Brand+Color, Ignored Tip): {b4_var} → {len(pool)}")
                elif not pool[is_same_brand].empty:
                    pool = pool[is_same_brand]
                    notes.append(f"Pen Variant (Fallback 2: Any from Brand): {b4_var} → {len(pool)}")
                else:
                    notes.append("⚠ No brand match found. Skipping variant match.")
                    pool = pool.head(0)
            else:
                notes.append("⚠ Missing Brand or Color on trigger. Skipping variant match.")
                pool = pool.head(0)

        # ── Marker Variant Match (Same Brand, Same Variant/Type, Different Color) ──
        # Handles BOTH singular "Μαρκαδόρος" triggers AND plural "Μαρκαδόροι" multi-packs.
        if flags.get('match_marker_variant'):
            if tb:
                target_brands = pool['Κατασκευαστής'].fillna('').str.strip().str.upper()
                
                na_vals = ['nan', 'n/a', 'none', '0', '#n/a', 'μη διαθέσιμη πληροφορία', 'null', '']
                mm_regex = r'(\d+(?:[\.,]\d+)?(?:-\d+(?:[\.,]\d+)?)?\s*mm)'
                
                # Detect trigger shape: singular vs plural (multi-pack)
                pack_pattern = r'\bμαρκαδόροι\b|\d+\s*τεμ|\d+\s*χρώμ|σετ|pack|set'
                single_pattern = r'\bμαρκαδόρος\b'
                is_single_trigger = bool(re.search(single_pattern, _tt_lower)) and not bool(re.search(pack_pattern, _tt_lower))
                is_pack_trigger = bool(re.search(pack_pattern, _tt_lower))
                
                # Tip/variant extraction (same as before)
                t_tip_raw = str(trigger.get('Πάχος Μύτης', '')).strip().lower()
                t_nib_raw = str(trigger.get('Τύπος Μύτης', '')).strip().lower()
                t_mm, t_text = '', ''
                
                for source in [t_tip_raw, t_nib_raw, _tt_lower]:
                    if source not in na_vals:
                        match = re.search(mm_regex, source)
                        if match:
                            t_mm = match.group(1).replace(' ', '').replace(',', '.')
                            break
                if not t_mm:
                    for source in [t_nib_raw, t_tip_raw]:
                        if source not in na_vals:
                            t_text = re.sub(mm_regex, '', source).strip()
                            if t_text: break
                            
                p_tip = pool['Πάχος Μύτης'].fillna('').astype(str).str.lower().str.strip()
                p_nib = pool['Τύπος Μύτης'].fillna('').astype(str).str.lower().str.strip()
                p_title = pool['Title'].fillna('').astype(str).str.lower()
                
                p_mm = p_tip.str.extract(mm_regex, expand=False).fillna(
                       p_nib.str.extract(mm_regex, expand=False)).fillna(
                       p_title.str.extract(mm_regex, expand=False)).fillna('').str.replace(' ', '').str.replace(',', '.')
                
                p_text = p_nib.replace(na_vals, '').where(p_nib.replace(na_vals, '') != '', p_tip.replace(na_vals, ''))
                
                if t_mm: is_same_variant = p_mm == t_mm
                elif t_text: is_same_variant = p_text.apply(lambda x: t_text in x or x in t_text if x else False)
                else: is_same_variant = pd.Series(True, index=pool.index)
                
                is_single_candidate = p_title.str.contains(single_pattern, regex=True) & ~p_title.str.contains(pack_pattern, regex=True)
                is_pack_candidate = p_title.str.contains(pack_pattern, regex=True)
                
                is_same_brand = target_brands == tb
                
                # Color diff only meaningful for singulars; for packs, often "Πολύχρωμο"
                color_col = 'Χρώμα Γραφής' if 'Χρώμα Γραφής' in pool.columns else 'Χρώμα'
                color_na_vals = ['#N/A', 'ΜΗ ΔΙΑΘΕΣΙΜΗ ΠΛΗΡΟΦΟΡΙΑ', 'NULL', 'NAN', 'N/A', 'NONE', '0']
                
                pool_colors = pool.get(color_col, pd.Series('', index=pool.index)).fillna('').astype(str).str.strip().str.upper().replace(color_na_vals, '')
                pool_colors_clean = pool_colors.str.replace('Ύ', 'Υ').str.replace('Ά', 'Α').str.replace('Έ', 'Ε').str.replace('Ί', 'Ι').str.replace('Ό', 'Ο').str.replace('Ή', 'Η').str.replace('Ώ', 'Ω')
                trigger_color_clean = tcolor.upper().replace('Ύ', 'Υ').replace('Ά', 'Α').replace('Έ', 'Ε').replace('Ί', 'Ι').replace('Ό', 'Ο').replace('Ή', 'Η').replace('Ώ', 'Ω')
                candidate_titles_clean = p_title.str.upper().str.replace('Ύ', 'Υ').str.replace('Ά', 'Α').str.replace('Έ', 'Ε').str.replace('Ί', 'Ι').str.replace('Ό', 'Ο').str.replace('Ή', 'Η').str.replace('Ώ', 'Ω')
                
                has_col_diff = (pool_colors_clean != '') & (~pool_colors_clean.str.contains(trigger_color_clean, regex=False, na=False))
                has_title_diff = (pool_colors_clean == '') & (~candidate_titles_clean.str.contains(trigger_color_clean, regex=False, na=False))
                is_diff_color = has_col_diff | has_title_diff
                
                b4_var = len(pool)
                
                if is_single_trigger:
                    # ── SINGLE TRIGGER → prefer single candidates, different color ──
                    strict_mask = is_same_brand & is_same_variant & is_diff_color & is_single_candidate
                    if not pool[strict_mask].empty:
                        pool = pool[strict_mask]
                        notes.append(f"Marker Variant (Single/Strict: Brand+Tip+Color+Single): {b4_var} → {len(pool)}")
                    elif not pool[is_same_brand & is_single_candidate & is_diff_color].empty:
                        pool = pool[is_same_brand & is_single_candidate & is_diff_color]
                        notes.append(f"Marker Variant (Single/Fallback 1: Brand+Single+Color): {b4_var} → {len(pool)}")
                    elif not pool[is_same_brand & is_diff_color].empty:
                        pool = pool[is_same_brand & is_diff_color]
                        notes.append(f"Marker Variant (Single/Fallback 2: Brand+Color, Any Pack): {b4_var} → {len(pool)}")
                    elif not pool[is_same_brand].empty:
                        pool = pool[is_same_brand]
                        notes.append(f"Marker Variant (Single/Fallback 3: Any from Brand): {b4_var} → {len(pool)}")
                    else:
                        notes.append("⚠ No brand match for single variant.")
                        pool = pool.head(0)
                elif is_pack_trigger:
                    # ── PACK TRIGGER → prefer other packs from same brand, same tip type ──
                    strict_mask = is_same_brand & is_pack_candidate & is_same_variant
                    if not pool[strict_mask].empty:
                        pool = pool[strict_mask]
                        notes.append(f"Marker Variant (Pack/Strict: Brand+Tip+Pack): {b4_var} → {len(pool)}")
                    elif not pool[is_same_brand & is_pack_candidate].empty:
                        pool = pool[is_same_brand & is_pack_candidate]
                        notes.append(f"Marker Variant (Pack/Fallback 1: Brand+Pack Any): {b4_var} → {len(pool)}")
                    elif not pool[is_same_brand].empty:
                        pool = pool[is_same_brand]
                        notes.append(f"Marker Variant (Pack/Fallback 2: Any from Brand): {b4_var} → {len(pool)}")
                    else:
                        notes.append("⚠ No brand match for pack variant.")
                        pool = pool.head(0)
                else:
                    # Neither clearly single nor pack: just brand match
                    if not pool[is_same_brand].empty:
                        pool = pool[is_same_brand]
                        notes.append(f"Marker Variant (Generic/Brand only): {b4_var} → {len(pool)}")
                    else:
                        notes.append("⚠ No brand match.")
                        pool = pool.head(0)
            else:
                notes.append("⚠ No brand on trigger. Skipping marker variant match.")
                pool = pool.head(0)
       
       
                
       # ── Eidos (Type) Include Match ──
        if flags.get('eidos_include') and 'Είδος' in pool.columns:
            allowed_types = flags['eidos_include']
            pat = '|'.join(re.escape(str(x)) for x in allowed_types)
            
            m_eidos = pool['Είδος'].fillna('').astype(str).str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').astype(str).str.contains(pat, case=False, regex=True, na=False)
            m_combined = m_eidos | m_title
            
            if m_combined.any():
                b4_eidos = len(pool)
                pool = pool[m_combined].copy()
                notes.append(f"Eidos filter ({pat}): {b4_eidos} → {len(pool)}")
            else:
                pool = pool.head(0) 
                notes.append(f"❌ Strict Eidos filter ({pat}) found 0 matches. Slot ignored.")

        # ── Eidos (Type) Boost — soft preference for these Είδος values ──
        if flags.get('eidos_boost') and 'Είδος' in pool.columns:
            pat = '|'.join(flags['eidos_boost'])
            m_eidos = pool['Είδος'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_combined = m_eidos | m_title
            if m_combined.any():
                pool.loc[m_combined, 'Final_Score'] += 80000
                notes.append(f"Eidos boost ({pat}): +80k to {m_combined.sum()} items")

        # ── Eidos (Type) Exclude — hard-filter out these Είδος values ──
        if flags.get('eidos_exclude') and 'Είδος' in pool.columns:
            pat = '|'.join(flags['eidos_exclude'])
            m_eidos = pool['Είδος'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_excl = m_eidos | m_title
            if m_excl.any() and not pool[~m_excl].empty:
                b4 = len(pool)
                pool = pool[~m_excl]
                notes.append(f"Eidos exclude ({pat}): {b4} → {len(pool)}")
            elif m_excl.any():
                pool.loc[m_excl, 'Final_Score'] -= 150000
                notes.append(f"Eidos exclude ({pat}): would empty pool, penalized {m_excl.sum()}")

        # ── Typos (Τύπος) Include Filter ──
        if flags.get('typos_include') and 'Τύπος' in pool.columns:
            pat = '|'.join(flags['typos_include'])
            m_typos = pool['Τύπος'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_combined = m_typos | m_title
            if m_combined.any():
                b4 = len(pool)
                pool = pool[m_combined]
                notes.append(f"Typos filter ({pat}): {b4} → {len(pool)}")
            else:
                notes.append(f"⚠ Typos filter ({pat}) would empty pool, skipped")

        # ── Typos (Τύπος) Boost ──
        if flags.get('typos_boost') and 'Τύπος' in pool.columns:
            pat = '|'.join(flags['typos_boost'])
            m_typos = pool['Τύπος'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_combined = m_typos | m_title
            if m_combined.any():
                pool.loc[m_combined, 'Final_Score'] += 80000
                notes.append(f"Typos boost ({pat}): +80k to {m_combined.sum()} items")

        # ── Typos (Τύπος) Exclude ──
        if flags.get('typos_exclude') and 'Τύπος' in pool.columns:
            pat = '|'.join(flags['typos_exclude'])
            m_typos = pool['Τύπος'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_title = pool['Title'].fillna('').str.contains(pat, case=False, regex=True, na=False)
            m_excl = m_typos | m_title
            if m_excl.any() and not pool[~m_excl].empty:
                b4 = len(pool)
                pool = pool[~m_excl]
                notes.append(f"Typos exclude ({pat}): {b4} → {len(pool)}")
            elif m_excl.any():
                pool.loc[m_excl, 'Final_Score'] -= 150000

        # ── Χρήση (Usage) filter — hide/penalize products by their usage category ──
        if flags.get('usage_hide') and 'Χρήση' in pool.columns:
            hide_usages = flags['usage_hide']
            pat_usage = '|'.join(re.escape(u) for u in hide_usages)
            m_hide = pool['Χρήση'].fillna('').str.contains(pat_usage, case=False, regex=True, na=False)
            if m_hide.any():
                pool.loc[m_hide, 'Final_Score'] -= 100000
                notes.append(f"Usage hide ({', '.join(hide_usages)}): penalized {m_hide.sum()}")
                
        # ── Wrist rest / XXL filters ──
        if flags.get('wrist_rest_only'):
            m = pool['Title'].fillna('').str.contains(r'Gel|Wrist|Καρπού|Μαξιλαράκι|Rest', case=False, regex=True, na=False)
            pool, note = filter_or_penalize(pool, m, "Wrist rest")
            notes.append(note)

        if flags.get('xxl_only'):
            m = pool['Title'].fillna('').str.contains(r'XXL|XL|Extended|Desk Mat', case=False, regex=True, na=False)
            if 'Μέγεθος16' in pool.columns:
                m |= pool['Μέγεθος16'].fillna('').str.contains(r'XXL|XL|Extended', case=False, regex=True, na=False)
            pool, note = filter_or_penalize(pool, m, "XXL/Desk Mat")
            notes.append(note)

        # ── Silent / Ergo / RGB matching ──
        if flags.get('silent_match') and is_silent:
            sm = pool['Title'].fillna('').str.lower().str.contains('silent|αθόρυβ')
            if 'Αθόρυβο' in pool.columns:
                sm |= pool['Αθόρυβο'].fillna('').astype(str).str.lower().isin(['ναι', 'yes'])
            pool.loc[sm, 'Final_Score'] += 60000

        if flags.get('ergo_match') and is_ergo:
            em = pool['Title'].fillna('').str.lower().str.contains('ergonomic|εργονομικ')
            if 'Εργονομικό' in pool.columns:
                em |= pool['Εργονομικό'].fillna('').astype(str).str.lower().isin(['ναι', 'yes'])
            pool.loc[em, 'Final_Score'] += 60000

        if flags.get('rgb_match'):
            rm = pool['Title'].fillna('').str.lower().str.contains('rgb|chroma|aura|lightsync')
            if has_rgb:
                pool.loc[rm, 'Final_Score'] += 40000
            else:
                pool.loc[rm, 'Final_Score'] -= 20000

        # ── Color match ──
        if do_color_match and flags.get('brand_match'):
            if 'Χρώμα' in pool.columns:
                cm = pool['Χρώμα'].fillna('').astype(str).str.upper() == tcolor.upper()
                pool.loc[cm, 'Final_Score'] += 30000



        # ── Writing Instrument Precision Matching ──
        if flags.get('match_writing_type'):
            t_type = str(trigger.get('Τύπος', '')).lower()
            
            # Rule 1: Mechanical Pencil -> Needs "Μύτες" (Leads)
            if 'μηχανικό' in t_type:
                is_leads = pool['Τύπος'].fillna('').str.lower().str.contains('μύτες')
                pool.loc[is_leads, 'Final_Score'] += 200000
                notes.append("Mechanical Pencil detected -> Boosted 'Μύτες'")
                
            # Rule 2: Ink/Gel/Roller -> Needs Correction Tape/Fluid (not a classic eraser)
            elif any(x in t_type for x in ['gel', 'υγρής', 'roller', 'διαρκείας', 'πένα']):
                is_tape = pool['Είδος'].fillna('').str.lower().str.contains('ταινία|υγρό')
                pool.loc[is_tape, 'Final_Score'] += 100000
                notes.append("Ink pen detected -> Boosted Correction Tape/Fluid")
                
            # Rule 3: Classic Pencil -> Needs classic sharpener with bin (Βαρελάκι)
            elif 'απλό' in t_type:
                is_barrel_sharpener = pool['Είδος'].fillna('').str.lower().str.contains('βαρελάκι|μανιβέλα')
                pool.loc[is_barrel_sharpener, 'Final_Score'] += 80000
                notes.append("Classic pencil detected -> Boosted 'Βαρελάκι' sharpeners")

        # ── Deep Attribute Matching (Art Mediums & Techniques) ──
        if flags.get('match_art_medium'):
            # 1. Identify the trigger's medium from its Τύπος or Είδος
            trigger_mediums = []
            t_type = str(trigger.get('Τύπος', '')).lower()
            t_eidos = str(trigger.get('Είδος', '')).lower()
            combined_trigger_text = f"{t_type} {t_eidos} {_tt_lower}"
            
            # Mapping core mediums to their various Greek naming conventions
            medium_map = {
                'watercolor': ['ακουαρέλα', 'νερομπογιά', 'νερού'],
                'oil': ['λαδιού', 'λαδοπαστέλ'],
                'acrylic': ['ακρυλικ'],
                'sketch': ['σχεδίου', 'μιλιμετρέ', 'κάρβουνο', 'γραφίτης'],
                'pastel': ['παστέλ', 'κιμωλία']
            }
            
            active_medium = None
            for medium_key, keywords in medium_map.items():
                if any(kw in combined_trigger_text for kw in keywords):
                    active_medium = medium_key
                    break
            
            # 2. Boost candidates that match the active medium
            if active_medium:
                candidate_text = pool['Τύπος'].fillna('').astype(str) + " " + pool['Είδος'].fillna('').astype(str) + " " + pool['Title'].fillna('').astype(str)
                candidate_text = candidate_text.str.lower()
                
                # Create a mask for candidates containing the matching keywords
                match_mask = pd.Series(False, index=pool.index)
                for kw in medium_map[active_medium]:
                    match_mask |= candidate_text.str.contains(kw, regex=False)
                
                # Massive boost for perfect medium match
                pool.loc[match_mask, 'Final_Score'] += 150000
                notes.append(f"Art Medium Match ({active_medium}): Boosted {match_mask.sum()} items")

        # ── Nib Type Deep Matching (Λεπτή, Χονδρή, Πλακέ, κλπ) ──
        if flags.get('match_nib_type'):
            t_nib = str(trigger.get('Τύπος Μύτης', '')).strip().lower()
            
            # Έξυπνο Fallback αν το κελί είναι άδειο (διαβάζει τον τίτλο)
            if not t_nib or t_nib == 'nan':
                if re.search(r'fine|λεπτή|0\.[1-8]mm', _tt_lower): t_nib = 'λεπτή'
                elif re.search(r'χονδρή|maxi|jumbo|broad', _tt_lower): t_nib = 'χονδρή'
                elif re.search(r'πλακέ|chisel|υπογράμμισης', _tt_lower): t_nib = 'πλακέ'
                elif re.search(r'σφραγίδα|stamp', _tt_lower): t_nib = 'σφραγίδα'
            
            if t_nib:
                # 1. Boost σε εναλλακτικούς μαρκαδόρους με την ΙΔΙΑ μύτη
                if 'Τύπος Μύτης' in pool.columns:
                    is_same_nib = pool['Τύπος Μύτης'].fillna('').astype(str).str.strip().str.lower() == t_nib
                    pool.loc[is_same_nib, 'Final_Score'] += 80000
                    if is_same_nib.any():
                        notes.append(f"Nib Match ({t_nib}): +80k points to {is_same_nib.sum()} items")
                
                # 2. Έξυπνα Cross-Sells (Χαρτιά & Αξεσουάρ) ανάλογα τη μύτη
                candidate_text = pool['Title'].fillna('').astype(str).str.lower() + " " + pool['Είδος'].fillna('').astype(str).str.lower()
                
                if t_nib == 'λεπτή':
                    # Λεπτή Μύτη -> Σχέδιο ακριβείας, χάρακες, μιλιμετρέ χαρτί
                    is_precision = candidate_text.str.contains(r'σχεδίου|μιλιμετρέ|χάρακας|fineliner|ακριβείας|fine')
                    pool.loc[is_precision, 'Final_Score'] += 60000
                    notes.append(f"Fine Nib -> Boosted precision tools/paper ({is_precision.sum()} items)")
                    
                elif t_nib == 'χονδρή' or t_nib == 'σφραγίδα':
                    # Χονδρή/Σφραγίδα -> Μεγάλα μπλοκ ζωγραφικής, παιδικά craft
                    is_broad_art = candidate_text.str.contains(r'ακουαρέλας|ζωγραφικής|maxi|jumbo|craft')
                    pool.loc[is_broad_art, 'Final_Score'] += 60000
                    notes.append(f"Broad/Stamp Nib -> Boosted art/drawing blocks ({is_broad_art.sum()} items)")
                    
                elif t_nib == 'πλακέ' or t_nib == 'μεσαία':
                    # Πλακέ (Chisel) / Μεσαία -> Υπογράμμιση, Τετράδια, Σημειώσεις
                    is_chisel_acc = candidate_text.str.contains(r'σημειώσεων|τετράδιο|υπογράμμισης|καλλιγραφίας')
                    pool.loc[is_chisel_acc, 'Final_Score'] += 60000
                    notes.append(f"Chisel Nib -> Boosted notebooks/highlighters ({is_chisel_acc.sum()} items)")
        
        # ── Kids vs Adult Coloring Activity Matching ──
        if flags.get('match_coloring_activity'):
            t_eidos = str(trigger.get('Είδος', '')).lower()
            is_art_marker = 'ζωγραφικής' in t_eidos or 'ζωγραφικής' in _tt_lower or 'drawing' in _tt_lower
            
            if not is_art_marker:
                notes.append("Not an art marker. Skipping coloring pad slot.")
                pool = pool.head(0)
            else:
                kids_brands = ['GIOTTO', 'CARIOCA', 'CRAYOLA', 'MAPED', 'FIBRAPEN', 'MILAN', 'BIC']
                is_kid = tb in kids_brands or 'παιδ' in _tt_lower or 'kids' in _tt_lower or 'maxi' in _tt_lower or 'jumbo' in _tt_lower
                
                b4_col = len(pool)
                hier_col = pool['Hierarchy'].fillna('').str.upper().str.strip()
                
                if is_kid:
                    # 👧 Παιδιά: Απαγορεύουμε τα COLORING BOOKS ενηλίκων και ζητάμε αυστηρά είδη ζωγραφικής/μπλοκ
                    is_coloring_book_hier = hier_col == 'COLORING BOOKS'
                    is_drawing_pad = pool['Είδος'].fillna('').str.lower() == 'ζωγραφικής'
                    is_drawing_pad |= pool['Title'].fillna('').str.lower().str.contains('μπλοκ ζωγραφικής|sketch pad|μπλοκ σχεδίου')
                    is_adult = pool['Title'].fillna('').str.lower().str.contains('mandala|μαντάλα|ενηλίκων|adult')
                    
                    pool = pool[(is_drawing_pad) & (~is_adult) & (~is_coloring_book_hier)]
                    notes.append(f"Kids Marker -> Φιλτράρισμα σε 'Μπλοκ Ζωγραφικής' ({b4_col} → {len(pool)})")
                else:
                    # 🧑 Ενήλικες: Στοχεύουμε ΑΠΕΥΘΕΙΑΣ τη Hierarchy 'COLORING BOOKS' (από τα βιβλία)
                    # ή ειδικά χαρτιά μαρκαδόρων από τα Χαρτικά!
                    is_coloring_book_hier = hier_col == 'COLORING BOOKS'
                    is_adult_title = pool['Title'].fillna('').str.lower().str.contains('mandala|μαντάλα|ενηλίκων|adult|coloring book')
                    is_pro_pad = pool['Title'].fillna('').str.lower().str.contains('coloring book')
                    
                    pool = pool[is_coloring_book_hier | is_adult_title | is_pro_pad]
                    notes.append(f"Adult Marker -> Φιλτράρισμα σε COLORING BOOKS / Pro Pads ({b4_col} → {len(pool)})")

                
        # ── Deep Attribute Matching (Art Mediums & Techniques) ──
        if flags.get('match_art_medium'):
            # 1. Identify the trigger's medium from its Τύπος or Είδος
            trigger_mediums = []
            t_type = str(trigger.get('Τύπος', '')).lower()
            t_eidos = str(trigger.get('Είδος', '')).lower()
            combined_trigger_text = f"{t_type} {t_eidos} {_tt_lower}"
            
            # Mapping core mediums to their various Greek naming conventions
            medium_map = {
                'watercolor': ['ακουαρέλα', 'νερομπογιά', 'νερού'],
                'oil': ['λαδιού', 'λαδοπαστέλ'],
                'acrylic': ['ακρυλικ'],
                'sketch': ['σχεδίου', 'μιλιμετρέ', 'κάρβουνο', 'γραφίτης'],
                'pastel': ['παστέλ', 'κιμωλία']
            }
            
            active_medium = None
            for medium_key, keywords in medium_map.items():
                if any(kw in combined_trigger_text for kw in keywords):
                    active_medium = medium_key
                    break
            
            # 2. Boost candidates that match the active medium
            if active_medium:
                candidate_text = pool['Τύπος'].fillna('').astype(str) + " " + pool['Είδος'].fillna('').astype(str) + " " + pool['Title'].fillna('').astype(str)
                candidate_text = candidate_text.str.lower()
                
                # Create a mask for candidates containing the matching keywords
                match_mask = pd.Series(False, index=pool.index)
                for kw in medium_map[active_medium]:
                    match_mask |= candidate_text.str.contains(kw, regex=False)
                
                # Massive boost for perfect medium match
                pool.loc[match_mask, 'Final_Score'] += 150000
                notes.append(f"Art Medium Match ({active_medium}): Boosted {match_mask.sum()} items")

        # ── DPI-based pad size (Gaming Mouse #17 L3) ──
        if flags.get('dpi_pad_size') and dpi_str:
            high_dpi = any(x in dpi_str for x in ['6401', '12801', '25600'])
            if high_dpi:
                m = pool['Title'].fillna('').str.contains(r'Medium|Small', case=False, regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 40000
                notes.append("High DPI → Medium/Small pad boost")
            else:
                m = pool['Title'].fillna('').str.contains(r'Large|XL', case=False, regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 40000
                notes.append("Low DPI → Large pad boost")

        # ── Sensor → Surface (Gaming Mouse #17 L6) ──
        if flags.get('sensor_surface') and sensor_type:
            if 'laser' in sensor_type:
                m = pool['Title'].fillna('').str.lower().str.contains('hard|hybrid|plastic')
                pool.loc[m, 'Final_Score'] += 30000
            elif 'optical' in sensor_type:
                m = pool['Title'].fillna('').str.lower().str.contains('cloth|fabric|control')
                pool.loc[m, 'Final_Score'] += 30000

        # ── Button count → keyboard size (Gaming Mouse #17 L5) ──
        if flags.get('button_kb_size') and button_count > 0:
            if 'Μέγεθος πληκτρολογίου' in pool.columns:
                if button_count >= 9:
                    m = pool['Μέγεθος πληκτρολογίου'].fillna('').str.contains('Full', case=False, na=False)
                    pool.loc[m, 'Final_Score'] += 30000
                    notes.append(f"MMO ({button_count} buttons) → Full-size KB")
                elif button_count <= 6:
                    m = pool['Μέγεθος πληκτρολογίου'].fillna('').str.contains(r'Tenkeyless|60%|65%|TKL', case=False, regex=True, na=False)
                    pool.loc[m, 'Final_Score'] += 30000
                    notes.append(f"FPS ({button_count} buttons) → TKL/60% KB")

        # ── VESA match (Monitors) ──
        if flags.get('vesa_match') and tvesa and tvesa.lower() not in ('', 'nan', 'n/a'):
            if 'Πρότυπο VESA' in pool.columns:
                vm = pool['Πρότυπο VESA'].fillna('').astype(str).str.upper().str.contains(tvesa.upper(), na=False)
                pool.loc[vm, 'Final_Score'] += 80000
                notes.append(f"VESA match ({tvesa}): {vm.sum()}")

       # ── Cable port match (Monitors — uses dedicated HDMI/DP/USB columns) ──
# ── Cable port match (Monitors — uses dedicated HDMI/DP/USB columns) ──
        if flags.get('cable_port_match'):
            port_keyword = flags['cable_port_match'].lower()
            # Map flag to dedicated port boolean
            port_present = False
            if 'displayport' in port_keyword or 'dp' == port_keyword:
                port_present = has_dp
            elif 'usb' in port_keyword or 'type-c' in port_keyword:
                port_present = has_usb
            elif 'hdmi' in port_keyword:
                port_present = has_hdmi
            else:
                # Fallback to old Θύρες substring
                port_present = port_keyword in tports

            if port_present:
                m = pool['Title'].fillna('').str.lower().str.contains(port_keyword, na=False)
                pool.loc[m, 'Final_Score'] += 80000
                notes.append(f"Port match ({port_keyword}): ✅ Monitor has this port, boosted {m.sum()}")
            else:
                # Monitor doesn't have this port → skip slot
                notes.append(f"Port match ({port_keyword}): ❌ Monitor lacks this port → skipping")
                slot_notes[idx] = notes
                diag.append((f"Slot {idx} ({role})", 0, f"No {port_keyword} port"))
                # This 'continue' is now correctly inside the 'for' loop
                continue

        # ── Cable length boost (Monitors mainstream) ──
        if flags.get('cable_length_boost'):
            if 'Μήκος Καλωδίου6' in pool.columns:
                length = pool['Μήκος Καλωδίου6'].fillna('').astype(str)
                m = length.str.contains(r'1\.[5-9]|2\.0|2m|1\.8', regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 30000

        # ── Resolution match (Webcam→Monitor res) ──
        if flags.get('resolution_match') and tres:
            if '4k' in tres or 'uhd' in tres or '5k' in tres:
                m = pool['Title'].fillna('').str.lower().str.contains('4k', na=False)
                pool.loc[m, 'Final_Score'] += 60000
                notes.append("4K monitor → 4K webcam boost")

        # ── UPS min VA (Laser printers) ──
        if flags.get('ups_min_va'):
            min_va = flags['ups_min_va']
            if 'Ισχύς' in pool.columns:
                va_vals = pd.to_numeric(pool['Ισχύς'].astype(str).str.extract(r'(\d+)', expand=False), errors='coerce').fillna(0)
                m = va_vals >= min_va
                pool.loc[m, 'Final_Score'] += 60000
                notes.append(f"UPS ≥{min_va}VA: {m.sum()}")

        # ── Ink/Toner model match (Printers) ──
        if flags.get('ink_model_match') or flags.get('toner_model_match'):
            if tink and tink.lower() not in ('', 'nan', 'n/a'):
                # Try matching cartridge model to printer's consumable spec
                for mcol in ['Μοντέλο', 'Συμβατό μοντέλο', 'Συμβατό μοντέλο2']:
                    if mcol in pool.columns:
                        ink_parts = [p.strip() for p in re.split(r'[,;/]', tink) if p.strip()]
                        for part in ink_parts:
                            m = pool[mcol].fillna('').astype(str).str.upper().str.contains(
                                re.escape(part.upper()), regex=True, na=False
                            )
                            pool.loc[m, 'Final_Score'] += 200000
                notes.append(f"Consumable match: '{tink[:40]}'")

        # ── Paper weight filters ──
        if flags.get('paper_weight_max') and 'Βάρος' in pool.columns:
            max_w = flags['paper_weight_max']
            w_vals = pd.to_numeric(pool['Βάρος'].astype(str).str.extract(r'(\d+)', expand=False), errors='coerce').fillna(80)
            m = w_vals <= max_w
            pool.loc[m, 'Final_Score'] += 30000

        if flags.get('paper_weight_min') and 'Βάρος' in pool.columns:
            min_w = flags['paper_weight_min']
            w_vals = pd.to_numeric(pool['Βάρος'].astype(str).str.extract(r'(\d+)', expand=False), errors='coerce').fillna(80)
            m = w_vals >= min_w
            pool.loc[m, 'Final_Score'] += 30000

        # ── USB version match (Hub) ──
        if flags.get('usb_version_match') and hub_interface:
            if 'usb 3' in hub_interface or 'usb 4' in hub_interface:
                m = pool['Title'].fillna('').str.lower().str.contains(r'usb 3|superspeed|usb 4', regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 40000

        # ── Port count → storage sizing (Hub) ──
        if flags.get('port_count_storage'):
            try:
                port_n = int(re.search(r'(\d+)', hub_ports_str).group(1)) if hub_ports_str else 4
            except: port_n = 4
            if port_n >= 7:
                if 'Χωρητικότητα' in pool.columns:
                    m = pool['Χωρητικότητα'].fillna('').astype(str).str.contains(r'1\s*TB|2\s*TB|4\s*TB|128\s*GB|256\s*GB', regex=True, na=False)
                    pool.loc[m, 'Final_Score'] += 30000
                    notes.append("7+ port hub → large storage boost")

        # ── Hub cable type match ──
        if flags.get('hub_cable_type'):
            if 'usb-c' in hub_input or 'type-c' in hub_input:
                m = pool['Title'].fillna('').str.lower().str.contains('usb-c|type-c', regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 80000
                notes.append("USB-C hub → USB-C cable boost")
            elif 'usb-a' in hub_input or 'type-a' in hub_input:
                m = pool['Title'].fillna('').str.lower().str.contains('usb-a|type-a|extension', regex=True, na=False)
                pool.loc[m, 'Final_Score'] += 80000

        # ── Pick best ──
        if pool.empty:
            notes.append("❌ Empty after filters")
            slot_notes[idx] = notes
            diag.append((f"Slot {idx} ({role})", 0, "Empty"))
            continue

        pool = pool.sort_values('Final_Score', ascending=False)
        chosen = pool.iloc[0]
        rc = chosen.copy()
        rc['Assigned_Slot'] = idx
        rc['Slot_Role'] = role
        rc['Marketing_Copy'] = "Ταιριάζει τέλεια στο setup σου."
        rc['Item_Rank'] = 1
        all_recs.append(rc)
        used_materials.add(chosen['Material'])
        notes.append(f"✅ {str(chosen.get('Title',''))[:60]}")
        slot_notes[idx] = notes
        diag.append((f"Slot {idx} ({role})", 1, f"Score: {chosen.get('Final_Score',0):.0f}"))

    diag.append(("TOTAL", len(all_recs), f"out of {len(slots)}"))

    # ═══════════════════════════════════════════════════════════
    # BACKFILL: If any slots are empty, recycle earlier hierarchies
    # to always show a full carousel. First pass with brand match,
    # second pass without.
    # ═══════════════════════════════════════════════════════════
    max_slots = len(slots)
    if len(all_recs) < max_slots and (cluster_key in ("Mouse", "Keyboard", "Gaming Mouse", "Gaming Keyboard", "Monitors") or cluster_key in STATIONERY_CLUSTERS):
        empty_count = max_slots - len(all_recs)
        backfill_notes = [f"🔄 Backfill: {empty_count} empty slots to fill"]

        # Build recyclable hierarchy list from filled slots (in order)
        recycle_hiers = []
        for _, hierarchies, _ in slots:
            for h in hierarchies:
                if h not in recycle_hiers:
                    recycle_hiers.append(h)

        filled = 0
        # Pass 1: brand match, Pass 2: no brand match
        for pass_num, do_brand in enumerate([True, False], 1):
            if filled >= empty_count:
                break
            for h in recycle_hiers:
                if filled >= empty_count:
                    break
                hier_upper = h.upper().strip()
                pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip() == hier_upper].copy()
                pool = pool[~pool['Material'].isin(used_materials)]

                if pool.empty:
                    continue

                # ── Scoring ──
                pool['Final_Score'] = 0.0
                if 'AVAILABILITY' in pool.columns:
                    pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
                    
                # 1. Primary: Actual co-purchase history (If people bought them together, boost it massively)
                if 'History_Score' in pool.columns:
                    pool['Final_Score'] += pool['History_Score']
                    pool['Final_Score'] += pool['Frequency'] * 100  # Give a slight edge to items bought together more often

                # 2. Secondary: Global Best Sellers (If no history exists, rely on overall popularity)
                pool['Final_Score'] += pool['Sales_Tiebreaker'].fillna(0) * 0.1

                # Brand boost (pass 1 only)
                if do_brand and tb:
                    target_brands = pool['Κατασκευαστής'].fillna('').str.strip().str.upper()
                    if tb in ['LOGITECH', 'LOGITECH G']:
                        is_same = target_brands.isin(['LOGITECH', 'LOGITECH G'])
                    else:
                        is_same = target_brands == tb
                    brand_pool = pool[is_same]
                    if not brand_pool.empty:
                        pool = brand_pool
                    elif pass_num == 1:
                        continue  # Pass 1: skip if no brand match, try in pass 2

                pool = pool.sort_values('Final_Score', ascending=False)
                chosen = pool.iloc[0]

                next_slot = len(all_recs) + 1
                rc = chosen.copy()
                rc['Assigned_Slot'] = next_slot
                rc['Slot_Role'] = f"Backfill ({h})"
                rc['Marketing_Copy'] = "Ταιριάζει τέλεια στο setup σου."
                rc['Item_Rank'] = 1
                all_recs.append(rc)
                used_materials.add(chosen['Material'])
                filled += 1

                pass_label = "brand" if do_brand else "any"
                backfill_notes.append(f"  Slot {next_slot}: [{pass_label}] {str(chosen.get('Title',''))[:50]} (from {h})")

        diag.append(("BACKFILL", filled, f"Recycled {filled} products"))
        slot_notes[max_slots + 1] = backfill_notes

    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        return recs_df, diag, slot_notes, recs_df
    return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ═══════════════════════════════════════════════════════════════
# 🟢 TV ENGINE — Deep Filtering & Ecosystem Sync
# ═══════════════════════════════════════════════════════════════

def run_tv_engine(trigger, df_products, df_history):
    diag = []
    slot_notes = {}
    all_recs = []

    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))
    
    # --- Attribute Extraction ---
    t_vesa = str(trigger.get('Πρότυπο VESA', '')).strip()
    
    t_weight = 0.0
    try: 
        t_weight = float(str(trigger.get('Βάρος', '0')).replace(',', '.').split()[0])
    except: pass

    t_ideal = str(trigger.get('Ιδανικό για ≡', '')).lower()
    t_extra = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    
    # ── FIX: Έξυπνη Εξαγωγή Ιντσών (Ακόμα κι αν λείπει η στήλη) ──
    t_size_str = str(trigger.get('Μέγεθος οθόνης', trigger.get('Μέγεθος', trigger.get('Ιντσες', ''))))
    t_size = parse_screen_size(t_size_str)
    if t_size == 0.0:
        # Ψάχνει μοτίβα όπως '65"' ή '65 inch' στον τίτλο της TV
        match = re.search(r'(\d{2})\s*["”\']', tt)
        if match: 
            t_size = float(match.group(1))
        else:
            match2 = re.search(r'\b(\d{2})\b', t_size_str)
            if match2: t_size = float(match2.group(1))

    inch_match = re.search(r'(\d{2})', t_size_str)
    if not inch_match: inch_match = re.search(r'(\d{2})', tt)
    t_inches = inch_match.group(1) if inch_match else ""

    # Logic Triggers
    is_gaming_tv = 'gaming' in t_ideal or '100hz' in t_extra or '120hz' in t_extra or '144hz' in t_extra
    is_cinema_tv = 'cinema' in t_ideal or 'ταινίες' in t_ideal
    is_the_frame = 'the frame' in tt.lower()
    is_the_serif = 'serif' in tt.lower()
    
    # ── Κανόνες Βάσει Τιμής & Μεγέθους ──
    is_expensive = tprice > 800
    is_large = t_size >= 65
    is_cheap = tprice <= 800   # used for REMOTE_LOGIC_CHEAP routing — leave as-is

    # ── 4-Tier Price System (separate from is_cheap; controls accessory caps) ──
    # Ranges aligned with Greek market reality (per Achilleas spec):
    # budget   : ≤€400          → Foititiko / bedroom — minimal bundle
    # mid      : €400-900       → Sweet spot family living room (QLED/MiniLED)
    # premium  : €900-1800      → Enthusiast OLED (LG C-series, Samsung S90)
    # flagship : >€1800         → No-compromise home cinema (G-series, Neo QLED 75"+)
    if tprice <= 400:
        price_tier = 'budget'
    elif tprice <= 900:
        price_tier = 'mid'
    elif tprice <= 1800:
        price_tier = 'premium'
    else:
        price_tier = 'flagship'

    # Generic-accessory price caps. Tuned to REAL Greek buyer behavior, not theoretical:
    # - Mounts: most Greek buyers won't pay >€80 for a TV mount even on a €1700 OLED
    # - Surge protectors: 90% buy €10-20 strips; €25-45 only for OLED+soundbar setups
    # - Other accessories: scaled gently with TV price tier
    # Caps are absolute MAX (€); use min(pct*tprice, hard_max) to enforce reality.
    GENERIC_CAPS = {
        'budget':   {'mount': (0.15, 35),  'surge': (0.08, 20),  'hdmi': (0.12, 25),  'antenna': (0.15, 25),  'cleaning': (0.15, 12), 'battery': (0.10, 10), 'cable': (0.10, 10), 'usb': (0.15, 20),  'soundbar': (0.40, 150)},
        'mid':      {'mount': (0.06, 50),  'surge': (0.04, 25),  'hdmi': (0.04, 30),  'antenna': (0.06, 35),  'cleaning': (0.04, 15), 'battery': (0.03, 10), 'cable': (0.03, 12), 'usb': (0.04, 30),  'soundbar': (0.45, 350)},
        'premium':  {'mount': (0.05, 80),  'surge': (0.03, 45),  'hdmi': (0.03, 50),  'antenna': (0.04, 45),  'cleaning': (0.03, 20), 'battery': (0.02, 10), 'cable': (0.02, 15), 'usb': (0.03, 40),  'soundbar': (0.55, 900)},
        'flagship': {'mount': (0.04, 100), 'surge': (0.02, 50),  'hdmi': (0.02, 60),  'antenna': (0.03, 50),  'cleaning': (0.02, 25), 'battery': (0.02, 12), 'cable': (0.02, 18), 'usb': (0.03, 50),  'soundbar': (0.55, 3000)},
    }
    # Floor prices so the cap never collapses to a few cents on cheap TVs
    GENERIC_FLOORS = {'mount': 25, 'surge': 12, 'hdmi': 10, 'antenna': 12, 'cleaning': 8, 'battery': 6, 'cable': 6, 'usb': 10, 'soundbar': 70}

    # Map slot role → cap key
    SLOT_CAP_KEY = {
        'Βάση Στήριξης': 'mount', 'Εναλλακτική Βάση': 'mount', 'Μαγνητικό Πλαίσιο': 'mount',
        'Προστασία Ρεύματος': 'surge',
        'Καλώδιο HDMI': 'hdmi', 'Εφεδρικό HDMI': 'hdmi', 'Εφεδρικό HDMI 2.1': 'hdmi',
        'Κεραία': 'antenna', 'Καλώδιο Κεραίας': 'cable',
        'Καθαρισμός': 'cleaning',
        'Μπαταρίες': 'battery',
        'Αποθήκευση USB': 'usb',
        'Soundbar': 'soundbar', 'Αναβάθμιση Ήχου': 'soundbar',
    }

    diag.append(("0. Trigger", f"Brand={tb}, Size={t_size}\", Price=€{tprice:.0f}", f"Tier={price_tier}, Frame={is_the_frame}, Serif={is_the_serif}, Cheap={is_cheap}"))

    # ── Δυναμική Λίστα Slots (Η 10άδα σου) ──
    # Slot 1: Mount or Magnetic Frame (Frame TVs only)
    if is_the_frame:
        # Frame trigger → use Μαγνητικό Πλαίσιο (magnetic frame) instead of standard mount
        potential_slots = [('Μαγνητικό Πλαίσιο', ['MOUNTS & STANDS'], 'FRAME_LOGIC')]
    elif is_the_serif:
        # Serif TVs have integrated stands — skip mount entirely. Slot 1 becomes surge instead.
        potential_slots = []
    else:
        potential_slots = [('Βάση Στήριξης', ['MOUNTS & STANDS'], 'MOUNT_LOGIC_FIXED')]
    
    # Soundbar slot — tier-based routing.
    # Budget tier: only show if TV is €250-€400 (skip if even cheaper, the gap doesn't justify upsell)
    if price_tier == 'budget':
        if tprice >= 250:
            potential_slots.append(('Soundbar', ['SOUNDBARS'], 'SOUND_LOGIC_TIER_BUDGET'))
        # else: skip soundbar entirely for very cheap TVs (≤€250)
    elif price_tier == 'mid':
        potential_slots.append(('Soundbar', ['SOUNDBARS'], 'SOUND_LOGIC_TIER_MID'))
    elif price_tier == 'premium':
        potential_slots.append(('Soundbar', ['SOUNDBARS'], 'SOUND_LOGIC_TIER_PREMIUM'))
    elif price_tier == 'flagship':
        potential_slots.append(('Soundbar', ['SOUNDBARS'], 'SOUND_LOGIC_TIER_FLAGSHIP'))
    
    # Surge Protectors (Πάντα υπάρχει)
    potential_slots.append(('Προστασία Ρεύματος', ['SURGE PROTECTORS'], 'GENERIC'))
    
    # ── Remote Control Rules ──
    if tb == 'LG' and is_expensive:
        potential_slots.append(('Τηλεχειριστήριο', ['REMOTE CONTROLS'], 'REMOTE_LOGIC_PREMIUM_LG'))
    elif is_cheap:
        potential_slots.append(('Τηλεχειριστήριο', ['REMOTE CONTROLS'], 'REMOTE_LOGIC_CHEAP'))
        
    potential_slots.extend([
        ('Κεραία', ['ANTENNAS'], 'ANTENNA_LOGIC'),
        ('Καλώδιο Κεραίας', ['ΚΕΡΑΙΑΣ'], 'GENERIC'),
        ('Μπαταρίες', ['ΑΛΚΑΛΙΚΕΣ'], 'GENERIC'),
        ('Καλώδιο HDMI', ['HDMI'], 'HDMI_LOGIC'),
        ('Αποθήκευση USB', ['USB FLASH DISK'], 'GENERIC'),
        ('Καθαρισμός', ['CLEANING PRODUCTS'], 'GENERIC'),
        ('Εναλλακτική Βάση', ['MOUNTS & STANDS'], 'MOUNT_LOGIC_MOTION'),
    ])

    # ── Slot 10: dynamic closer (tiered) ──
    # flagship/premium → premium HDMI 2.1 spare (soundbar already in slot 2)
    # mid              → budget soundbar upsell (slot 2 has main soundbar; this is a 2nd cheaper option)
    # budget           → spare HDMI as bundle filler
    if price_tier in ('flagship', 'premium'):
        potential_slots.append(('Εφεδρικό HDMI 2.1', ['HDMI'], 'HDMI_LOGIC_PREMIUM_SPARE'))
    elif price_tier == 'mid':
        potential_slots.append(('Αναβάθμιση Ήχου', ['SOUNDBARS'], 'SOUND_LOGIC_BUDGET'))
    else:
        potential_slots.append(('Εφεδρικό HDMI', ['HDMI'], 'HDMI_LOGIC'))

    # --- Base Candidate Pool & History ---
    c = df_products[df_products['Material'] != tm].copy()
    c['Sales_Tiebreaker'] = pd.to_numeric(c.get('Sum of Sales', 0), errors='coerce').fillna(0)
    c['_p'] = c['LIST PRICE'].apply(parse_euro_price) # Υπολογισμός τιμής αξεσουάρ εκ των προτέρων

    tcust = df_history[df_history['Material']==tm]['customerEmail'].unique() if not df_history.empty else []
    bw = df_history[(df_history['customerEmail'].isin(tcust))&(df_history['Material']!=tm)] if not df_history.empty else pd.DataFrame()
    fdf = bw['Material'].value_counts().reset_index() if not bw.empty else pd.DataFrame(columns=['NID', 'Frequency'])
    if not fdf.empty:
        fdf.columns = ['NID', 'Frequency']
        c = c.merge(fdf, left_on='Material', right_on='NID', how='left')
        c['Frequency'] = c['Frequency'].fillna(0).astype(int)
    else:
        c['Frequency'] = 0

    used_materials = {tm}
    current_slot = 1

    for role, hierarchies, logic_key in potential_slots:
        if current_slot > 10: break # Σταματάμε αυστηρά στα 10 slots
        
        notes = [f"Logic: {logic_key}"]
        hier_upper = [h.upper().strip() for h in hierarchies]

        pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(hier_upper)].copy()
        pool = pool[~pool['Material'].isin(used_materials)]

        if pool.empty:
            diag.append((f"Slot {current_slot}", 0, "Empty Hierarchy"))
            continue

        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
        pool['Final_Score'] += pool['Sales_Tiebreaker'] * 0.1
        pool['Final_Score'] += pool['Frequency'] * 100 

        # ══════════════════════════════════════════════════════════════
        # 🔴 ΑΣΠΙΔΑ ΥΠΕΡΒΟΛΙΚΗΣ ΤΙΜΗΣ (Anti-Overbuy) — TIERED & PER-SLOT
        # ══════════════════════════════════════════════════════════════
        # Cap = max(floor, min(pct*tprice, hard_max)) — three-way clamp:
        #   floor   prevents the cap from collapsing on very cheap TVs
        #   pct     scales softly with TV price
        #   hard_max enforces real Greek buyer behavior (e.g. mounts cap €80)
        cap_key = SLOT_CAP_KEY.get(role)
        if cap_key:
            pct, hard_max = GENERIC_CAPS[price_tier][cap_key]
            floor = GENERIC_FLOORS[cap_key]
            max_price_cap = max(float(floor), min(tprice * pct, float(hard_max)))
            overpriced_mask = pool['_p'] > max_price_cap
            pool.loc[overpriced_mask, 'Final_Score'] -= 800000
            if overpriced_mask.any():
                notes.append(f"Price Cap (€{max_price_cap:.0f}, {price_tier}/{cap_key}): Penalized {overpriced_mask.sum()} expensive items")

        # ══════════════════════════════════════════════════════════════
        # 🔴 DEEP ATTRIBUTE LOGIC
        # ══════════════════════════════════════════════════════════════
        if 'MOUNT_LOGIC' in logic_key:
            # Exclude Frame magnetic frames from regular mount slots (they're for FRAME_LOGIC only)
            pool = pool[~pool['Title'].fillna('').str.lower().str.contains('μαγνητικό πλαίσιο|magnetic frame', na=False, regex=True)]
            
            # Exclude Δαπέδου (floor) and Επιδαπέδια mounts from regular mount slots
            # (special use case — dorms/rentals — not surfaced by default per user spec)
            topo_col = pool.get('Τοποθέτηση ≡', pd.Series('', index=pool.index)).fillna('').astype(str).str.strip()
            pool = pool[~topo_col.isin(['Δαπέδου', 'Επιδαπέδια'])]
            
            if t_vesa and t_vesa not in ('nan', '', '0'):
                vesa_match = pool['Πρότυπο VESA'].fillna('').astype(str).str.contains(re.escape(t_vesa), na=False)
                pool.loc[vesa_match, 'Final_Score'] += 300000
            
            if t_weight > 0 and 'Μέγιστο Βάρος ≡' in pool.columns:
                try:
                    pool_limit = pool['Μέγιστο Βάρος ≡'].astype(str).str.extract(r'(\d+)')[0].astype(float)
                    safe_mask = (pool_limit >= t_weight) | pool_limit.isna()
                    pool = pool[safe_mask]
                except: pass

            # ── SIZE COMPATIBILITY FILTER ──
            # The Ιδανικό για ≡ field has buckets like "Τηλεοράσεις 45" - 54""; map the
            # trigger size to its bucket and require the mount to list it.
            if t_size > 0:
                if   t_size <= 29:  bucket = '29"'
                elif t_size <= 39:  bucket = '30" - 39"'
                elif t_size <= 44:  bucket = '40" - 44"'
                elif t_size <= 54:  bucket = '45" - 54"'
                elif t_size <= 64:  bucket = '55" - 64"'
                elif t_size <= 74:  bucket = '65" - 74"'
                else:               bucket = '75"'
                bucket_alt = bucket.replace(' - ', '- ')
                ideal_col = pool.get('Ιδανικό\xa0για ≡', pd.Series('', index=pool.index)).fillna('').astype(str)
                size_ok = ideal_col.str.contains(re.escape(bucket), na=False) | ideal_col.str.contains(re.escape(bucket_alt), na=False)
                if size_ok.sum() >= 3:
                    pool = pool[size_ok]
                    notes.append(f"Size filter (hard): kept mounts compatible with {bucket}")
                else:
                    pool.loc[~size_ok, 'Final_Score'] -= 500000
                    notes.append(f"Size filter (soft): penalized non-{bucket} mounts (only {size_ok.sum()} matches)")
            
            # ── PREMIUM-TIER MOUNT BOOST (Greek market reality: €40-€80 sweet spot) ──
            # Boost solid mid-tier mounts that real Greek buyers pick (Hama 220824, One For
            # All WM2251/WM2651, Meliconi Flatstyle, Vogel's TVM3403/3405). Avoid overpriced
            # Vogel's Elite / Sbox FS-305 which buyers balk at.
            if price_tier in ('premium', 'flagship'):
                title_l = pool['Title'].fillna('').str.lower()
                # Realistic premium mount keywords (€40-80 range)
                sweet_spot_kw = title_l.str.contains(
                    r'220824|wm2251|wm2651|wm2421|flatstyle|tvm 340|tvm340|220844|220809|220810',
                    regex=True, na=False
                )
                pool.loc[sweet_spot_kw, 'Final_Score'] += 200000
                # De-rank the cheapest €15-20 mounts (premium TV deserves a bit more)
                pool.loc[pool['_p'] < 22, 'Final_Score'] -= 100000
                notes.append(f"Premium mount boost: €40-80 sweet spot ({price_tier})")
            
            # ΔΙΑΧΩΡΙΣΜΟΣ ΣΤΑΘΕΡΗΣ / ΜΕ ΒΡΑΧΙΟΝΑ (Fixed vs Motion)
            is_fixed_mask = pool.get('Τύπος Βάσης', pd.Series(dtype=str)).fillna('').str.lower().str.contains('σταθερή|fixed', na=False)
            
            if logic_key == 'MOUNT_LOGIC_FIXED':
                pool.loc[is_fixed_mask, 'Final_Score'] += 400000
                notes.append("Forced Slot 1 to Fixed Mount (+400k)")
            elif logic_key == 'MOUNT_LOGIC_MOTION':
                pool.loc[~is_fixed_mask, 'Final_Score'] += 400000
                notes.append("Forced Alt Mount to Motion/Arm Mount (+400k)")

        elif logic_key == 'FRAME_LOGIC':
            # Slot 1 for Samsung The Frame triggers — Μαγνητικό Πλαίσιο instead of regular mount.
            frame_mask = pool['Title'].fillna('').str.lower().str.contains('μαγνητικό πλαίσιο', na=False)
            if frame_mask.any():
                pool = pool[frame_mask]
                notes.append("🖼️ The Frame → Μαγνητικό Πλαίσιο active")
                # Exact size match (e.g. 65" trigger → match "65\"" or "65''" in title)
                if t_inches:
                    size_pat = rf'\b{t_inches}["\']?'
                    inch_mask = pool['Title'].fillna('').str.contains(size_pat, regex=True, na=False)
                    if inch_mask.any():
                        pool.loc[inch_mask, 'Final_Score'] += 800000
                        notes.append(f"Exact size match: {t_inches}\" boosted")
                # Extract color from trigger title to color-coordinate when possible
                tt_l = tt.lower()
                color_kw = None
                for c_eng, gr in [('white','λευκό'), ('beige','μπεζ'), ('brown','καφέ'), ('terracotta','τερακότα'), ('gold','χρυσό')]:
                    if c_eng in tt_l or gr in tt_l:
                        color_kw = gr; break
                if color_kw:
                    color_mask = pool['Title'].fillna('').str.lower().str.contains(color_kw, na=False)
                    pool.loc[color_mask, 'Final_Score'] += 100000
                    notes.append(f"Color-matched frame: {color_kw}")
            else:
                pool = pool.head(0)  # No frames → empty slot

        elif logic_key in ('SOUND_LOGIC_TIER_BUDGET', 'SOUND_LOGIC_TIER_MID', 'SOUND_LOGIC_TIER_PREMIUM', 'SOUND_LOGIC_TIER_FLAGSHIP'):
            # Classify each soundbar by channel notation in title (e.g. "2.1", "5.1.2", "9.1.4")
            # 2.0 / 3.0           → Soundbar only (no sub)
            # 2.1 / 3.1           → Soundbar + Sub
            # 5.0 / 5.1 / 7.1     → Full set (with rear speakers)
            # X.Y.Z (any height)  → Premium full set with Atmos/upfiring
            title_col = pool['Title'].fillna('')
            chan = title_col.str.extract(r'\b(\d{1,2})\.(\d)(?:\.(\d))?\b')
            front  = pd.to_numeric(chan[0], errors='coerce').fillna(0)
            sub    = pd.to_numeric(chan[1], errors='coerce').fillna(0)
            height = pd.to_numeric(chan[2], errors='coerce').fillna(0)

            is_bar_only       = (sub == 0) & (front <= 3)
            is_bar_sub        = (sub >= 1) & (front <= 3) & (height == 0)
            is_full_set       = (front >= 4) & (height == 0)
            is_premium_atmos  = (height >= 1) | ((front >= 4) & (sub >= 1) & (height >= 1))

            # Per-tier price target windows (matching Greek market spec from Achilleas):
            # Budget   TV €250-€400  → Soundbar €70-€150  (basic 2.0/2.1)
            # Mid      TV €400-€900  → Soundbar €200-€350 (3.1.2/5.1 with sub, basic Atmos)
            # Premium  TV €900-€1800 → Soundbar €500-€900 (5.1.2/7.1.2 true surround Atmos)
            # Flagship TV >€1800     → Soundbar €1000+    (9.1.4/11.1.4 flagship Atmos)
            if logic_key == 'SOUND_LOGIC_TIER_BUDGET':
                target_lo, target_hi = 70, 150
                pool.loc[is_bar_sub, 'Final_Score'] += 250000
                pool.loc[is_bar_only, 'Final_Score'] += 200000
                pool.loc[is_full_set, 'Final_Score'] -= 200000   # too much for budget TV
                pool.loc[is_premium_atmos, 'Final_Score'] -= 400000
                notes.append(f"Budget TV → cheap 2.0/2.1 soundbar (€{target_lo}-{target_hi})")
            elif logic_key == 'SOUND_LOGIC_TIER_MID':
                target_lo, target_hi = 200, 350
                pool.loc[is_bar_sub, 'Final_Score'] += 200000
                pool.loc[is_full_set, 'Final_Score'] += 250000
                pool.loc[is_premium_atmos & (pool['_p'] <= target_hi + 50), 'Final_Score'] += 200000
                pool.loc[is_premium_atmos & (pool['_p'] > target_hi + 100), 'Final_Score'] -= 200000
                pool.loc[is_bar_only, 'Final_Score'] -= 100000
                notes.append(f"Mid TV → Soundbar+Sub or basic Atmos (€{target_lo}-{target_hi})")
            elif logic_key == 'SOUND_LOGIC_TIER_PREMIUM':
                target_lo, target_hi = 500, 900
                pool.loc[is_premium_atmos, 'Final_Score'] += 400000
                pool.loc[is_full_set, 'Final_Score'] += 200000
                pool.loc[is_bar_sub, 'Final_Score'] -= 100000
                pool.loc[is_bar_only, 'Final_Score'] -= 300000
                notes.append(f"Premium TV → True surround Atmos (€{target_lo}-{target_hi})")
            else:  # SOUND_LOGIC_TIER_FLAGSHIP
                target_lo, target_hi = 1000, 3000
                pool.loc[is_premium_atmos, 'Final_Score'] += 500000
                pool.loc[is_full_set, 'Final_Score'] -= 100000
                pool.loc[is_bar_sub, 'Final_Score'] -= 200000
                pool.loc[is_bar_only, 'Final_Score'] -= 400000
                notes.append(f"Flagship TV → Top-tier Atmos (€{target_lo}+)")

            # Strong boost for soundbars in the target price window — this is the key fix:
            # ensures we don't show a €350 soundbar on a €1700 TV.
            in_window = (pool['_p'] >= target_lo) & (pool['_p'] <= target_hi)
            pool.loc[in_window, 'Final_Score'] += 350000
            # Soft penalty for those well below the window (under-recommendation)
            pool.loc[pool['_p'] < target_lo * 0.7, 'Final_Score'] -= 200000

            # Brand match boost — kept across all tiers (Q-Symphony, LG WOW Sync, etc.)
            # Greek retailers heavily push brand-matched bundles. Boosted to +300k so brand
            # match wins over close-window competitors when both tier and channel config match.
            if tb:
                brand_match = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                pool.loc[brand_match, 'Final_Score'] += 300000
                notes.append(f"Brand Match ({tb}) boosted (+300k)")

            # Cinema TV → still prefer Atmos/DTS within the chosen tier
            if is_cinema_tv:
                atmos_tech = pool.get('Τεχνολογίες ≡', pd.Series(dtype=str)).fillna('').str.lower().str.contains('atmos|dts')
                pool.loc[atmos_tech, 'Final_Score'] += 80000

        elif logic_key == 'SOUND_LOGIC_BUDGET':
            # Slot-10 closer: budget soundbar, no brand boost (don't duplicate slot 2 logic).
            # Cap at ~30% of TV price to keep AOV sane.
            cap = max(80.0, tprice * 0.30)
            pool.loc[pool['_p'] <= cap, 'Final_Score'] += 200000
            pool.loc[pool['_p'] > cap, 'Final_Score'] -= 300000
            notes.append(f"Budget soundbar closer (cap €{cap:.0f})")

        elif logic_key == 'HDMI_LOGIC':
            # Tier the cable to the TV. Premium/large/OLED/gaming TVs need HDMI 2.1.
            # 4K mid-range needs HDMI 2.0+. Cheap HD-Ready can use 1.4.
            ver_col = pool.get('Έκδοση ≡', pd.Series('', index=pool.index)).fillna('').astype(str)
            title_col = pool['Title'].fillna('')
            tt_lower = tt.lower()

            needs_21 = (
                is_gaming_tv
                or 'oled' in tt_lower
                or price_tier in ('premium', 'flagship')
                or t_size >= 65
            )
            needs_20 = price_tier == 'mid'  # mid-tier 4K TVs

            is_21 = ver_col.str.contains('2.1', na=False) | title_col.str.contains('2.1', na=False)
            is_20 = ver_col.str.contains('2.0', na=False) | title_col.str.contains(r'\b2\.0\b', regex=True, na=False)
            is_14 = ver_col.str.contains('1.4', na=False) | ver_col.str.contains('1.3', na=False) | ver_col.str.contains('1.2', na=False)

            if needs_21:
                pool.loc[is_21, 'Final_Score'] += 400000
                pool.loc[is_20, 'Final_Score'] += 50000
                pool.loc[is_14, 'Final_Score'] -= 200000
                notes.append("Premium TV → forced HDMI 2.1")
            elif needs_20:
                pool.loc[is_21, 'Final_Score'] += 250000
                pool.loc[is_20, 'Final_Score'] += 200000
                pool.loc[is_14, 'Final_Score'] -= 100000
                notes.append("4K TV → boosted HDMI 2.0+")
            # else: budget HD-Ready TV — no HDMI version boost; sales/availability decide

        elif logic_key == 'HDMI_LOGIC_PREMIUM_SPARE':
            # Slot-10 closer for premium TVs: force HDMI 2.1, prefer a different
            # length than slot 7's pick to give the bundle real variety.
            ver_col = pool.get('Έκδοση ≡', pd.Series('', index=pool.index)).fillna('').astype(str)
            title_col = pool['Title'].fillna('')
            is_21 = ver_col.str.contains('2.1', na=False) | title_col.str.contains('2.1', na=False)
            pool.loc[is_21, 'Final_Score'] += 400000
            pool.loc[~is_21, 'Final_Score'] -= 200000
            # Slight nudge toward longer cables since the user already has a short one
            is_long = title_col.str.contains(r'\b(?:3m|5m|3\.0m|5\.0m)\b', regex=True, na=False)
            pool.loc[is_long & is_21, 'Final_Score'] += 50000
            notes.append("Premium spare → HDMI 2.1, length-diversified")

        elif logic_key == 'REMOTE_LOGIC_PREMIUM_LG':
            magic_mask = pool['Title'].fillna('').str.lower().str.contains('magic remote', na=False)
            if magic_mask.any():
                pool = pool[magic_mask]
                notes.append("LG Premium TV -> Forced Magic Remote Match")
            else:
                pool = pool.head(0) # Hide slot if Magic Remote is completely out of stock
                
        elif logic_key == 'REMOTE_LOGIC_CHEAP':
            generic_mask = pool['Title'].fillna('').str.lower().str.contains('universal|one for all|superior|αντικατάστασης|συμβατό|generic', regex=True, na=False)
            pool.loc[generic_mask, 'Final_Score'] += 300000
            
            if tb:
                brand_match = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb
                pool.loc[brand_match, 'Final_Score'] += 150000
            
            # Απαγόρευση του Magic Remote στις φθηνές
            magic_mask = pool['Title'].fillna('').str.lower().str.contains('magic remote', na=False)
            pool.loc[magic_mask, 'Final_Score'] -= 1000000
            notes.append("Cheap TV -> Boosted Generic/Universal Replacements, Banned Magic Remote")

        elif logic_key == 'ANTENNA_LOGIC':
            # Stop the same Philips 24dB from auto-winning every TV trigger via sales tiebreaker.
            # Boost mid-gain DVB-T2 antennas (better technical fit), penalize the entry-level
            # 24dB unit, slightly nudge by TV tier (more expensive TV → better antenna).
            title_l = pool['Title'].fillna('').str.lower()
            is_dvbt2_strong = title_l.str.contains(r'dvb.?t2|pro\s?50|221083|221082', regex=True, na=False)
            is_low_gain     = title_l.str.contains(r'24\s?db', regex=True, na=False)
            is_high_gain    = title_l.str.contains(r'(?:38|44|48|52)\s?db', regex=True, na=False)

            pool.loc[is_dvbt2_strong, 'Final_Score'] += 200000
            pool.loc[is_high_gain, 'Final_Score'] += 100000
            pool.loc[is_low_gain, 'Final_Score'] -= 150000

            # Tier-based extra boost so flagship TVs lean toward stronger antennas
            if price_tier in ('premium', 'flagship'):
                pool.loc[is_high_gain | is_dvbt2_strong, 'Final_Score'] += 80000

            notes.append(f"Antenna: boosted DVB-T2/high-gain, penalized 24dB ({price_tier} tier)")

        # ── Selection ──
        pool = pool.sort_values('Final_Score', ascending=False)
        if not pool.empty:
            chosen = pool.iloc[0]
            
            rc = chosen.copy()
            rc['Assigned_Slot'] = current_slot
            rc['Slot_Role'] = role
            rc['Marketing_Copy'] = TV_MARKETING_COPY.get(role, "Ιδανική επιλογή.")
            rc['Item_Rank'] = 1
            all_recs.append(rc)
            used_materials.add(chosen['Material'])
            notes.append(f"✅ {str(chosen.get('Title',''))[:60]}")
            slot_notes[current_slot] = notes
            diag.append((f"Slot {current_slot} ({role})", 1, f"Score: {chosen['Final_Score']:.0f}"))
            
            current_slot += 1

    recs_df = pd.DataFrame(all_recs) if all_recs else pd.DataFrame()
    if not recs_df.empty: recs_df['Draft_Score'] = recs_df['Assigned_Slot']
    return recs_df, diag, slot_notes, recs_df


    
# ═════════════════════════════════════════════════════════════
# 🟢 PROJECTORS ENGINE — REWRITE
# ═════════════════════════════════════════════════════════════
# Slot order (per Achilleas' spec):
#   1. ΤΣΑΝΤΕΣ PROJECTOR              (brand-matched bag)
#   2. HDMI                            (cable, version-tiered)
#   3. ΟΘΟΝΕΣ PROJECTOR or ΒΑΣΕΙΣ      (screen, OR stand for XGIMI/AURZEN)
#   4. ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ              (portable speaker, price-tiered)
#   5. ΑΛΚΑΛΙΚΕΣ                       (batteries — skipped if Samsung Freestyle)
#   6. SURGE PROTECTORS                (price-tiered)
#   7. ΛΑΜΠΕΣ + ΔΙΑΦΟΡΑ ΑΞΕΣΟΥΑΡ      (lamp/accessory, brand-specific)
#   8. MOUSE WIRELESS
#   9. KEYBOARDS WIRELESS
#  10. PARTY SPEAKERS
#
# Brand overrides:
#   • SAMSUNG Freestyle: Slot 1 = Freestyle Case, Slot 7 = Freestyle Battery Base
#   • XGIMI: Slot 1 = XGIMI bag (model-matched), Slot 3 = XGIMI Stand, Slot 7 = XGIMI accessory
#   • AURZEN: Slot 1 = AURZEN CasePlay, Slot 3 = AURZEN MagPlay/PowerPlay, Slot 7 = AURZEN accessory
#
def run_projectors_engine(trigger, df_products, df_history):
    diag = []
    slot_notes = {}
    all_recs = []

    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    tt_l = tt.lower()
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tmodel = str(trigger.get('Μοντέλο', '')).strip()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))

    # Trigger attributes for deep filtering
    tusage = str(trigger.get('Προτεινόμενη χρήση', '')).lower()
    ttech  = str(trigger.get('Τεχνολογία οθόνης', '')).lower()
    tres   = str(trigger.get('Ανάλυση', '')).lower()
    tdyn   = str(trigger.get('Δυνατότητες', '')).lower()

    is_cinema    = 'home cinema' in tusage or 'gaming' in tusage
    is_pro       = 'επαγγελματική' in tusage
    is_class     = 'classroom' in tusage
    is_portable  = 'φορητός' in tdyn or 'φορητός' in tt_l or 'mogo' in tt_l or 'freestyle' in tt_l or 'aurzen' in tt_l
    is_laser_led = 'laser' in ttech or 'led' in ttech
    is_4k        = '4k' in tres or 'uhd' in tres

    # Brand-specific flags
    is_samsung_freestyle = tb == 'SAMSUNG' and 'freestyle' in tt_l
    is_xgimi             = tb == 'XGIMI'
    is_aurzen            = tb == 'AURZEN'

    # ── Price tier (projector market — tighter than TVs) ──
    # budget : ≤€200    → cheap accessories, no fancy bag/stand
    # mid    : €200-600 → mid speaker, brand bag if available
    # premium: >€600    → premium speaker, brand-matched accessories
    if tprice <= 200:
        ptier = 'budget'
    elif tprice <= 600:
        ptier = 'mid'
    else:
        ptier = 'premium'
   
    # Per-slot price caps for projectors: (pct_of_trigger, hard_max_eur)
    PROJ_CAPS = {
        'budget':  {'bag': (0.40, 50),  'cable': (0.15, 25), 'screen': (0.40, 80),  'speaker': (0.30, 50),  'battery': (0.10, 12), 'surge': (0.15, 25), 'lamp': (0.50, 100), 'mouse': (0.15, 30), 'keyboard': (0.30, 60), 'party': (0.50, 100)},
        'mid':     {'bag': (0.20, 90),  'cable': (0.08, 35), 'screen': (0.30, 150), 'speaker': (0.30, 200), 'battery': (0.05, 15), 'surge': (0.08, 35), 'lamp': (0.40, 200), 'mouse': (0.10, 50), 'keyboard': (0.20, 100), 'party': (0.40, 250)},
        'premium': {'bag': (0.18, 150), 'cable': (0.06, 60), 'screen': (0.30, 400), 'speaker': (0.45, 500), 'battery': (0.04, 20), 'surge': (0.05, 60), 'lamp': (0.40, 400), 'mouse': (0.08, 80), 'keyboard': (0.18, 150), 'party': (0.40, 600)},
    }
    PROJ_FLOORS = {'bag': 30, 'cable': 8, 'screen': 30, 'speaker': 25, 'battery': 5, 'surge': 10, 'lamp': 15, 'mouse': 10, 'keyboard': 25, 'party': 60}

    diag.append((
        "0. Trigger Context",
        f"Brand={tb}, Price=€{tprice:.0f}, Tier={ptier}",
        f"Tech={ttech}, Cinema={is_cinema}, Portable={is_portable}, Freestyle={is_samsung_freestyle}, XGIMI={is_xgimi}, AURZEN={is_aurzen}"
    ))

    # ── Build slot list ──
    # Default slot order
    slots = [
        (1,  'Τσάντα Μεταφοράς',    ['ΤΣΑΝΤΕΣ PROJECTOR'],                              'BAG_LOGIC',     'bag'),
        (2,  'Καλώδιο Σύνδεσης',    ['HDMI'],                                            'CABLE_LOGIC',   'cable'),
        (3,  'Οθόνη Προβολής',      ['ΟΘΟΝΕΣ PROJECTOR'],                                'CANVAS_LOGIC',  'screen'),
        (4,  'Ηχείο',               ['ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ'],                              'AUDIO_LOGIC',   'speaker'),
        (5,  'Μπαταρίες',           ['ΑΛΚΑΛΙΚΕΣ'],                                       'BATTERY_LOGIC', 'battery'),
        (6,  'Προστασία Τάσης',     ['SURGE PROTECTORS'],                                'POWER_LOGIC',   'surge'),
        (7,  'Αξεσουάρ Συσκευής',   ['ΛΑΜΠΕΣ PROJECTOR', 'ΔΙΑΦΟΡΑ ΑΞΕΣΟΥΑΡ PROJECTOR'],   'ACCESSORY_LOGIC','lamp'),
        (8,  'Ποντίκι',             ['MOUSE WIRELESS'],                                  'INPUT_LOGIC',   'mouse'),
        (9,  'Πληκτρολόγιο',        ['KEYBOARDS WIRELESS'],                              'KEYBOARD_LOGIC','keyboard'),
        (10, 'Party Ήχος',          ['PARTY SPEAKERS'],                                  'GENERIC',       'party'),
    ]

    # ── Brand-specific overrides ──
    # XGIMI/AURZEN: surface BOTH brand items in the FIRST 2 SLOTS (Bag at 1, Stand at 2),
    # demote HDMI cable to slot 3, drop the screen slot (the stand replaces it),
    # and add a SECOND brand accessory at slot 7.
    if is_xgimi or is_aurzen:
        new_slots = [
            (1,  'Τσάντα Μεταφοράς',  ['ΤΣΑΝΤΕΣ PROJECTOR'],                                                        'BAG_LOGIC',             'bag'),
            (2,  'Βάση Στήριξης',     ['ΒΑΣΕΙΣ PROJECTOR'],                                                          'STAND_LOGIC',           'screen'),
            (3,  'Καλώδιο Σύνδεσης',  ['HDMI'],                                                                       'CABLE_LOGIC',           'cable'),
            (4,  'Ηχείο',             ['ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ'],                                                         'AUDIO_LOGIC',           'speaker'),
            (5,  'Μπαταρίες',         ['ΑΛΚΑΛΙΚΕΣ'],                                                                  'BATTERY_LOGIC',         'battery'),
            (6,  'Προστασία Τάσης',   ['SURGE PROTECTORS'],                                                           'POWER_LOGIC',           'surge'),
            (7,  'Brand Accessory',   ['ΒΑΣΕΙΣ PROJECTOR', 'ΤΣΑΝΤΕΣ PROJECTOR', 'ΔΙΑΦΟΡΑ ΑΞΕΣΟΥΑΡ PROJECTOR'],         'BRAND_ACCESSORY_LOGIC', 'lamp'),
            (8,  'Ποντίκι',           ['MOUSE WIRELESS'],                                                             'INPUT_LOGIC',           'mouse'),
            (9,  'Πληκτρολόγιο',      ['KEYBOARDS WIRELESS'],                                                         'KEYBOARD_LOGIC',        'keyboard'),
            (10, 'Party Ήχος',        ['PARTY SPEAKERS'],                                                             'GENERIC',               'party'),
        ]
        slots = new_slots
    
    # Samsung Freestyle: surface BOTH official Samsung accessories in the FIRST 2 SLOTS
    # (Case in slot 1, Battery in slot 2). Drop the standard batteries slot and the
    # generic accessory slot since Samsung's are now front-loaded.
    if is_samsung_freestyle:
        # Pull Battery up to slot 2 (replacing HDMI cable in slot 2)
        # New order: Bag(1), Battery(2), Cable(3), Screen(4), Speaker(5), Surge(6),
        #            Mouse(7), Keyboard(8), Party(9)
        new_slots = [
            (1, 'Τσάντα Μεταφοράς', ['ΤΣΑΝΤΕΣ PROJECTOR'],   'BAG_LOGIC',         'bag'),
            (2, 'Μπαταρία Συσκευής', ['ΛΑΜΠΕΣ PROJECTOR'],    'ACCESSORY_LOGIC',   'lamp'),
            (3, 'Καλώδιο Σύνδεσης',  ['HDMI'],                'CABLE_LOGIC',       'cable'),
            (4, 'Οθόνη Προβολής',    ['ΟΘΟΝΕΣ PROJECTOR'],    'CANVAS_LOGIC',      'screen'),
            (5, 'Ηχείο',             ['ΗΧΕΙΑ ΦΟΡΗΤΟΥ ΗΧΟΥ'],  'AUDIO_LOGIC',       'speaker'),
            (6, 'Προστασία Τάσης',   ['SURGE PROTECTORS'],    'POWER_LOGIC',       'surge'),
            (7, 'Ποντίκι',           ['MOUSE WIRELESS'],      'INPUT_LOGIC',       'mouse'),
            (8, 'Πληκτρολόγιο',      ['KEYBOARDS WIRELESS'],  'KEYBOARD_LOGIC',    'keyboard'),
            (9, 'Party Ήχος',        ['PARTY SPEAKERS'],      'GENERIC',           'party'),
        ]
        slots = new_slots

    # Base candidate pool
    c = df_products[df_products['Material'] != tm].copy()
    if 'Sum of Sales' in c.columns:
        c['Sales_Tiebreaker'] = pd.to_numeric(c['Sum of Sales'], errors='coerce').fillna(0)
    else:
        c['Sales_Tiebreaker'] = 0
    c['_p'] = pd.to_numeric(c['LIST PRICE'], errors='coerce').fillna(0)

    used_materials = {tm}
    used_hierarchies_count = {}

    for slot_num, role, hierarchies, logic_key, cap_key in slots:
        notes = [f"Logic: {logic_key}"]

        # Pool filtering
        hier_upper = [h.upper().strip() for h in hierarchies]
        pool = c[c['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin(hier_upper)].copy()
        pool = pool[~pool['Material'].isin(used_materials)]

        # Drop blank-title placeholder rows (catalog has some Material rows with NaN Title)
        pool = pool[pool['Title'].notna() & (pool['Title'].astype(str).str.strip() != '')]

        if pool.empty:
            slot_notes[slot_num] = notes + ["❌ Empty hierarchy"]
            diag.append((f"Slot {slot_num} ({role})", 0, "Empty"))
            continue

        # Base score: availability + sales tiebreaker
        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
        pool['Final_Score'] += pool['Sales_Tiebreaker'].fillna(0) * 0.1

        # ── Price cap (soft penalty, like the TV engine) ──
        # EXCEPTION: brand-locked items (Samsung/XGIMI/AURZEN matching the trigger brand)
        # are exempt — we always want to surface the official accessory even if it's
        # over the generic cap (e.g. XGIMI PowerBase €135 on a €443 MoGo).
        if cap_key in PROJ_CAPS[ptier]:
            pct, hard_max = PROJ_CAPS[ptier][cap_key]
            floor = PROJ_FLOORS[cap_key]
            cap_eur = max(float(floor), min(tprice * pct, float(hard_max)))
            overpriced = pool['_p'] > cap_eur

            # Build brand-exemption mask: items from the trigger's brand are exempt
            # for slots that have brand-lock logic.
            mfr_col = pool['Κατασκευαστής'].fillna('').str.upper().str.strip()
            title_l_for_exempt = pool['Title'].fillna('').str.lower()
            brand_exempt = pd.Series(False, index=pool.index)
            if logic_key in ('BAG_LOGIC', 'STAND_LOGIC', 'ACCESSORY_LOGIC', 'BRAND_ACCESSORY_LOGIC'):
                if is_samsung_freestyle:
                    brand_exempt = title_l_for_exempt.str.contains('freestyle', na=False)
                elif is_xgimi:
                    brand_exempt = mfr_col == tb
                elif is_aurzen:
                    brand_exempt = mfr_col == tb

            penalize = overpriced & ~brand_exempt
            pool.loc[penalize, 'Final_Score'] -= 800000
            if penalize.any():
                notes.append(f"Price Cap (€{cap_eur:.0f}, {ptier}/{cap_key}): {penalize.sum()} penalized")
            if (overpriced & brand_exempt).any():
                notes.append(f"Brand exemption: {(overpriced & brand_exempt).sum()} brand items kept above cap")

        # ══════════════════════════════════════════════════════════════
        # PER-SLOT LOGIC
        # ══════════════════════════════════════════════════════════════

        if logic_key == 'BAG_LOGIC':
            title_l = pool['Title'].fillna('').str.lower()
            if is_samsung_freestyle:
                m = title_l.str.contains('freestyle', na=False)
                pool.loc[m, 'Final_Score'] += 800000
                pool = pool[m]  # hard filter — only Freestyle bag
                notes.append("🟢 Samsung Freestyle bag forced")
            elif is_xgimi:
                m_xgimi = title_l.str.contains('xgimi', na=False)
                pool = pool[m_xgimi]  # hard filter to XGIMI
                title_l = pool['Title'].fillna('').str.lower()
                pool.loc[:, 'Final_Score'] += 600000
                # Model-specific match (e.g., "MoGo 3 Pro" → bag with that model)
                if tmodel and not pool.empty:
                    m_model = title_l.str.contains(re.escape(tmodel.lower()), na=False)
                    pool.loc[m_model, 'Final_Score'] += 400000
                    if m_model.any():
                        notes.append(f"🟢 XGIMI bag exact model match: {tmodel}")
                    else:
                        notes.append("🟡 XGIMI bag (no exact model match)")
            elif is_aurzen:
                m_aur = title_l.str.contains('aurzen|caseplay', na=False, regex=True)
                pool = pool[m_aur]  # hard filter to AURZEN
                pool.loc[:, 'Final_Score'] += 600000
                notes.append("🟢 AURZEN bag forced")
            else:
                # Generic projector — no brand-specific bag fits. Skip this slot to avoid
                # recommending an XGIMI MoGo bag for a Philips NeoPix.
                pool = pool.head(0)
                notes.append("Generic projector — no brand bag, slot skipped")

        elif logic_key == 'CABLE_LOGIC':
            title_l = pool['Title'].fillna('').str.lower()
            ver_col = pool.get('Έκδοση ≡', pd.Series('', index=pool.index)).fillna('').astype(str)

            if is_class:
                # Classroom: VGA cables aren't in this catalog (HDMI hierarchy only),
                # so we just keep HDMI but don't penalize older versions.
                notes.append("Classroom: HDMI primary, no VGA in catalog")
            
            if is_4k or ptier == 'premium':
                is_21 = ver_col.str.contains('2.1', na=False) | title_l.str.contains('2.1', na=False)
                pool.loc[is_21, 'Final_Score'] += 200000
                notes.append("Boosted HDMI 2.1 (4K/premium)")
            elif ptier == 'mid':
                is_20p = ver_col.str.contains('2.0|2.1', na=False, regex=True) | title_l.str.contains(r'2\.0|2\.1', na=False, regex=True)
                pool.loc[is_20p, 'Final_Score'] += 120000
                notes.append("Boosted HDMI 2.0+")
            
            if is_cinema:
                if 'Μήκος' in pool.columns:
                    long_cab = pool['Μήκος'].fillna('').astype(str).str.contains(r'5|10|15|20', regex=True)
                    pool.loc[long_cab, 'Final_Score'] += 50000
                    notes.append("Cinema: boosted longer cables")

        elif logic_key == 'CANVAS_LOGIC':
            # Generic screen — ΟΘΟΝΕΣ PROJECTOR. Boost 100"+ for cinema usage.
            title_l = pool['Title'].fillna('').str.lower()
            if is_cinema:
                large = title_l.str.contains(r'100|108|110|112|120|135', regex=True, na=False)
                pool.loc[large, 'Final_Score'] += 150000
                notes.append("Cinema: boosted ≥100\" screens")
            else:
                # Smaller portable projectors → boost smaller affordable screens
                small = title_l.str.contains(r'\b60|\b80|\b84', regex=True, na=False)
                pool.loc[small, 'Final_Score'] += 80000
                notes.append("Boosted compact screens")

        elif logic_key == 'STAND_LOGIC':
            # XGIMI / AURZEN brand-locked stand. Match brand first, then model if possible.
            title_l = pool['Title'].fillna('').str.lower()
            mfr_col = pool['Κατασκευαστής'].fillna('').str.upper().str.strip()
            
            if is_xgimi:
                m_xgimi = mfr_col == 'XGIMI'
                pool.loc[m_xgimi, 'Final_Score'] += 700000
                # PowerBase MoGo 3 Pro → forced exact match if model matches
                if tmodel and 'mogo' in tmodel.lower():
                    m_mogo = title_l.str.contains('mogo', na=False)
                    pool.loc[m_mogo, 'Final_Score'] += 500000
                    notes.append("🟢 XGIMI MoGo PowerBase forced")
                else:
                    notes.append("🟢 XGIMI stand forced")
            elif is_aurzen:
                m_aur = mfr_col == 'AURZEN'
                pool.loc[m_aur, 'Final_Score'] += 700000
                notes.append("🟢 AURZEN stand forced")

        elif logic_key == 'AUDIO_LOGIC':
            # Tier-aware target window boost για Projectors:
            # budget   → €20-€50 sweet spot (JBL Go, Sony SRS-XB100)
            # mid      → €60-€150 (JBL Charge/Flip, Sony ULT FIELD 3)
            # premium  → €200-€450 (Marshall Stanmore, JBL Xtreme)
            title_l = pool['Title'].fillna('').str.lower()
            
            if ptier == 'budget':
                window_lo, window_hi = 20, 50
            elif ptier == 'mid':
                window_lo, window_hi = 60, 150
            else:  # premium
                window_lo, window_hi = 200, 450
            
            in_window = (pool['_p'] >= window_lo) & (pool['_p'] <= window_hi)
            pool.loc[in_window, 'Final_Score'] += 250000
            notes.append(f"Speaker target window €{window_lo}-€{window_hi} ({ptier})")
            
            if is_cinema and ptier in ('mid', 'premium'):
                premium_kw = title_l.str.contains(r'marshall|xtreme|ult field|partybox|stanmore', regex=True, na=False)
                pool.loc[premium_kw, 'Final_Score'] += 200000
                notes.append("Cinema: boosted premium room speakers")
            
            if is_portable:
                compact_kw = title_l.str.contains(r'\bgo\b|flip|charge|grip|srs|hifuture', regex=True, na=False)
                pool.loc[compact_kw, 'Final_Score'] += 80000
                notes.append("Portable: compact speakers boosted")
                

        elif logic_key == 'BATTERY_LOGIC':
            pass

        elif logic_key == 'POWER_LOGIC':
            pass

        elif logic_key == 'ACCESSORY_LOGIC':
            # Slot 7 (or slot 2 for Samsung Freestyle): brand-specific accessory.
            title_l = pool['Title'].fillna('').str.lower()
            mfr_col = pool['Κατασκευαστής'].fillna('').str.upper().str.strip()
            
            if is_samsung_freestyle:
                # ΛΑΜΠΕΣ PROJECTOR has the Freestyle Battery (mislabeled as a lamp)
                m_fr = title_l.str.contains('freestyle', na=False)
                pool.loc[m_fr, 'Final_Score'] += 800000
                pool = pool[m_fr]  # hard filter — only Samsung Freestyle items
                notes.append("🟢 Samsung Freestyle Battery forced (hard filter)")
            else:
                # Generic projector — exclude Samsung Freestyle (irrelevant), boost tripod
                pool = pool[~title_l.str.contains('freestyle', na=False)]
                if pool.empty:
                    notes.append("Generic projector — no relevant accessory")
                else:
                    m_acc = pool['Hierarchy'].fillna('').str.upper().str.contains('ΑΞΕΣΟΥΑΡ', na=False)
                    pool.loc[m_acc, 'Final_Score'] += 200000
                    notes.append("Generic: tripod/accessory boosted")

        elif logic_key == 'BRAND_ACCESSORY_LOGIC':
            # XGIMI/AURZEN slot 7: prefer a SECOND item from the brand ecosystem
            # (e.g. 2nd stand or alt-color bag), not already used in earlier slots.
            title_l = pool['Title'].fillna('').str.lower()
            mfr_col = pool['Κατασκευαστής'].fillna('').str.upper().str.strip()
            
            # Hard-exclude irrelevant items (Samsung Freestyle, ultra-expensive UST screen)
            pool = pool[~title_l.str.contains('freestyle', na=False)]
            
            if is_xgimi:
                m_brand = mfr_col == 'XGIMI'
                pool.loc[m_brand, 'Final_Score'] += 700000
                # Model-specific match (e.g. MoGo bag for MoGo trigger)
                if tmodel:
                    m_model = title_l.str.contains(re.escape(tmodel.lower()), na=False)
                    pool.loc[m_model, 'Final_Score'] += 300000
                notes.append("🟢 XGIMI 2nd accessory forced")
            elif is_aurzen:
                m_brand = mfr_col == 'AURZEN'
                pool.loc[m_brand, 'Final_Score'] += 700000
                if tmodel:
                    m_model = title_l.str.contains(re.escape(tmodel.lower()), na=False)
                    pool.loc[m_model, 'Final_Score'] += 300000
                notes.append("🟢 AURZEN 2nd accessory forced")

        elif logic_key == 'INPUT_LOGIC':
            # Mouse — tier-aware target window
            #   budget   → €10-€20 (M171/M220)
            #   mid      → €15-€40 (M280, MX Anywhere entry)
            #   premium  → €40-€90 (MX Master, MX Anywhere 3)
            title_l = pool['Title'].fillna('').str.lower()
            if ptier == 'budget':
                window_lo, window_hi = 8, 20
            elif ptier == 'mid':
                window_lo, window_hi = 12, 40
            else:
                window_lo, window_hi = 35, 90
            in_window = (pool['_p'] >= window_lo) & (pool['_p'] <= window_hi)
            pool.loc[in_window, 'Final_Score'] += 200000
            notes.append(f"Mouse target window €{window_lo}-€{window_hi} ({ptier})")
            
            compact = title_l.str.contains(r'silent|compact|portable|m171|m220|m280|anywhere', regex=True, na=False)
            pool.loc[compact, 'Final_Score'] += 80000

        elif logic_key == 'GENERIC':
            # Party Speakers — filter out non-speakers + tier window.
            #   budget  → €30-€90  (cheap karaoke kid speakers)
            #   mid     → €80-€250 (Crystal Audio PRT, JBL Partybox 110)
            #   premium → €250-€600 (JBL Partybox 320/710)
            title_l = pool['Title'].fillna('').str.lower()
            non_speaker = title_l.str.contains(r'μπαταρία|powerbank|battery|charger', regex=True, na=False)
            pool = pool[~non_speaker]
            if pool.empty:
                notes.append("No real party speakers after filter")
            else:
                if ptier == 'budget':
                    window_lo, window_hi = 30, 90
                elif ptier == 'mid':
                    window_lo, window_hi = 80, 250
                else:
                    window_lo, window_hi = 250, 600
                in_window = (pool['_p'] >= window_lo) & (pool['_p'] <= window_hi)
                pool.loc[in_window, 'Final_Score'] += 250000
                notes.append(f"Party target window €{window_lo}-€{window_hi} ({ptier})")

        elif logic_key == 'KEYBOARD_LOGIC':
            # Keyboard — tier-aware target window.
            #   budget  → €25-€60 (Logitech K380, Pebble Keys 2)
            #   mid     → €40-€100 (K580, MX Keys Mini)
            #   premium → €90-€200 (MX Keys S, Craft)
            title_l = pool['Title'].fillna('').str.lower()
            if ptier == 'budget':
                window_lo, window_hi = 20, 60
            elif ptier == 'mid':
                window_lo, window_hi = 35, 100
            else:
                window_lo, window_hi = 80, 200
            in_window = (pool['_p'] >= window_lo) & (pool['_p'] <= window_hi)
            pool.loc[in_window, 'Final_Score'] += 200000
            notes.append(f"Keyboard target window €{window_lo}-€{window_hi} ({ptier})")
            
            compact = title_l.str.contains(r'compact|portable|multi.?device|k380|k480|pebble|mx keys', regex=True, na=False)
            pool.loc[compact, 'Final_Score'] += 80000

        # ── Selection (with hierarchy cap of 2) ──
        pool = pool.sort_values('Final_Score', ascending=False)
        chosen = None
        for _, row in pool.iterrows():
            h = row['Hierarchy']
            if used_hierarchies_count.get(h, 0) < 2:
                chosen = row
                break

        if chosen is None:
            slot_notes[slot_num] = notes + ["❌ Hierarchy cap blocked"]
            diag.append((f"Slot {slot_num} ({role})", 0, "Hier cap"))
            continue

        rc = chosen.copy()
        rc['Assigned_Slot'] = slot_num
        rc['Slot_Role']     = role
        rc['Marketing_Copy']= "Απαραίτητος εξοπλισμός για την προβολή σας."
        rc['Item_Rank']     = 1
        all_recs.append(rc)
        used_materials.add(chosen['Material'])
        used_hierarchies_count[chosen['Hierarchy']] = used_hierarchies_count.get(chosen['Hierarchy'], 0) + 1
        notes.append(f"✅ {str(chosen.get('Title', ''))[:60]}")
        slot_notes[slot_num] = notes
        diag.append((f"Slot {slot_num} ({role})", 1, f"Score: {chosen.get('Final_Score', 0):.0f}"))

    diag.append(("TOTAL", len(all_recs), f"out of {len(slots)}"))

    if all_recs:
        recs_df = pd.DataFrame(all_recs)
        recs_df['Draft_Score'] = recs_df['Assigned_Slot']
        return recs_df, diag, slot_notes, recs_df
    return pd.DataFrame(), diag, slot_notes, pd.DataFrame()


# ═══════════════════════════════════════════════════════════════
# 🟢 VINYL & TURNTABLES ENGINE
# ═══════════════════════════════════════════════════════════════

def run_vinyl_engine(trigger, df_products, df_peripherals, df_music, df_history):
    diag, slot_notes, all_recs = [], {}, []
    
    tm = trigger['Material']
    tt = str(trigger.get('Title', ''))
    tb = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    tprice = parse_euro_price(trigger.get('LIST PRICE', 0))
    ttier = get_vinyl_tier(tprice)
    
    # ── DEEP FILTER EXTRACTION ──
    _tt_lower = tt.lower()
    
    internal_spk_raw = str(trigger.get('Ενσωματωμένα Ηχεία', '')).lower()
    has_spk = ("διαθέτει" in internal_spk_raw and "δε διαθέτει" not in internal_spk_raw) or ("ενσωματωμένα ηχεία" in _tt_lower)
    no_spk = ("δε διαθέτει" in internal_spk_raw) or not has_spk
    
    # DATA FIX: Τα πικάπ της Audio-Technica ΔΕΝ έχουν ενσωματωμένα ηχεία.
    # Αγνοούμε τυχόν λάθος του Excel για να λειτουργήσει σωστά η μηχανή.
    if tb == 'AUDIO-TECHNICA':
        has_spk = False
        no_spk = True
        
    extra_char = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    is_suitcase = "βαλιτσάκι" in extra_char or "βαλιτσάκι" in _tt_lower
    
    has_preamp = "ενσωματωμένος προενισχυτής" in extra_char or "προενισχυτ" in _tt_lower
    is_usb_extra = "usb" in extra_char
    
    conn = str(trigger.get('Συνδεσιμότητα', '')).lower()
    is_bt = "bluetooth" in conn or "bluetooth" in _tt_lower
    is_usb_conn = "usb" in conn or "usb" in _tt_lower
    is_rca = "rca" in conn

    diag.append(("0. Trigger", f"Brand={tb}, Price=€{tprice:.0f} ({ttier})", f"Spk={has_spk}, PreAmp={has_preamp}, BT={is_bt}, USB={is_usb_conn or is_usb_extra}"))

    # --- Data Prep ---
    c_prod_full = pd.concat([df_products, df_peripherals], ignore_index=True)
    c_prod = c_prod_full[c_prod_full['Material'] != tm].copy()
    
    c_music = df_music.copy() if not df_music.empty else pd.DataFrame()
    
    c_prod['Sales_30'] = pd.to_numeric(c_prod.get('Sum of Sales', 0), errors='coerce').fillna(0)
    c_prod['_p'] = c_prod['LIST PRICE'].apply(parse_euro_price)
    if not c_music.empty:
        c_music['Sales_30'] = pd.to_numeric(c_music.get('Sum of Sales', 0), errors='coerce').fillna(0)

    used_materials = {tm}

    for slot_num, role, hierarchies, logic_key in VINYL_SLOTS:
        notes = [f"Logic: {logic_key}"]
        
        source_df = c_music if logic_key == 'LP_LOGIC' else c_prod
        
        pool = source_df[source_df['Hierarchy'].fillna('').astype(str).str.upper().str.strip().isin([h.upper() for h in hierarchies])].copy()
        
        if pool.empty:
            mask = pd.Series(False, index=source_df.index)
            for h in hierarchies:
                mask |= source_df['Hierarchy'].fillna('').str.contains(h, case=False, na=False)
            pool = source_df[mask].copy()

        pool = pool[~pool['Material'].isin(used_materials)]

        if pool.empty:
            diag.append((f"Slot {slot_num}", 0, "Empty Hierarchy"))
            continue

        pool['Final_Score'] = 0.0
        if 'AVAILABILITY' in pool.columns:
            pool.loc[pool['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Final_Score'] += 100000
            
        # 🔴 BUDGET CAP TABLES 
        if logic_key != 'LP_LOGIC' and '_p' in pool.columns:
            caps = TURNTABLE_ACCESSORY_BUDGET[ttier]
            cap = None
            
            if logic_key == 'AUDIO_LOGIC': cap = caps['audio_cap']
            elif logic_key == 'HEADPHONE_LOGIC': cap = caps['headphone_cap']
            elif logic_key == 'SURGE_LOGIC': cap = caps['surge_cap']
            elif logic_key in ['CABLE_JACK_USB_LOGIC', 'CABLE_RCA_LOGIC']: cap = caps['cable_cap']
            
            if cap:
                over_budget = pool['_p'] > cap
                pool.loc[over_budget, 'Final_Score'] -= 800000
                if over_budget.any():
                    notes.append(f"💶 Budget Tier [{ttier}]: Penalized items over €{cap}")

        # 🔴 DEEP LOGIC RULES
        
        if logic_key == 'LP_LOGIC':
            pool = pool.sort_values('Sales_30', ascending=False)
            notes.append("💿 Vinyl: Picked Top 30d Seller")

        elif logic_key == 'ACCESSORY_LOGIC':
            if tb in ["AUDIO-TECHNICA", "LENCO", "CROSLEY"]:
                needle_mask = pool['Hierarchy'].str.contains('ΒΕΛΟΝΕΣ', case=False, na=False)
                if needle_mask.any():
                    pool.loc[needle_mask, 'Final_Score'] += 500000
                    notes.append(f"Logic 6: Brand Match ({tb}) -> Replacement Needle Boosted")

        elif logic_key == 'AUDIO_LOGIC':
            pc_mask = pool['Hierarchy'].str.contains('PC SPEAKERS', case=False, na=False)
            bt_mask = pool['Hierarchy'].str.contains('ΦΟΡΗΤΟΥ ΗΧΟΥ', case=False, na=False)
            amp_mask = pool['Hierarchy'].str.contains('AMPLIFIERS|ΕΝΙΣΧΥΤΕΣ', case=False, na=False)
            hifi_mask = pool['Hierarchy'].str.contains('ΗΧΕΙΑ HI-FI', case=False, na=False)
            premium_audio_mask = pool['Hierarchy'].str.contains('SOUNDBARS|MULTIROOM', case=False, na=False)
            
            active_mask = pool['Title'].str.contains('Αυτοενισχυόμενα|Active|Powered', case=False, na=False) | pc_mask | premium_audio_mask

            # --- A. HARD TECHNICAL FILTERS ---
            if no_spk:
                if not has_preamp and is_rca:
                    pool.loc[amp_mask, 'Final_Score'] += 600000
                    pool.loc[hifi_mask, 'Final_Score'] += 400000
                    notes.append("Strict: No Pre-Amp -> Forced Amplifiers & Hi-Fi Speakers")
                else:
                    pool.loc[active_mask, 'Final_Score'] += 200000
                    notes.append("Strict: No Speakers -> Needs Active/Powered Output")
            elif has_spk or is_suitcase:
                pool.loc[amp_mask | hifi_mask, 'Final_Score'] -= 900000
                notes.append("Strict: Has Speakers -> Banned Amplifiers & Hi-Fi")

            # --- B. COMMERCIAL TIERING (SALES & BUDGET) ---
            if ttier == 'Entry':
                pool.loc[pc_mask, 'Final_Score'] += 500000
                notes.append("Sales Tier [Entry]: Boosted PC Speakers 2.0")
            elif ttier == 'Mid':
                if is_bt:
                    pool.loc[bt_mask, 'Final_Score'] += 500000
                    notes.append("Sales Tier [Mid + BT]: Boosted Portable BT")
                else:
                    pool.loc[pc_mask, 'Final_Score'] += 500000
                    notes.append("Sales Tier [Mid + No BT]: Boosted PC Speakers")
            elif ttier == 'Premium':
                pool.loc[premium_audio_mask, 'Final_Score'] += 500000
                if is_bt:
                    pool.loc[bt_mask, 'Final_Score'] += 300000
                notes.append("Sales Tier [Premium]: Boosted Soundbars & Multiroom")

        elif logic_key == 'CABLE_JACK_USB_LOGIC':
            if is_usb_conn or is_usb_extra:
                usb_mask = pool['Hierarchy'].str.contains('USB', case=False, na=False)
                pool.loc[usb_mask, 'Final_Score'] += 500000
                notes.append("Logic 4: USB Digitizer -> USB Cables Boosted")
                if 'Βύσμα(τα) (στην άλλη πλευρά) ≡' in pool.columns:
                    usb_b_mask = pool['Βύσμα(τα) (στην άλλη πλευρά) ≡'].fillna('').str.contains('USB-B|USB B', case=False, na=False) | pool['Title'].str.contains('USB-B|USB B', case=False, na=False)
                    pool.loc[usb_mask & usb_b_mask, 'Final_Score'] += 200000
            else:
                jack_mask = pool['Hierarchy'].str.contains('3.5MM', case=False, na=False)
                pool.loc[jack_mask, 'Final_Score'] += 300000
                notes.append("Non-USB -> Jack 3.5mm Boosted")

        elif logic_key == 'HEADPHONE_LOGIC':
            # Logic 5: Αν έχει BT το πικάπ, προτιμάμε Ασύρματα ακουστικά
            if is_bt:
                wl_mask = pool['Title'].str.contains('Wireless|Bluetooth|Ασύρματα', case=False, na=False)
                pool.loc[wl_mask, 'Final_Score'] += 200000
                notes.append("Logic 5: BT Turntable -> Wireless Headphones Boosted")

            # ── Οικοσύστημα & Λογική Προτεινόμενης Χρήσης (Tiering) ──
            if 'Προτεινόμενη χρήση' in pool.columns:
                usage_col = pool['Προτεινόμενη χρήση'].fillna('').str.lower()
                premium_usage = usage_col.str.contains('premium', na=False)
                music_usage = usage_col.str.contains('μουσική|music', na=False)
                
                is_same_brand = pool['Κατασκευαστής'].fillna('').str.strip().str.upper() == tb

                if tb == 'SONY':
                    # Οικοσύστημα SONY: Πρώτα τα Premium, μετά τα Μουσική, μετά οποιοδήποτε Sony
                    pool.loc[is_same_brand & premium_usage, 'Final_Score'] += 800000
                    pool.loc[is_same_brand & music_usage, 'Final_Score'] += 700000
                    pool.loc[is_same_brand, 'Final_Score'] += 600000
                    notes.append("Ecosystem Match: Boosted Sony (Premium -> Music)")
                elif ttier == 'Premium':
                    # Άλλα Premium πικάπ -> Ακουστικά "Premium"
                    pool.loc[premium_usage, 'Final_Score'] += 500000
                    notes.append("Premium Tier -> Boosted 'Premium' Usage Headphones")
                else:
                    # Entry / Mid πικάπ -> Ακουστικά "Μουσική"
                    pool.loc[music_usage, 'Final_Score'] += 500000
                    notes.append(f"{ttier} Tier -> Boosted 'Μουσική' Usage Headphones")

        elif logic_key == 'CABLE_RCA_LOGIC':
            if has_preamp:
                rca_mask = pool['Hierarchy'].str.contains('RCA', case=False, na=False)
                pool.loc[rca_mask, 'Final_Score'] += 500000
                notes.append("Logic 3: Has Pre-Amp -> RCA Cables Boosted")

        # ── SELECTION ──
        sort_col = 'Sales_30' if logic_key == 'LP_LOGIC' else 'Final_Score'
        
        pool = pool.sort_values([sort_col, 'Sales_30'], ascending=[False, False])
        
        if not pool.empty:
            chosen = pool.iloc[0]

            rc = chosen.copy()
            rc['Assigned_Slot'] = slot_num
            rc['Slot_Role'] = role
            rc['Marketing_Copy'] = VINYL_MARKETING_COPY.get("LP_GENRE" if logic_key == 'LP_LOGIC' else role, "Ιδανική επιλογή.")
            
            all_recs.append(rc)
            used_materials.add(chosen['Material'])
            slot_notes[slot_num] = notes
            diag.append((f"Slot {slot_num} ({role})", 1, f"Score/Sales: {chosen.get(sort_col, 0):.0f} / Price €{chosen.get('_p', 0):.0f}"))

    recs_df = pd.DataFrame(all_recs) if all_recs else pd.DataFrame()
    if not recs_df.empty: recs_df['Draft_Score'] = recs_df['Assigned_Slot']
    return recs_df, diag, slot_notes, recs_df
    
# ─────────────────────────────────────────────────────────────
# RUN ENGINE
# ─────────────────────────────────────────────────────────────
if active_cluster == "Smartphones":
    recs, diag, slot_diag, slot_notes, full_candidates = run_engine(trigger, df_products, df_history, df_slots)
elif active_cluster == "Laptops":
    # --- FIX: Combine both sheets so it finds Bags/Mice (Laptops sheet) AND Headsets (Products sheet) ---
    combined_pool = pd.concat([df_products, df_laptops], ignore_index=True)
    recs, diag, slot_notes, full_candidates = run_laptops_engine(trigger, combined_pool, df_history)
    slot_diag = []
elif active_cluster == "Floor Care":
    # Combine both sheets: triggers are in Vacuums, accessories may be in either
    combined_pool = pd.concat([df_products, df_vacuums], ignore_index=True)
    recs, diag, slot_notes, full_candidates = run_floor_care_engine(trigger, combined_pool, df_history)
    slot_diag = []
elif active_cluster == "TVs":
    recs, diag, slot_notes, full_candidates = run_tv_engine(trigger, df_products, df_history)
    slot_diag = []
elif active_cluster == "Tablets":
    recs, diag, slot_notes, full_candidates = run_tablets_engine(trigger, df_products, df_history)
    slot_diag = []
elif active_cluster == "Projectors":
    recs, diag, slot_notes, full_candidates = run_projectors_engine(trigger, df_products, df_history)
    slot_diag = []
elif active_cluster == "Turntables":
    recs, diag, slot_notes, full_candidates = run_vinyl_engine(trigger, df_products, df_peripherals, df_music, df_history)
    slot_diag = []
    full_candidates = recs
elif active_cluster in ("Mouse", "Keyboard", "Gaming Mouse", "Gaming Keyboard"):
    recs, diag, slot_notes, full_candidates = run_peripherals_engine(trigger, df_peripherals, df_history, active_cluster)
    slot_diag = []
elif active_cluster in STATIONERY_CLUSTERS:
    # Συνδυάζουμε Stationery ΚΑΙ Books ώστε να μπορεί να "δει" τα Coloring Books!
    combined_stat_books = pd.concat([df_stationery, df_books], ignore_index=True)
    
    stat_slots = STATIONERY_CLUSTER_SLOTS.get(active_cluster, [])
    
    # ── Markers sub-cluster routing: pick specialized slot list based on trigger TITLE first, then hierarchy ──
    # Title is more reliable than hierarchy — the data has "Μαρκαδόρος Γραφής Pilot Twin" filed under
    # ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ even though it's actually a writing marker, AND has "Μαρκαδόρος Ανεξίτηλος Office Log"
    # with Είδος="Μαρκαδόροι Γραφής" even though it's actually permanent. Title disambiguates both cases.
    if active_cluster == "Markers":
        trigger_hier = str(trigger.get('Hierarchy', '')).strip().upper()
        trigger_title_lower = str(trigger.get('Title', '')).strip().lower()
        trigger_eidos_lower = str(trigger.get('Είδος', '')).strip().lower()
        
        # Priority 1: TITLE-based detection (most reliable — the title is authored by humans and disambiguates)
        if 'υπογράμμισης' in trigger_title_lower or 'highlighter' in trigger_title_lower:
            stat_slots = HIGHLIGHTERS_SLOTS
        elif 'πίνακα' in trigger_title_lower or 'whiteboard' in trigger_title_lower or 'board marker' in trigger_title_lower:
            stat_slots = WHITEBOARD_MARKERS_SLOTS
        elif 'ζωγραφικής' in trigger_title_lower or 'drawing' in trigger_title_lower:
            stat_slots = DRAWING_MARKERS_SLOTS
        elif 'ανεξίτηλ' in trigger_title_lower or 'permanent' in trigger_title_lower:
            # Title takes precedence over Είδος — "Μαρκαδόρος Ανεξίτηλος" with Είδος="Γραφής" → permanent.
            stat_slots = PERMANENT_MARKERS_SLOTS
        elif 'γραφής' in trigger_title_lower or 'writing marker' in trigger_title_lower:
            # "Μαρκαδόρος Γραφής Pilot Twin" → writing markers
            stat_slots = WRITING_MARKERS_SLOTS
        # Priority 2: Είδος (Type) fallback — when title is generic
        elif 'ζωγραφικής' in trigger_eidos_lower:
            stat_slots = DRAWING_MARKERS_SLOTS
        elif 'γραφής' in trigger_eidos_lower:
            stat_slots = WRITING_MARKERS_SLOTS
        # Priority 3: Hierarchy fallback (for truly ambiguous triggers)
        elif trigger_hier == 'ΜΑΡΚΑΔΟΡΟΙ ΥΠΟΓΡΑΜΜΙΣΗΣ':
            stat_slots = HIGHLIGHTERS_SLOTS
        elif trigger_hier == 'ΜΑΡΚΑΔΟΡΟΙ ΠΙΝΑΚΑ':
            stat_slots = WHITEBOARD_MARKERS_SLOTS
        elif trigger_hier == 'ΜΑΡΚΑΔΟΡΟΙ ΖΩΓΡΑΦΙΚΗΣ':
            stat_slots = DRAWING_MARKERS_SLOTS
        elif trigger_hier == 'ΜΑΡΚΑΔΟΡΟΙ ΑΝΕΞΙΤΗΛΟΙ':
            stat_slots = PERMANENT_MARKERS_SLOTS
        # else: fall through to default MARKERS_SLOTS (for truly generic ΜΑΡΚΑΔΟΡΟΙ)
    
    if stat_slots:
        PERIPHERAL_CLUSTER_SLOTS[active_cluster] = stat_slots
    recs, diag, slot_notes, full_candidates = run_peripherals_engine(trigger, combined_stat_books, df_history, active_cluster)
    slot_diag = []
elif active_cluster in ("Monitors", "Printers", "Webcam", "USB Hub"):
    recs, diag, slot_notes, full_candidates = run_peripherals_engine(trigger, df_peripherals, df_history, active_cluster)
    slot_diag = []
else:
    df_all_for_books = pd.concat([df_books, df_products], ignore_index=True)
    recs, diag, slot_notes, full_candidates = run_books_engine(trigger, df_all_for_books, df_history)

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
    "Series Book": "Η συνέχεια της περιπέτειας!",
    "Start from Beginning": "Ξεκίνα από την αρχή!", 
    "Other Box Set": "Ολόκληρη η συλλογή!", 
    "Series Discovery": "Άλλη έκδοση της σειράς!",
    "Cross-Sell: IP Toy": "Ο ήρωας ζωντανεύει!",
    "Cross-Sell: Plush": "Αγκαλιά με τον αγαπημένο σου!",
    "Cross-Sell: Arts": "Δημιούργησε & φαντάσου!",
    "Cross-Sell: Creative Toy": "Χτίσε τον κόσμο σου!",
    "Cross-Sell: Puzzle": "Μάθε παίζοντας!",
    "Cross-Sell: Lifestyle": "Στιλ για κάθε μέρα!",
    "Cross-Sell: Collectable Cards": "Συλλογή για πρωταθλητές!",
    "Cross-Sell: Action Figure": "Ο ήρωας στο ράφι σου!",
    "Explore Series": "Ανακάλυψε κι άλλα από τη σειρά!",
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
        elif active_cluster == "Laptops":
            # Fetches the dynamic text we created, falls back to the dictionary
            marketing_text = str(r.get('Marketing_Copy', LAPTOP_MARKETING_COPY.get(raw_role, "Ιδανική επιλογή!")))
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

    if active_cluster == "Smartphones":
        header_text = "Μαζί με αυτό αγοράζουν"
    elif active_cluster == "Laptops":
        header_text = "Ολοκλήρωσε το setup σου"
    else:
        header_text = "Συνέχισε την περιπέτεια"

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
    
    # Unique variable name to avoid collision with UI 'cols'
    attr_keys_to_show = []
    if active_cluster == "Kids Books":
        attr_keys_to_show = ['Material','Title','Level 2','Hierarchy','Σειρά βιβλίου','Ηλικία','Εξώφυλλο','Brand','LIST PRICE']
    elif active_cluster == "Laptops":
        attr_keys_to_show = ['Material','Title','Level 1','Level 2','Hierarchy','Κατασκευαστής','Μοντέλο','Προτεινόμενη χρήση','Μέγεθος οθόνης','Θύρες','LIST PRICE']
    elif active_cluster == "Tablets":
        attr_keys_to_show = ['Material','Title','Level 2','Κατασκευαστής','Μοντέλο','Experts Rating','Λειτουργικό σύστημα','LIST PRICE']
    else:
        attr_keys_to_show = ['Material','Title','Level 2','Hierarchy','Κατασκευαστής','Μοντέλο','LIST PRICE']
        
    for a_key in attr_keys_to_show:
        try:
            if a_key in trigger.index:
                val = trigger[a_key]
                if isinstance(val, pd.Series): val = val.iloc[0]
            else: val = 'N/A'
        except: val = 'N/A'
        st.text(f"{a_key}: {val}")

    if not recs.empty:
        st.markdown("### Final Recommendations")
        df_disp = recs[['Title','Hierarchy','Assigned_Slot','Slot_Role','Final_Score']].copy()
        st.dataframe(df_disp, use_container_width=True, hide_index=True)

    # ─────────────────────────────────────────────────────────────
    # ONE-CLICK COPYABLE DIAGNOSTICS (COLLAPSED)
    # ─────────────────────────────────────────────────────────────
    with st.expander("📋 Copy Diagnostics", expanded=False):
        import json
        
        diag_export = f"Active Cluster: {active_cluster}\n\n--- TRIGGER ATTRIBUTES ---\n"
        for a_key in attr_keys_to_show:
            try:
                val = trigger[a_key].iloc[0] if isinstance(trigger.get(a_key), pd.Series) else trigger.get(a_key, 'N/A')
            except: val = 'N/A'
            diag_export += f"{a_key}: {val}\n"
            
        diag_export += "\n--- ENGINE FUNNEL ---\n"
        for step in diag:
            diag_export += f"{step[0]} | Count: {step[1]} | Note: {step[2]}\n"
            
        diag_export += "\n--- SLOT DETAILS ---\n"
        for sn, notes_list in sorted(slot_notes.items()):
            if notes_list:
                diag_export += f"\nPriority {sn}\n" + "\n".join(notes_list) + "\n"
                    
        if not recs.empty:
            diag_export += "\n--- FINAL RECOMMENDATIONS ---\n"
            for _, r in recs.iterrows():
                diag_export += f"Slot {r.get('Assigned_Slot', '?')}: {r.get('Title', 'Unknown')} (Score: {r.get('Final_Score', 0)})\n"

        safe_text = json.dumps(diag_export)
        
        copy_html = f"""
        <button id="cpBtn" style="background:#111; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:bold;">
            📋 Copy Full Text
        </button>
        <script>
        document.getElementById("cpBtn").addEventListener("click", function() {{
            navigator.clipboard.writeText({safe_text}).then(function() {{
                var b = document.getElementById("cpBtn");
                b.style.background = "#00897b"; b.innerText = "✅ Copied!";
                setTimeout(() => {{ b.style.background = "#111"; b.innerText = "📋 Copy Full Text"; }}, 2000);
            }});
        }});
        </script>
        """
        components.html(copy_html, height=70)
