import streamlit as st
import pandas as pd
from difflib import SequenceMatcher

st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"

# Cluster-level settings (from Global Rules Part 4)
CLUSTER_CONFIG = {
    "Smartphones": {
        "allow_siblings": False,
        "hierarchy_cap": 2,
    },
    "Kids Books": {
        "allow_siblings": True,
        "hierarchy_cap": 10,
    },
}
ACTIVE_CLUSTER = "Smartphones"

# The spec says flat +100 per synergy rule (Global Rules Part 1, Section 2).
# If you intentionally want variable weights, change these and document why.
SMART_BOOST      = 100   # Any synergy match
AVAIL_BOOST      = 50    # "Άμεσα Διαθέσιμο"
HISTORY_BOOST    = 2000  # Frequency >= 3
HISTORY_FREQ_MIN = 3     # Minimum frequency to trigger history boost

# Macro-category walls (Global Rules U3)
TECH_CATEGORIES     = {"IT", "Telephony", "TV"}
APPLIANCE_CATEGORIES = {"MDA", "SDA", "Air Condition", "Personal Care"}

# Column name config — change here if your sheet uses different names
COL_COMPATIBLE = "Συμβατό με"   # Spec says "Συμβατή συσκευή" — verify your sheet


# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    url_products = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Products"
    url_history  = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=History"
    url_slots    = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Slot_Matrix"

    df_p = pd.read_csv(url_products)
    df_h = pd.read_csv(url_history)
    df_s = pd.read_csv(url_slots)

    # Strip accidental spaces from column names
    df_p.columns = df_p.columns.str.strip()
    df_h.columns = df_h.columns.str.strip()
    df_s.columns = df_s.columns.str.strip()

    return df_p, df_h, df_s

df_products, df_history, df_slots = load_data()

st.title("📱 Smartphone Recommendation Tool")


# ─────────────────────────────────────────────────────────────
# 1. SELECT THE TRIGGER
# Gap 8: Spec says Trigger = Level 2 == 'Mobiles' AND Hierarchy == 'Smartphones'
# ─────────────────────────────────────────────────────────────
phones = df_products[
    (df_products['Level 2'] == 'Mobiles') &
    (df_products['Hierarchy'] == 'Smartphones')
]
selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]

st.subheader(f"Building the perfect loadout for: {selected_phone_name}")


