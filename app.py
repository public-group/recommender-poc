import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
import re
from difflib import SequenceMatcher

st.set_page_config(page_title="Smart Recommender POC", layout="wide")

st.info("🟢 **Engine v4.2** — Defensive filtering: empty columns skipped, not fatal")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"

CLUSTER_CONFIG = {
    "Smartphones": {"allow_siblings": False, "hierarchy_cap": 2},
    "Kids Books":  {"allow_siblings": True,  "hierarchy_cap": 10},
}
ACTIVE_CLUSTER = "Smartphones"

SMART_BOOST      = 100
AVAIL_BOOST      = 50
HISTORY_BOOST    = 2000
HISTORY_FREQ_MIN = 3

TECH_CATEGORIES      = {"IT", "Telephony", "TV"}
APPLIANCE_CATEGORIES = {"MDA", "SDA", "Air Condition", "Personal Care"}

# Compatibility columns — different categories use different names
# We'll merge them into a single "_Compatible" column at load time
COMPAT_COLS = ["Συμβατό με", "Συμβατή συσκευή"]
COL_COMPAT_MERGED = "_Compatible"  # Internal merged column name

# ─────────────────────────────────────────────────────────────
# PORT EXTRACTION
# "Type-C 3.2 Gen 2" → "Type-C"
# "Lightning" → "Lightning"
# "Micro USB 2.0" → "Micro USB"
# ─────────────────────────────────────────────────────────────
def extract_base_port(raw_port: str) -> str:
    """Extract the base connector type, stripping version/gen info."""
    s = str(raw_port).strip()
    if not s or s.lower() == 'nan':
        return ''
    # Try to match common patterns
    s_lower = s.lower()
    if 'type-c' in s_lower or 'type c' in s_lower or 'usb-c' in s_lower or 'usb c' in s_lower:
        return 'Type-C'
    if 'lightning' in s_lower:
        return 'Lightning'
    if 'micro usb' in s_lower or 'micro-usb' in s_lower:
        return 'Micro USB'
    if 'usb' in s_lower:
        return 'USB'
    # Fallback: strip version numbers (e.g., "3.2 Gen 2")
    cleaned = re.sub(r'\s*\d+\.?\d*\s*(gen\s*\d+)?', '', s, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else s

# ─────────────────────────────────────────────────────────────
# COLOR MAPPING
# Map specific phone colors to case-friendly search terms
# "Black Titanium" → search for "Μαύρο" or "Black" in cases
# ─────────────────────────────────────────────────────────────
COLOR_BASE_MAP = {
    'black titanium': ['μαύρο', 'black', 'διάφανο'],
    'natural titanium': ['διάφανο', 'μπεζ', 'natural'],
    'white titanium': ['λευκό', 'white', 'διάφανο'],
    'blue titanium': ['μπλε', 'blue', 'διάφανο'],
    'deep purple': ['μωβ', 'μοβ', 'purple', 'διάφανο'],
    'space black': ['μαύρο', 'black', 'διάφανο'],
    'silver': ['ασημί', 'silver', 'διάφανο'],
    'gold': ['χρυσό', 'gold', 'διάφανο'],
    'starlight': ['λευκό', 'white', 'μπεζ', 'διάφανο'],
    'midnight': ['μαύρο', 'black', 'σκούρο μπλε', 'διάφανο'],
    'red': ['κόκκινο', 'red', 'διάφανο'],
    'pink': ['ροζ', 'pink', 'διάφανο'],
    'green': ['πράσινο', 'green', 'διάφανο'],
    'blue': ['μπλε', 'blue', 'διάφανο'],
    'yellow': ['κίτρινο', 'yellow', 'διάφανο'],
}

def get_case_colors(phone_color: str) -> list:
    """Get list of acceptable case colors for a given phone color."""
    key = phone_color.strip().lower()
    if key in COLOR_BASE_MAP:
        return COLOR_BASE_MAP[key]
    # Fallback: try partial match
    for map_key, colors in COLOR_BASE_MAP.items():
        if map_key in key or key in map_key:
            return colors
    # Last resort: just allow transparent + the raw color
    return [key, 'διάφανο']


# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    url_p = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Products"
    url_h = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=History"
    url_s = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Slot_Matrix"
    df_p = pd.read_csv(url_p);  df_p.columns = df_p.columns.str.strip()
    df_h = pd.read_csv(url_h);  df_h.columns = df_h.columns.str.strip()
    df_s = pd.read_csv(url_s);  df_s.columns = df_s.columns.str.strip()

    # Merge compatibility columns into one unified field
    # Coalesce: take whichever column has data for each row
    compat_parts = []
    found_cols = []
    for col in COMPAT_COLS:
        if col in df_p.columns:
            compat_parts.append(df_p[col].fillna('').astype(str).str.strip())
            found_cols.append(col)
    if compat_parts:
        # Join all non-empty values with semicolon (in case a product has data in both)
        df_p[COL_COMPAT_MERGED] = compat_parts[0]
        for extra in compat_parts[1:]:
            # Where the merged field is empty, take the other; otherwise append
            empty_mask = df_p[COL_COMPAT_MERGED] == ''
            df_p.loc[empty_mask, COL_COMPAT_MERGED] = extra[empty_mask]
            df_p.loc[~empty_mask, COL_COMPAT_MERGED] = (
                df_p.loc[~empty_mask, COL_COMPAT_MERGED] + ';' + extra[~empty_mask]
            )
        # Clean up trailing semicolons from empty values
        df_p[COL_COMPAT_MERGED] = df_p[COL_COMPAT_MERGED].str.strip(';').str.replace(';;', ';')
    else:
        df_p[COL_COMPAT_MERGED] = ''
        found_cols = []

    return df_p, df_h, df_s, found_cols

df_products, df_history, df_slots, compat_found_cols = load_data()

st.title("📱 Smartphone Recommendation Tool")

# ─────────────────────────────────────────────────────────────
# TRIGGER SELECTION
# ─────────────────────────────────────────────────────────────
phones = df_products[
    (df_products['Level 2'] == 'Mobiles') &
    (df_products['Hierarchy'] == 'Smartphones')
]
if phones.empty:
    phones = df_products[df_products['Level 2'] == 'Mobiles']
    st.sidebar.warning("⚠ 'Smartphones' hierarchy not found — using all Mobiles")

selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]
st.subheader(f"Building the perfect loadout for: {selected_phone_name}")


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def title_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100

def parse_euro_price(val):
    s = str(val).replace('€', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

def passes_price_ceiling(trigger_price, next_price, trigger_level1):
    if next_price <= 0 or trigger_price <= 0:
        return True
    peer = {"Books", "Stationery", "Toys", "Music & Films", "Gaming"}
    if trigger_level1 in peer:
        return next_price <= trigger_price * 1.5
    elif trigger_price <= 30:
        return next_price <= trigger_price * 1.5
    else:
        return next_price <= max(trigger_price * 0.40, 45)

def safe(val):
    return html_lib.escape(str(val))

def col_sample(df, col, n=5):
    """Get sample non-empty values from a column for debugging."""
    if col not in df.columns:
        return f"[COLUMN '{col}' NOT FOUND]"
    vals = df[col].dropna().astype(str)
    vals = vals[vals.str.strip() != '']
    if vals.empty:
        return "[ALL EMPTY]"
    return vals.head(n).tolist()

def col_has_data(df, col, min_pct=0.05):
    """Check if a column has meaningful data in at least min_pct of rows."""
    if col not in df.columns:
        return False
    vals = df[col].fillna('').astype(str).str.strip()
    populated = (vals != '').sum()
    return (populated / len(df)) >= min_pct if len(df) > 0 else False

def soft_filter(sc, col, pattern, notes, label, case=False):
    """Apply filter only if column has data. Returns filtered df.
    If column is empty, skip and log it."""
    if not col_has_data(sc, col):
        notes.append(f"{label}: SKIPPED ({col} empty for this slice)")
        return sc
    before = len(sc)
    filtered = sc[sc[col].fillna('').str.contains(pattern, case=case, regex=True)]
    notes.append(f"{label}: {before}→{len(filtered)}")
    if len(filtered) == 0:
        notes.append(f"  Sample {col}: {col_sample(sc, col, 5)}")
        return sc  # Return unfiltered rather than empty — downgrade to no-filter
    return filtered

def soft_filter_strict(sc, col, pattern, notes, label, case=False):
    """Apply filter strictly — if column has data, filter. If empty, skip.
    Unlike soft_filter, returns empty if filter matches nothing."""
    if not col_has_data(sc, col):
        notes.append(f"{label}: SKIPPED ({col} empty)")
        return sc
    before = len(sc)
    filtered = sc[sc[col].fillna('').str.contains(pattern, case=case, regex=True)]
    notes.append(f"{label}: {before}→{len(filtered)}")
    if len(filtered) == 0:
        notes.append(f"  Sample {col}: {col_sample(sc, col, 5)}")
    return filtered


# ─────────────────────────────────────────────────────────────
# THE ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_recommendations(trigger, df_products, df_history, df_slots):
    config = CLUSTER_CONFIG[ACTIVE_CLUSTER]
    diag = []
    slot_diag = []
    slot_debug_notes = {}  # Extra notes per slot

    # ── Trigger attributes ──
    trig_material  = trigger['Material']
    trig_title     = str(trigger.get('Title', ''))
    trig_brand     = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    trig_model     = str(trigger.get('Μοντέλο', '')).strip()
    trig_port_raw  = str(trigger.get('Θύρα USB', '')).strip()
    trig_port      = extract_base_port(trig_port_raw)
    trig_color     = str(trigger.get('Χρώμα', '')).strip()
    trig_extras    = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    trig_os        = str(trigger.get('Λειτουργικό σύστημα', '')).lower()
    trig_hierarchy = str(trigger.get('Hierarchy', ''))
    trig_level1    = str(trigger.get('Level 1', ''))
    trig_price     = parse_euro_price(trigger.get('LIST PRICE', 0))

    case_colors = get_case_colors(trig_color)

    c = df_products[df_products['Material'] != trig_material].copy()
    diag.append(("0. Start", len(c), ""))

    # ── U2a: Exact title dedup ──
    c = c[c['Title'] != trig_title]
    diag.append(("1. U2a: title dedup", len(c), ""))

    # ── U2b: Ghost SKU ──
    if 'CW Stock Units' in c.columns:
        stock = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        pct = (stock > 0).sum() / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c['CW Stock Units'] = stock.fillna(0)
            c = c[c['CW Stock Units'] > 0]
            diag.append(("2. U2b: stock", len(c), f"Applied ({pct:.0%} populated)"))
        else:
            diag.append(("2. U2b: stock", len(c), f"⚠ SKIPPED ({pct:.0%} populated)"))
    else:
        diag.append(("2. U2b: stock", len(c), "⚠ SKIPPED (no column)"))

    # ── U1: Anti-Sibling ──
    if not config["allow_siblings"]:
        mask = (
            (c['Hierarchy'] == trig_hierarchy) &
            (c['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand)
        )
        n_sibs = mask.sum()
        if mask.any():
            sims = c.loc[mask, 'Title'].apply(lambda t: title_similarity(trig_title, str(t)))
            dupes = sims[sims >= 70].index
            c = c.drop(dupes)
            diag.append(("3. U1: siblings", len(c), f"Checked {n_sibs}, removed {len(dupes)}"))
        else:
            diag.append(("3. U1: siblings", len(c), "No siblings"))
    else:
        diag.append(("3. U1: siblings", len(c), "Bypassed"))

    # ── U3: Macro wall ──
    b4 = len(c)
    if trig_level1 in TECH_CATEGORIES:
        c = c[~c['Level 1'].isin(APPLIANCE_CATEGORIES)]
    elif trig_level1 in APPLIANCE_CATEGORIES:
        c = c[~c['Level 1'].isin(TECH_CATEGORIES)]
    diag.append(("4. U3: macro wall", len(c), f"Removed {b4 - len(c)}"))

    # ── Scoring ──
    tcust = df_history[df_history['Material'] == trig_material]['customerEmail'].unique()
    bw = df_history[(df_history['customerEmail'].isin(tcust)) & (df_history['Material'] != trig_material)]
    fdf = bw['Material'].value_counts().reset_index()
    fdf.columns = ['Next_Item_ID', 'Frequency']

    c = c.merge(fdf, left_on='Material', right_on='Next_Item_ID', how='left')
    c['Frequency'] = c['Frequency'].fillna(0).astype(int)
    c['History_Score'] = c['Frequency'].apply(lambda f: HISTORY_BOOST if f >= HISTORY_FREQ_MIN else 0)
    c['Next_Price'] = c['LIST PRICE'].apply(parse_euro_price)

    hm = c['History_Score'] > 0
    if hm.any():
        ok = c.loc[hm].apply(lambda r: passes_price_ceiling(trig_price, r['Next_Price'], trig_level1), axis=1)
        c.loc[ok[~ok].index, 'History_Score'] = 0

    c['Avail_Boost'] = 0
    c.loc[c['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Avail_Boost'] = AVAIL_BOOST

    c['Smart_Boost'] = 0
    c.loc[c['Μοντέλο'] == trigger.get('Μοντέλο', ''), 'Smart_Boost'] += SMART_BOOST
    c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Smart_Boost'] += SMART_BOOST

    c['Final_Score'] = c['History_Score'] + c['Frequency'] + c['Avail_Boost'] + c['Smart_Boost']

    b4u5 = len(c)
    nhm = c['History_Score'] == 0
    if nhm.any():
        ok2 = c.loc[nhm].apply(lambda r: passes_price_ceiling(trig_price, r['Next_Price'], trig_level1), axis=1)
        c = c.drop(ok2[~ok2].index)
    diag.append(("5. U5: price ceiling", len(c), f"Removed {b4u5 - len(c)} (ceiling: €{max(trig_price*0.40,45):.2f})"))

    # ─────────────────────────────────────────
    # SLOT ASSIGNMENT
    # ─────────────────────────────────────────
    all_slot = []

    for _, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_h = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]
        sc = c[c['Hierarchy'].isin(allowed_h)].copy()
        after_h = len(sc)
        notes = []

        # ── ATTRIBUTE LOGIC (defensive: empty columns = skip filter) ──

        if slot_num in [1, 2, 7, 10]:
            # Step 1: Model match via compatibility column
            if trig_model:
                before_model = len(sc)
                matched = sc[sc[COL_COMPAT_MERGED].fillna('').str.contains(trig_model, case=False, regex=False)]
                notes.append(f"Model '{trig_model}': {before_model}→{len(matched)}")
                if len(matched) > 0:
                    sc = matched
                else:
                    notes.append(f"  ⚠ Model match failed — keeping all {len(sc)} (Sample _Compatible: {col_sample(sc, COL_COMPAT_MERGED, 3)})")

            # Step 2: Sub-type filter
            if slot_num == 1 and not sc.empty:
                sc = soft_filter(sc, 'Τύπος Θήκης', "Back Cover", notes, "Back Cover")
                if not sc.empty and trig_color:
                    before_color = len(sc)
                    sc = sc[sc['Χρώμα'].fillna('').str.strip().str.lower().isin(case_colors)]
                    notes.append(f"Color {case_colors[:3]}: {before_color}→{len(sc)}")

            elif slot_num == 2 and not sc.empty:
                # Try strict filter first; if column empty, hierarchy already limits to screen protectors
                sc = soft_filter(sc, 'Τύπος προϊόντος', "Προστατευτικό οθόνης|Tempered Glass|Screen Protector|Glass", notes, "Screen Protector type")

            elif slot_num == 7:
                if not sc.empty:
                    sc = soft_filter(sc, 'Τύπος προϊόντος', "Προστατευτικό καμερών|Camera|Κάμερα", notes, "Camera Protector type")
                if sc.empty and trig_port:
                    fb_h = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS']
                    sc = c[c['Hierarchy'].isin(fb_h)].copy()
                    if trig_model:
                        fb_model = sc[sc[COL_COMPAT_MERGED].fillna('').str.contains(trig_model, case=False, regex=False)]
                        if not fb_model.empty:
                            sc = fb_model
                    sc = soft_filter(sc, COL_COMPAT_MERGED, trig_port, notes, f"Fallback cable ({trig_port})")

            elif slot_num == 10 and not sc.empty:
                sc = soft_filter(sc, 'Τύπος Θήκης', "Book Cover|Wallet|360 Full Cover|Folio|Flip", notes, "Book/Wallet/Folio type")

        elif slot_num == 3:
            # Chargers: _Compatible often has model names ("Universal", "iPhone 15 Pro") NOT port types
            # Strategy: try model match OR "Universal", then port match, then type filter
            if not sc.empty:
                before = len(sc)
                # Match on model name in compat, OR "Universal" items
                compat_vals = sc[COL_COMPAT_MERGED].fillna('').str.lower()
                if trig_model:
                    model_or_universal = compat_vals.str.contains(trig_model.lower(), regex=False) | compat_vals.str.contains("universal", regex=False)
                else:
                    model_or_universal = compat_vals.str.contains("universal", regex=False)
                # Also keep items where compat has the port type (some chargers do use it)
                if trig_port:
                    model_or_universal = model_or_universal | compat_vals.str.contains(trig_port.lower(), regex=False)
                # Also keep items with empty compat (they're likely universal)
                model_or_universal = model_or_universal | (compat_vals == '')
                matched = sc[model_or_universal]
                notes.append(f"Compat (model/universal/port/empty): {before}→{len(matched)}")
                if len(matched) > 0:
                    sc = matched

            if "γρήγορη φόρτιση" in trig_extras and not sc.empty:
                sc = soft_filter(sc, 'Ισχύς (Watt)', "21 - 60|61 - 100", notes, "Fast charge watt")

            if not sc.empty:
                if "ασύρματη φόρτιση" in trig_extras:
                    sc = soft_filter(sc, 'Τύπος3', "Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", notes, "Wireless charger type")
                    sc.loc[sc['Τύπος3'].fillna('').str.contains("Ασύρματος Φορτιστής", case=False), 'Final_Score'] += SMART_BOOST
                    if trig_brand == "APPLE":
                        sc.loc[sc['Title'].fillna('').str.contains("MagSafe", case=False), 'Final_Score'] += SMART_BOOST
                else:
                    sc = soft_filter(sc, 'Τύπος3', "Φορτιστής Πρίζας|Σετ Φόρτισης", notes, "Wall charger type")

        elif slot_num == 4:
            # Audio: Τύπος σύνδεσης may be empty — if so, keep all and just boost
            if "3.5mm jack" in trig_extras:
                if col_has_data(sc, 'Τύπος σύνδεσης'):
                    sc.loc[sc['Τύπος σύνδεσης'].fillna('').str.contains("Jack 3.5mm", case=False), 'Final_Score'] += SMART_BOOST
                    notes.append(f"3.5mm boost applied")
                else:
                    notes.append("3.5mm boost: SKIPPED (Τύπος σύνδεσης empty)")
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST
                notes.append(f"Brand boost applied, {len(sc)} remain")
            else:
                # Try to filter by BT/port, but if column is empty, keep all and boost brand
                if col_has_data(sc, 'Τύπος σύνδεσης'):
                    before = len(sc)
                    filtered = sc[sc['Τύπος σύνδεσης'].fillna('').str.contains(f"Bluetooth|{trig_port}", case=False)]
                    notes.append(f"BT/Port '{trig_port}': {before}→{len(filtered)}")
                    if len(filtered) > 0:
                        sc = filtered
                    else:
                        notes.append(f"  ⚠ No matches — keeping all {len(sc)}")
                else:
                    notes.append(f"Connection type filter: SKIPPED (column empty), {len(sc)} remain")
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

        elif slot_num == 5:
            # Powerbank: Τύπος θύρας may be empty
            if trig_port:
                if col_has_data(sc, 'Τύπος θύρας'):
                    before = len(sc)
                    filtered = sc[sc['Τύπος θύρας'].fillna('').str.contains(trig_port, case=False, regex=False)]
                    notes.append(f"Port '{trig_port}': {before}→{len(filtered)}")
                    if len(filtered) > 0:
                        sc = filtered
                    else:
                        notes.append(f"  ⚠ No matches — keeping all {len(sc)}")
                else:
                    notes.append(f"Port filter: SKIPPED (Τύπος θύρας empty), {len(sc)} remain")
            if "γρήγορη φόρτιση" in trig_extras and not sc.empty:
                if col_has_data(sc, 'Ταχύτητα φόρτισης') or col_has_data(sc, 'Ισχύς (Watt)'):
                    sc.loc[
                        sc['Ταχύτητα φόρτισης'].fillna('').str.contains("Ταχεία|Υπερταχεία", case=False) |
                        sc['Ισχύς (Watt)'].fillna('').str.contains("20|30|40|50|60", case=False),
                        'Final_Score'
                    ] += SMART_BOOST
                    notes.append("Fast charge boost applied")
                else:
                    notes.append("Fast charge boost: SKIPPED (columns empty)")
            if "ασύρματη φόρτιση" in trig_extras and not sc.empty:
                sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Ασύρματη φόρτιση", case=False), 'Final_Score'] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Magsafe", case=False), 'Final_Score'] += SMART_BOOST
            if not sc.empty:
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

        elif slot_num == 6:
            before = len(sc)
            if "με pen" in trig_extras:
                sc = soft_filter(sc, 'Τύπος3', "Γραφίδα", notes, "Stylus")
            elif trig_brand == "APPLE":
                # Try Τύπος3 first, but also search Title and Hierarchy for AirTag
                if col_has_data(sc, 'Τύπος3'):
                    filtered = sc[sc['Τύπος3'].fillna('').str.contains("AirTag|Air Tag", case=False)]
                    if not filtered.empty:
                        sc = filtered
                        notes.append(f"AirTag (Τύπος3): {before}→{len(sc)}")
                    else:
                        # Fallback: search in Title or Hierarchy
                        filtered2 = sc[
                            sc['Title'].fillna('').str.contains("AirTag|Air Tag", case=False) |
                            sc['Hierarchy'].fillna('').str.contains("AIRTAG", case=False)
                        ]
                        if not filtered2.empty:
                            sc = filtered2
                            notes.append(f"AirTag (Title/Hierarchy fallback): {before}→{len(sc)}")
                        else:
                            notes.append(f"AirTag: {before}→0 (Sample Τύπος3: {col_sample(sc, 'Τύπος3', 5)})")
                            sc = sc.head(0)  # Empty
                else:
                    # Column empty — try Title/Hierarchy
                    filtered2 = sc[
                        sc['Title'].fillna('').str.contains("AirTag|Air Tag", case=False) |
                        sc['Hierarchy'].fillna('').str.contains("AIRTAG", case=False)
                    ]
                    if not filtered2.empty:
                        sc = filtered2
                    notes.append(f"AirTag (Τύπος3 empty, Title/Hierarchy): {before}→{len(sc)}")
            else:
                sc = soft_filter(sc, 'Τύπος3',
                    "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού",
                    notes, "Misc accessories")

        elif slot_num == 8:
            before = len(sc)
            if "ios" in trig_os or trig_brand == "APPLE":
                if col_has_data(sc, COL_COMPAT_MERGED):
                    filtered = sc[sc[COL_COMPAT_MERGED].fillna('').str.contains("iOS|Apple", case=False)]
                    if not filtered.empty:
                        sc = filtered
                        notes.append(f"iOS compat: {before}→{len(sc)}")
                    else:
                        notes.append(f"iOS compat: no matches (Sample: {col_sample(sc, COL_COMPAT_MERGED, 3)}), keeping all {len(sc)}")
                else:
                    notes.append(f"OS compat: SKIPPED (column empty), {len(sc)} remain")
            elif "android" in trig_os or trig_brand in ["SAMSUNG", "XIAOMI", "MOTOROLA"]:
                if col_has_data(sc, COL_COMPAT_MERGED):
                    filtered = sc[sc[COL_COMPAT_MERGED].fillna('').str.contains("Android", case=False)]
                    if not filtered.empty:
                        sc = filtered
                        notes.append(f"Android compat: {before}→{len(sc)}")
                    else:
                        notes.append(f"Android compat: no matches, keeping all {len(sc)}")
                else:
                    notes.append(f"OS compat: SKIPPED (column empty), {len(sc)} remain")
            sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

        elif slot_num == 9:
            if trig_brand == "APPLE" and "ασύρματη φόρτιση" in trig_extras:
                sc.loc[sc['Τρόπος τοποθέτησης'].fillna('').str.contains("Μαγνητική", case=False), 'Final_Score'] += SMART_BOOST
            notes.append(f"No hard filter, {len(sc)} remain")

        after_attr = len(sc)
        slot_diag.append((slot_num, slot_rule.get('Slot_Role', ''), after_h, after_attr))
        slot_debug_notes[slot_num] = notes

        if not sc.empty:
            sc = sc.sort_values(by='Final_Score', ascending=False).copy()
            sc['Assigned_Slot'] = slot_num
            sc['Slot_Role'] = slot_rule['Slot_Role']
            sc['Item_Rank'] = range(1, len(sc) + 1)
            sc['Draft_Score'] = sc['Item_Rank'] * 100 + slot_num
            all_slot.append(sc)

    if not all_slot:
        return pd.DataFrame(), diag, slot_diag, slot_debug_notes

    full = pd.concat(all_slot, ignore_index=True)

    # ── S1: Hierarchy cap ──
    hcap = config["hierarchy_cap"]
    full = full.sort_values(by='Draft_Score').reset_index(drop=True)
    selected = []
    hcounts = {}
    seen = set()
    for _, row in full.iterrows():
        h, mat = row['Hierarchy'], row['Material']
        if mat in seen: continue
        if hcounts.get(h, 0) >= hcap: continue
        selected.append(row)
        hcounts[h] = hcounts.get(h, 0) + 1
        seen.add(mat)
        if len(selected) >= 10: break

    diag.append(("6. Final", len(selected), f"Hierarchy cap={hcap}"))

    if selected:
        return pd.DataFrame(selected), diag, slot_diag, slot_debug_notes
    return pd.DataFrame(), diag, slot_diag, slot_debug_notes


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
st.markdown("### <span style='color:#ff5e00; font-weight:bold;'>|</span> Μαζί με αυτό, οι περισσότεροι αγοράζουν", unsafe_allow_html=True)

recs, diag, slot_diag, slot_notes = calculate_recommendations(trigger, df_products, df_history, df_slots)


# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🩺 Diagnostics")

# Derived values
trig_port_raw = str(trigger.get('Θύρα USB', '')).strip()
trig_port = extract_base_port(trig_port_raw)
trig_color = str(trigger.get('Χρώμα', '')).strip()
case_colors = get_case_colors(trig_color)

st.markdown(f"""**Derived matching values:**
- Port: `{trig_port_raw}` → **`{trig_port}`**
- Color: `{trig_color}` → case colors: **{case_colors}**
- Compatibility columns found: **{compat_found_cols}** → merged into `_Compatible`
""")

# Guardrail funnel
st.markdown("### Guardrail Funnel")
st.dataframe(pd.DataFrame(diag, columns=["Step", "Candidates Left", "Note"]), use_container_width=True, hide_index=True)

# Slot breakdown with debug notes
st.markdown("### Per-Slot Breakdown")
st.dataframe(pd.DataFrame(slot_diag, columns=["Slot", "Role", "After Hierarchy", "After Attributes"]), use_container_width=True, hide_index=True)

st.markdown("### Per-Slot Filter Details")
for slot_num, notes in sorted(slot_notes.items()):
    if notes:
        with st.expander(f"Slot {slot_num} — {notes[0][:60]}..." if len(notes[0]) > 60 else f"Slot {slot_num} — {notes[0]}"):
            for n in notes:
                st.text(n)

# Trigger info
with st.expander("📋 Trigger Attributes"):
    for col in ['Material', 'Title', 'Level 1', 'Level 2', 'Hierarchy',
                'Κατασκευαστής', 'Μοντέλο', 'Θύρα USB', 'Χρώμα',
                'Λειτουργικό σύστημα', 'Extra Χαρακτηριστικά', 'LIST PRICE']:
        st.text(f"{col}: {trigger.get(col, 'N/A')}")

# Score table
if not recs.empty:
    st.markdown("### Score Breakdown")
    dcols = ['Title', 'Hierarchy', 'Assigned_Slot', 'Slot_Role', 'Item_Rank',
             'History_Score', 'Frequency', 'Avail_Boost', 'Smart_Boost',
             'Final_Score', 'Draft_Score']
    st.dataframe(recs[[c for c in dcols if c in recs.columns]], use_container_width=True)

st.markdown("---")


# ─────────────────────────────────────────────────────────────
# VISUALIZATION
# ─────────────────────────────────────────────────────────────
if not recs.empty:
    recs_to_show = recs.head(10)

    cards_html = ""
    for _, row in recs_to_show.iterrows():
        img_url    = safe(str(row.get('Thumbnails', '')).strip())
        raw_price  = parse_euro_price(row.get('LIST PRICE', 0))
        new_price  = f"{raw_price:.2f}".replace('.', ',')
        old_price  = f"{(raw_price * 1.25):.2f}".replace('.', ',')
        title      = safe(str(row.get('Title', '')))
        slot_label = safe(str(row.get('Slot_Role', '')))
        slot_num   = int(row.get('Assigned_Slot', 0))

        cards_html += f"""<div class="product-card">
            <div class="slot-badge">Slot {slot_num}</div>
            <img src="{img_url}" alt="product">
            <div class="title" title="{title}">{title}</div>
            <div class="slot-role">{slot_label}</div>
            <div class="reviews"><span class="score">4.8</span> <span class="stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> <span class="count">(305)</span></div>
            <div class="old-price">&#928;.&#923;.&#932;. : {old_price}&#8364;</div>
            <div class="new-price">{new_price.split(',')[0]}<span class="decimals">,{new_price.split(',')[1]}&#8364;</span></div>
            <button class="cart-btn">&#128722;</button>
        </div>"""

    card_css = """
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:transparent}
        .product-card{background:#fff;border:1px solid #f0f0f0;border-radius:12px;padding:15px;
            display:flex;flex-direction:column;align-items:center;box-shadow:0 4px 6px rgba(0,0,0,.05);
            flex-shrink:0;position:relative}
        .slot-badge{position:absolute;top:8px;left:8px;background:#ff5e00;color:#fff;
            font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px}
        .product-card img{height:120px;object-fit:contain;margin-bottom:15px}
        .title{font-size:13px;color:#333;text-align:center;height:36px;overflow:hidden;
            display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-bottom:10px}
        .slot-role{font-size:10px;color:#888;margin-bottom:8px;text-align:center}
        .reviews{font-size:11px;margin-bottom:15px}
        .score{color:#ff5e00;font-weight:700}.stars{color:#ff5e00;letter-spacing:-2px}.count{color:#1a73e8}
        .old-price{font-size:11px;color:#888;text-decoration:line-through;margin-bottom:2px}
        .new-price{font-size:18px;font-weight:700;color:#ff5e00;margin-bottom:15px}
        .decimals{font-size:12px}
        .cart-btn{background:#ff5e00;color:#fff;border:none;border-radius:8px;
            width:40px;height:35px;font-size:16px;cursor:pointer}
        .cart-btn:hover{background:#e65500}
    """

    desktop_page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    {card_css}
    .carousel{{display:flex;overflow-x:auto;gap:15px;padding:10px 5px 15px;scrollbar-width:thin}}
    .carousel .product-card{{width:200px;min-width:200px}}
    </style></head><body><div class="carousel">{cards_html}</div></body></html>"""

    mobile_page = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    {card_css}
    .mockup{{border:12px solid #333;border-radius:36px;padding:15px 10px;
        background:#fafafa;height:470px;overflow:hidden}}
    .m-header{{text-align:center;font-weight:700;font-size:18px;margin-bottom:15px;line-height:1.2}}
    .m-carousel{{display:flex;overflow-x:auto;gap:10px;padding-bottom:15px;scrollbar-width:none}}
    .m-carousel::-webkit-scrollbar{{display:none}}
    .m-carousel .product-card{{width:calc(50% - 5px);min-width:calc(50% - 5px);padding:10px}}
    .m-carousel .product-card img{{height:90px}}
    .m-carousel .title{{font-size:11px;height:30px}}
    .m-carousel .slot-role{{font-size:9px}}.m-carousel .reviews{{font-size:10px}}
    .m-carousel .old-price{{font-size:10px}}.m-carousel .new-price{{font-size:16px}}
    .m-carousel .decimals{{font-size:11px}}.m-carousel .cart-btn{{width:36px;height:32px;font-size:14px}}
    .m-carousel .slot-badge{{font-size:9px;padding:2px 6px}}
    </style></head><body>
    <div class="mockup">
        <div class="m-header"><span style="color:#ff5e00">&#8212;</span><br>
        &#924;&#945;&#950;&#943; &#956;&#949; &#945;&#965;&#964;&#972;, &#959;&#953;<br>
        &#960;&#949;&#961;&#953;&#963;&#963;&#972;&#964;&#949;&#961;&#959;&#953; &#945;&#947;&#959;&#961;&#940;&#950;&#959;&#965;&#957;</div>
        <div class="m-carousel">{cards_html}</div>
    </div></body></html>"""

    col_d, col_sp, col_m = st.columns([2.5, 0.2, 1.3])
    with col_d:
        st.write("##### 💻 Web View")
        components.html(desktop_page, height=380, scrolling=True)
    with col_m:
        st.write("##### 📱 Mobile View")
        components.html(mobile_page, height=520, scrolling=False)
else:
    st.error("❌ No recommendations. Check diagnostics above — especially Per-Slot Filter Details.")