# ─────────────────────────────────────────────────────────────
# HELPER: Levenshtein-style similarity (for U1)
# ─────────────────────────────────────────────────────────────
def title_similarity(a: str, b: str) -> float:
    """Return 0-100 similarity score between two titles."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


# ─────────────────────────────────────────────────────────────
# HELPER: Price parsing (European format)
# ─────────────────────────────────────────────────────────────
def parse_euro_price(val) -> float:
    """Parse a European-format price string into a float."""
    s = str(val).replace('€', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '')      # "1.234,56" → "1234,56"
    s = s.replace(',', '.')         # "1234,56" → "1234.56"
    try:
        return float(s)
    except ValueError:
        return 0.0


# ─────────────────────────────────────────────────────────────
# HELPER: Price ceiling check (Global Rules Part 1 + U5)
# ─────────────────────────────────────────────────────────────
def passes_price_ceiling(trigger_price: float, next_price: float, trigger_level1: str) -> bool:
    """
    Returns True if the candidate's price is within the allowed ceiling.
    Condition A: Peer categories → up to 150%.
    Condition B: Trigger price ≤ €30 → up to 150%.
    Condition C: Otherwise → 40% cap OR flat €45, whichever is higher.
    """
    if next_price <= 0 or trigger_price <= 0:
        return True  # Can't evaluate — let it through

    peer_categories = {"Books", "Stationery", "Toys", "Music & Films", "Gaming"}

    if trigger_level1 in peer_categories:
        return next_price <= trigger_price * 1.5
    elif trigger_price <= 30:
        return next_price <= trigger_price * 1.5
    else:
        ceiling = max(trigger_price * 0.4, 45)
        return next_price <= trigger_price + ceiling


# ─────────────────────────────────────────────────────────────
# THE MAIN ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_recommendations(trigger, df_products, df_history, df_slots):
    config = CLUSTER_CONFIG[ACTIVE_CLUSTER]

    # ── Trigger attributes (safe extraction) ──
    trig_material = trigger['Material']
    trig_title    = str(trigger.get('Title', ''))
    trig_brand    = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    trig_model    = str(trigger.get('Μοντέλο', '')).strip()
    trig_port     = str(trigger.get('Θύρα USB', '')).strip()
    trig_color    = str(trigger.get('Χρώμα', '')).strip()
    trig_extras   = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    trig_os       = str(trigger.get('Λειτουργικό σύστημα', '')).lower()
    trig_hierarchy = str(trigger.get('Hierarchy', ''))
    trig_level1   = str(trigger.get('Level 1', ''))
    trig_price    = parse_euro_price(trigger.get('LIST PRICE', 0))

    # Start from all products except the trigger itself
    candidates = df_products[df_products['Material'] != trig_material].copy()

    # ─────────────────────────────────────────
    # UNIVERSAL GUARDRAILS (Global Rules Part 2)
    # Run BEFORE any scoring or slot logic.
    # ─────────────────────────────────────────

    # ── U2: Exact Duplicate & Ghost SKU Purge ──
    candidates = candidates[candidates['Title'] != trig_title]
    if 'CW Stock Units' in candidates.columns:
        candidates['CW Stock Units'] = pd.to_numeric(candidates['CW Stock Units'], errors='coerce').fillna(0)
        candidates = candidates[candidates['CW Stock Units'] > 0]

    # ── U1: Anti-Sibling Fuzzy Title Match ──
    if not config["allow_siblings"]:
        sibling_mask = (
            (candidates['Hierarchy'] == trig_hierarchy) &
            (candidates['Κατασκευαστής'].str.strip().str.upper() == trig_brand)
        )
        if sibling_mask.any():
            similarities = candidates.loc[sibling_mask, 'Title'].apply(
                lambda t: title_similarity(trig_title, str(t))
            )
            fuzzy_dupes = similarities[similarities >= 70].index
            candidates = candidates.drop(fuzzy_dupes)

    # ── U3: Macro-Category Cross-Pollination Wall ──
    if trig_level1 in TECH_CATEGORIES:
        candidates = candidates[~candidates['Level 1'].isin(APPLIANCE_CATEGORIES)]
    elif trig_level1 in APPLIANCE_CATEGORIES:
        candidates = candidates[~candidates['Level 1'].isin(TECH_CATEGORIES)]

    # ─────────────────────────────────────────
    # SCORING — History + Frequency + Avail + Smart
    # (Global Rules Part 1, Section 2)
    # ─────────────────────────────────────────

    # ── History & Frequency ──
    trigger_customers = df_history[
        df_history['Material'] == trig_material
    ]['customerEmail'].unique()

    bought_with = df_history[
        (df_history['customerEmail'].isin(trigger_customers)) &
        (df_history['Material'] != trig_material)
    ]
    frequency_df = bought_with['Material'].value_counts().reset_index()
    frequency_df.columns = ['Next_Item_ID', 'Frequency']

    candidates = candidates.merge(
        frequency_df, left_on='Material', right_on='Next_Item_ID', how='left'
    )
    candidates['Frequency'] = candidates['Frequency'].fillna(0).astype(int)

    # History Score: +2000 only if frequency >= threshold
    candidates['History_Score'] = candidates['Frequency'].apply(
        lambda f: HISTORY_BOOST if f >= HISTORY_FREQ_MIN else 0
    )

    # ── Gap 5: Price guardrail on history-boosted items ──
    # "Historical data is not exempt from the engine's core logic."
    candidates['Next_Price'] = candidates['LIST PRICE'].apply(parse_euro_price)
    history_items = candidates['History_Score'] > 0
    if history_items.any():
        price_ok = candidates.loc[history_items].apply(
            lambda row: passes_price_ceiling(trig_price, row['Next_Price'], trig_level1),
            axis=1
        )
        # Zero out history score for items that fail price check
        fail_idx = price_ok[~price_ok].index
        candidates.loc[fail_idx, 'History_Score'] = 0

    # ── Availability Boost (separate from Smart_Boost per spec) ──
    candidates['Avail_Boost'] = 0
    candidates.loc[
        candidates['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Avail_Boost'
    ] = AVAIL_BOOST

    # ── Base Smart Boosts (universal synergies) ──
    candidates['Smart_Boost'] = 0
    candidates.loc[
        candidates['Μοντέλο'] == trigger.get('Μοντέλο', ''), 'Smart_Boost'
    ] += SMART_BOOST
    candidates.loc[
        candidates['Κατασκευαστής'].str.strip().str.upper() == trig_brand, 'Smart_Boost'
    ] += SMART_BOOST

    # ── Final Score = all four components ──
    candidates['Final_Score'] = (
        candidates['History_Score']
        + candidates['Frequency']
        + candidates['Avail_Boost']
        + candidates['Smart_Boost']
    )

    # ── U5: Non-History Price Ceiling (for items WITHOUT history boost) ──
    non_history = candidates['History_Score'] == 0
    if non_history.any():
        price_ok_nh = candidates.loc[non_history].apply(
            lambda row: passes_price_ceiling(trig_price, row['Next_Price'], trig_level1),
            axis=1
        )
        fail_nh = price_ok_nh[~price_ok_nh].index
        candidates = candidates.drop(fail_nh)

    # ─────────────────────────────────────────
    # SLOT ASSIGNMENT ENGINE (with multi-rank)
    # Gap 7: Keep multiple candidates per slot
    # ─────────────────────────────────────────
    all_slot_candidates = []

    for _, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_hierarchies = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]

        # Base filter by Hierarchy
        sc = candidates[candidates['Hierarchy'].isin(allowed_hierarchies)].copy()

        # ─────────────────────────────────────
        # STRICT ATTRIBUTE LOGIC
        # ─────────────────────────────────────

        # LOGIC 1: Cases & Glass (Slots 1, 2, 7, 10)
        if slot_num in [1, 2, 7, 10]:
            if trig_model:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_model, case=False)]

            if slot_num == 1:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                # Gap 10: Exact color match, not substring
                if trig_color:
                    color_lower = trig_color.lower()
                    sc = sc[
                        sc['Χρώμα'].fillna('').str.strip().str.lower().isin(
                            [color_lower, 'διάφανο']
                        )
                    ]

            elif slot_num == 2:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό οθόνης", case=False)]

            elif slot_num == 7:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό καμερών", case=False)]

                # Slot 7 Fallback: if no camera protector, fall back to a cable
                if sc.empty and trig_port:
                    fallback_hierarchies = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS']
                    sc = candidates[candidates['Hierarchy'].isin(fallback_hierarchies)].copy()
                    sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]

            elif slot_num == 10:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains(
                    "Book Cover|Wallet|360 Full Cover", case=False
                )]

        # LOGIC 2: Chargers (Slot 3)
        elif slot_num == 3:
            if trig_port:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]

            # Speed Match
            if "γρήγορη φόρτιση" in trig_extras:
                sc = sc[sc['Ισχύς (Watt)'].fillna('').str.contains("21 - 60|61 - 100", case=False)]

            # Wireless Upsell
            if "ασύρματη φόρτιση" in trig_extras:
                sc = sc[sc['Τύπος'].fillna('').str.contains(
                    "Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", case=False
                )]
                # BOOST: Wireless charger synergy
                sc.loc[
                    sc['Τύπος'].fillna('').str.contains("Ασύρματος Φορτιστής", case=False),
                    'Final_Score'
                ] += SMART_BOOST
                # BOOST: Apple MagSafe
                if trig_brand == "APPLE":
                    sc.loc[
                        sc['Title'].fillna('').str.contains("MagSafe", case=False),
                        'Final_Score'
                    ] += SMART_BOOST
            else:
                sc = sc[sc['Τύπος'].fillna('').str.contains(
                    "Φορτιστής Πρίζας|Σετ Φόρτισης", case=False
                )]

        # LOGIC 3: Audio (Slot 4)
        elif slot_num == 4:
            if "3.5mm jack" in trig_extras:
                # BOOST 1: Hardware match
                sc.loc[
                    sc['Τύπος σύνδεσης'].fillna('').str.contains("Jack 3.5mm", case=False),
                    'Final_Score'
                ] += SMART_BOOST
                # BOOST 2: Brand lock
                sc.loc[
                    sc['Κατασκευαστής'].str.strip().str.upper() == trig_brand,
                    'Final_Score'
                ] += SMART_BOOST
            else:
                # FILTER: Bluetooth or matching USB port only
                sc = sc[sc['Τύπος σύνδεσης'].fillna('').str.contains(
                    f"Bluetooth|{trig_port}", case=False
                )]
                # BOOST: Brand lock
                sc.loc[
                    sc['Κατασκευαστής'].str.strip().str.upper() == trig_brand,
                    'Final_Score'
                ] += SMART_BOOST

        # LOGIC 4: Powerbank (Slot 5)
        elif slot_num == 5:
            if trig_port:
                sc = sc[sc['Τύπος θύρας'].fillna('').str.contains(trig_port, case=False)]

            if "γρήγορη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Ταχύτητα φόρτισης'].fillna('').str.contains("Ταχεία|Υπερταχεία", case=False) |
                    sc['Ισχύς (Watt)'].fillna('').str.contains("20|30|40|50|60", case=False),
                    'Final_Score'
                ] += SMART_BOOST

            if "ασύρματη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Ασύρματη φόρτιση", case=False),
                    'Final_Score'
                ] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[
                        sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Magsafe", case=False),
                        'Final_Score'
                    ] += SMART_BOOST

            # General brand lock
            sc.loc[
                sc['Κατασκευαστής'].str.strip().str.upper() == trig_brand,
                'Final_Score'
            ] += SMART_BOOST

        # LOGIC 6: Cross-Sell (Slot 6)
        elif slot_num == 6:
            if "με pen" in trig_extras:
                sc = sc[sc['Τύπος3'].fillna('').str.contains("Γραφίδα", case=False)]
            elif trig_brand == "APPLE":
                sc = sc[sc['Τύπος3'].fillna('').str.contains("AirTag", case=False)]
            else:
                allowed_types = "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού"
                sc = sc[sc['Τύπος3'].fillna('').str.contains(allowed_types, case=False)]

        # LOGIC 5: Wearable (Slot 8)
        elif slot_num == 8:
            if "ios" in trig_os or trig_brand == "APPLE":
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains("Apple iOS", case=False)]
            elif "android" in trig_os or trig_brand in ["SAMSUNG", "XIAOMI", "MOTOROLA"]:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains("Google Android", case=False)]

            # BOOST: Brand lock
            sc.loc[
                sc['Κατασκευαστής'].str.strip().str.upper() == trig_brand,
                'Final_Score'
            ] += SMART_BOOST

        # LOGIC: Car Holder MagSafe (Slot 9)
        elif slot_num == 9:
            if trig_brand == "APPLE" and "ασύρματη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Τρόπος τοποθέτησης'].fillna('').str.contains("Μαγνητική", case=False),
                    'Final_Score'
                ] += SMART_BOOST

        # ─────────────────────────────────────
        # RANKING: Keep ALL valid candidates for this slot
        # Gap 7: Multi-rank allocation
        # ─────────────────────────────────────
        if not sc.empty:
            sc = sc.sort_values(by='Final_Score', ascending=False).copy()
            sc['Assigned_Slot'] = slot_num
            sc['Slot_Role'] = slot_rule['Slot_Role']
            # Item_Rank: 1-based rank within this slot
            sc['Item_Rank'] = range(1, len(sc) + 1)
            # Draft_Score = (Item_Rank * 100) + Slot_Number
            sc['Draft_Score'] = sc['Item_Rank'] * 100 + slot_num
            all_slot_candidates.append(sc)

    if not all_slot_candidates:
        return pd.DataFrame()

    full_df = pd.concat(all_slot_candidates, ignore_index=True)

    # ─────────────────────────────────────────
    # S1: HIERARCHY DIVERSITY CAP (Global Rules Part 3)
    # Max N items from the same Hierarchy in the final output.
    # ─────────────────────────────────────────
    hierarchy_cap = config["hierarchy_cap"]

    # Sort by Draft_Score to get the best-first horizontal fill
    full_df = full_df.sort_values(by='Draft_Score').reset_index(drop=True)

    # Greedy selection: walk in Draft_Score order, enforce cap
    selected = []
    hierarchy_counts = {}
    seen_materials = set()

    for _, row in full_df.iterrows():
        h = row['Hierarchy']
        mat = row['Material']

        # Skip if we already selected this exact product
        if mat in seen_materials:
            continue

        # Enforce hierarchy cap
        if hierarchy_counts.get(h, 0) >= hierarchy_cap:
            continue

        selected.append(row)
        hierarchy_counts[h] = hierarchy_counts.get(h, 0) + 1
        seen_materials.add(mat)

        # Stop at 10
        if len(selected) >= 10:
            break

    if selected:
        return pd.DataFrame(selected)
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# VISUALIZATION WITH E-COMMERCE UI
# ─────────────────────────────────────────────────────────────
st.markdown(
    "### <span style='color:#ff5e00; font-weight:bold;'>|</span> Μαζί με αυτό, οι περισσότεροι αγοράζουν",
    unsafe_allow_html=True,
)

recs = calculate_recommendations(trigger, df_products, df_history, df_slots)

if not recs.empty:
    recs_to_show = recs.head(10)

    # ── Debug expander ──
    with st.expander("🔍 Debug: Score Breakdown"):
        debug_cols = [
            'Title', 'Hierarchy', 'Assigned_Slot', 'Slot_Role', 'Item_Rank',
            'History_Score', 'Frequency', 'Avail_Boost', 'Smart_Boost',
            'Final_Score', 'Draft_Score',
        ]
        available_debug = [c for c in debug_cols if c in recs_to_show.columns]
        st.dataframe(recs_to_show[available_debug], use_container_width=True)

    # ── Build HTML cards ──
    cards_html = ""
    for _, row in recs_to_show.iterrows():
        img_url = str(row.get('Thumbnails', '')).strip()

        raw_price = parse_euro_price(row.get('LIST PRICE', 0))
        new_price = f"{raw_price:.2f}".replace('.', ',')
        old_price = f"{(raw_price * 1.25):.2f}".replace('.', ',')

        raw_title = str(row.get('Title', ''))
        title = raw_title.replace('"', '&quot;').replace("'", "&#39;")

        slot_label = str(row.get('Slot_Role', ''))
        slot_num   = int(row.get('Assigned_Slot', 0))

        cards_html += f"""
        <div class="product-card">
            <div class="slot-badge">Slot {slot_num}</div>
            <img src="{img_url}" alt="product">
            <div class="title" title="{title}">{title}</div>
            <div class="slot-role">{slot_label}</div>
            <div class="reviews">
                <span class="score">4.8</span>
                <span class="stars">★★★★★</span>
                <span class="count">(305)</span>
            </div>
            <div class="old-price">Π.Λ.Τ. : {old_price}€</div>
            <div class="new-price">{new_price.split(',')[0]}<span class="decimals">,{new_price.split(',')[1]}€</span></div>
            <button class="cart-btn">🛒</button>
        </div>
        """

    # ── CSS ──
    st.markdown(f"""
    <style>
        .block-container {{ padding-top: 2rem; }}
        .product-card {{
            background: white;
            border: 1px solid #f0f0f0;
            border-radius: 12px;
            padding: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            flex-shrink: 0;
            position: relative;
        }}
        .product-card .slot-badge {{
            position: absolute;
            top: 8px;
            left: 8px;
            background: #ff5e00;
            color: white;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 6px;
        }}
        .product-card img {{
            height: 120px;
            object-fit: contain;
            margin-bottom: 15px;
        }}
        .product-card .title {{
            font-size: 13px;
            color: #333;
            text-align: center;
            height: 36px;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            margin-bottom: 10px;
        }}
        .product-card .slot-role {{
            font-size: 10px;
            color: #888;
            margin-bottom: 8px;
            text-align: center;
        }}
        .product-card .reviews {{ font-size: 11px; margin-bottom: 15px; }}
        .product-card .score {{ color: #ff5e00; font-weight: bold; }}
        .product-card .stars {{ color: #ff5e00; letter-spacing: -2px; }}
        .product-card .count {{ color: #1a73e8; }}
        .product-card .old-price {{
            font-size: 11px;
            color: #888;
            text-decoration: line-through;
            margin-bottom: 2px;
        }}
        .product-card .new-price {{
            font-size: 18px;
            font-weight: bold;
            color: #ff5e00;
            margin-bottom: 15px;
        }}
        .product-card .decimals {{ font-size: 12px; }}
        .product-card .cart-btn {{
            background-color: #ff5e00;
            color: white;
            border: none;
            border-radius: 8px;
            width: 40px;
            height: 35px;
            font-size: 16px;
            cursor: pointer;
            transition: 0.2s;
        }}
        .product-card .cart-btn:hover {{ background-color: #e65500; }}

        .desktop-carousel {{
            display: flex;
            overflow-x: auto;
            gap: 15px;
            padding-bottom: 15px;
            scrollbar-width: thin;
        }}
        .desktop-carousel .product-card {{ width: 200px; }}

        .mobile-mockup {{
            border: 12px solid #333;
            border-radius: 36px;
            padding: 15px 10px;
            background: #fafafa;
            height: 500px;
            overflow: hidden;
            position: relative;
        }}
        .mobile-carousel {{
            display: flex;
            overflow-x: auto;
            gap: 10px;
            padding-bottom: 15px;
            scrollbar-width: none;
        }}
        .mobile-carousel::-webkit-scrollbar {{ display: none; }}
        .mobile-carousel .product-card {{
            width: calc(50% - 5px);
            padding: 10px;
        }}
        .mobile-carousel .product-card img {{ height: 90px; }}
    </style>
    """, unsafe_allow_html=True)

    # ── Split view ──
    col_desktop, col_spacer, col_mobile = st.columns([2.5, 0.2, 1.3])

    with col_desktop:
        st.write("##### 💻 Web View (Scroll to see all 10)")
        st.markdown(f'<div class="desktop-carousel">{cards_html}</div>', unsafe_allow_html=True)

    with col_mobile:
        st.write("##### 📱 Mobile View (2 items visible)")
        st.markdown(f"""
        <div class="mobile-mockup">
            <div style="text-align:center; font-weight:bold; font-size:18px; margin-bottom:15px; line-height:1.2;">
                <span style="color:#ff5e00;">—</span><br>Μαζί με αυτό, οι<br>περισσότεροι αγοράζουν
            </div>
            <div class="mobile-carousel">{cards_html}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.warning("No recommendations found. Check your data and compatibility mapping.")
