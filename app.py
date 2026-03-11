import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
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

# Scoring weights — spec says flat +100 per synergy rule.
# Change these if you want variable weights (document the reason).
SMART_BOOST      = 100
AVAIL_BOOST      = 50
HISTORY_BOOST    = 2000
HISTORY_FREQ_MIN = 3

# Macro-category walls (Global Rules U3)
TECH_CATEGORIES      = {"IT", "Telephony", "TV"}
APPLIANCE_CATEGORIES = {"MDA", "SDA", "Air Condition", "Personal Care"}

# Column name config — change here if your sheet uses a different name
COL_COMPATIBLE = "Συμβατό με"  # Spec says "Συμβατή συσκευή" — verify your sheet


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
# Spec: Level 2 == 'Mobiles' AND Hierarchy == 'Smart phones'
# ─────────────────────────────────────────────────────────────
phones = df_products[
    (df_products['Level 2'] == 'Mobiles') &
    (df_products['Hierarchy'] == 'Smart phones')
]

# Fallback: if the strict filter returns nothing, relax to Level 2 only
if phones.empty:
    phones = df_products[df_products['Level 2'] == 'Mobiles']
    st.sidebar.warning("⚠ No 'Smart phones' hierarchy found — falling back to all Mobiles.")

selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]

st.subheader(f"Building the perfect loadout for: {selected_phone_name}")


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def title_similarity(a: str, b: str) -> float:
    """Return 0-100 similarity score between two titles."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


def parse_euro_price(val) -> float:
    """Parse a European-format price string into a float."""
    s = str(val).replace('€', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0


def passes_price_ceiling(trigger_price: float, next_price: float, trigger_level1: str) -> bool:
    """
    Condition A: Peer categories -> up to 150% of trigger.
    Condition B: Trigger price <= 30 -> up to 150%.
    Condition C: Otherwise -> next_price <= max(trigger * 0.40, 45).
    """
    if next_price <= 0 or trigger_price <= 0:
        return True  # Can't evaluate — let it through

    peer_categories = {"Books", "Stationery", "Toys", "Music & Films", "Gaming"}

    if trigger_level1 in peer_categories:
        return next_price <= trigger_price * 1.5
    elif trigger_price <= 30:
        return next_price <= trigger_price * 1.5
    else:
        ceiling = max(trigger_price * 0.40, 45)
        return next_price <= ceiling


def safe_html(val) -> str:
    """Escape any value for safe HTML embedding."""
    return html_lib.escape(str(val))


# ─────────────────────────────────────────────────────────────
# THE MAIN ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_recommendations(trigger, df_products, df_history, df_slots):
    config = CLUSTER_CONFIG[ACTIVE_CLUSTER]
    diag = {}  # Diagnostic counters

    # ── Trigger attributes (safe extraction) ──
    trig_material  = trigger['Material']
    trig_title     = str(trigger.get('Title', ''))
    trig_brand     = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    trig_model     = str(trigger.get('Μοντέλο', '')).strip()
    trig_port      = str(trigger.get('Θύρα USB', '')).strip()
    trig_color     = str(trigger.get('Χρώμα', '')).strip()
    trig_extras    = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    trig_os        = str(trigger.get('Λειτουργικό σύστημα', '')).lower()
    trig_hierarchy = str(trigger.get('Hierarchy', ''))
    trig_level1    = str(trigger.get('Level 1', ''))
    trig_price     = parse_euro_price(trigger.get('LIST PRICE', 0))

    # Start from all products except the trigger Material
    candidates = df_products[df_products['Material'] != trig_material].copy()
    diag['0_start'] = len(candidates)

    # ─────────────────────────────────────────
    # UNIVERSAL GUARDRAILS (Global Rules Part 2)
    # ─────────────────────────────────────────

    # ── U2a: Exact title duplicate purge ──
    candidates = candidates[candidates['Title'] != trig_title]
    diag['1_after_U2a_title_dedup'] = len(candidates)

    # ── U2b: Ghost SKU purge (zero stock) ──
    # DEFENSIVE: Only filter if column exists AND has meaningful data.
    # If <10% of rows have stock > 0, the column is likely unpopulated -> skip.
    if 'CW Stock Units' in candidates.columns:
        stock_col = pd.to_numeric(candidates['CW Stock Units'], errors='coerce')
        pct_populated = (stock_col > 0).sum() / len(candidates) if len(candidates) > 0 else 0
        if pct_populated >= 0.10:
            candidates['CW Stock Units'] = stock_col.fillna(0)
            candidates = candidates[candidates['CW Stock Units'] > 0]
            diag['2_after_U2b_stock'] = len(candidates)
            diag['2_stock_note'] = f"Applied ({pct_populated:.0%} populated)"
        else:
            diag['2_after_U2b_stock'] = len(candidates)
            diag['2_stock_note'] = f"SKIPPED — only {pct_populated:.0%} populated"
    else:
        diag['2_after_U2b_stock'] = len(candidates)
        diag['2_stock_note'] = "SKIPPED — column not found"

    # ── U1: Anti-Sibling Fuzzy Title Match ──
    if not config["allow_siblings"]:
        sibling_mask = (
            (candidates['Hierarchy'] == trig_hierarchy)
            & (candidates['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand)
        )
        if sibling_mask.any():
            similarities = candidates.loc[sibling_mask, 'Title'].apply(
                lambda t: title_similarity(trig_title, str(t))
            )
            fuzzy_dupes = similarities[similarities >= 70].index
            candidates = candidates.drop(fuzzy_dupes)
    diag['3_after_U1_siblings'] = len(candidates)

    # ── U3: Macro-Category Cross-Pollination Wall ──
    if trig_level1 in TECH_CATEGORIES:
        candidates = candidates[~candidates['Level 1'].isin(APPLIANCE_CATEGORIES)]
    elif trig_level1 in APPLIANCE_CATEGORIES:
        candidates = candidates[~candidates['Level 1'].isin(TECH_CATEGORIES)]
    diag['4_after_U3_macro_wall'] = len(candidates)

    # ─────────────────────────────────────────
    # SCORING
    # ─────────────────────────────────────────

    # ── History & Frequency ──
    trigger_customers = df_history[
        df_history['Material'] == trig_material
    ]['customerEmail'].unique()

    bought_with = df_history[
        (df_history['customerEmail'].isin(trigger_customers))
        & (df_history['Material'] != trig_material)
    ]
    frequency_df = bought_with['Material'].value_counts().reset_index()
    frequency_df.columns = ['Next_Item_ID', 'Frequency']

    candidates = candidates.merge(
        frequency_df, left_on='Material', right_on='Next_Item_ID', how='left'
    )
    candidates['Frequency'] = candidates['Frequency'].fillna(0).astype(int)
    candidates['History_Score'] = candidates['Frequency'].apply(
        lambda f: HISTORY_BOOST if f >= HISTORY_FREQ_MIN else 0
    )

    # ── Parse prices for ceiling checks ──
    candidates['Next_Price'] = candidates['LIST PRICE'].apply(parse_euro_price)

    # ── Price guardrail on history-boosted items ──
    history_mask = candidates['History_Score'] > 0
    if history_mask.any():
        price_ok = candidates.loc[history_mask].apply(
            lambda row: passes_price_ceiling(trig_price, row['Next_Price'], trig_level1),
            axis=1,
        )
        candidates.loc[price_ok[~price_ok].index, 'History_Score'] = 0

    # ── Availability Boost ──
    candidates['Avail_Boost'] = 0
    candidates.loc[
        candidates['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Avail_Boost'
    ] = AVAIL_BOOST

    # ── Base Smart Boosts ──
    candidates['Smart_Boost'] = 0
    candidates.loc[
        candidates['Μοντέλο'] == trigger.get('Μοντέλο', ''), 'Smart_Boost'
    ] += SMART_BOOST
    candidates.loc[
        candidates['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand,
        'Smart_Boost',
    ] += SMART_BOOST

    # ── Final Score ──
    candidates['Final_Score'] = (
        candidates['History_Score']
        + candidates['Frequency']
        + candidates['Avail_Boost']
        + candidates['Smart_Boost']
    )

    # ── U5: Non-History Price Ceiling ──
    non_history_mask = candidates['History_Score'] == 0
    if non_history_mask.any():
        price_ok_nh = candidates.loc[non_history_mask].apply(
            lambda row: passes_price_ceiling(trig_price, row['Next_Price'], trig_level1),
            axis=1,
        )
        candidates = candidates.drop(price_ok_nh[~price_ok_nh].index)
    diag['5_after_U5_price_ceiling'] = len(candidates)

    # ─────────────────────────────────────────
    # SLOT ASSIGNMENT (multi-rank)
    # ─────────────────────────────────────────
    all_slot_candidates = []
    slot_diag = {}

    for _, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_hierarchies = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]

        sc = candidates[candidates['Hierarchy'].isin(allowed_hierarchies)].copy()
        slot_diag[f"slot_{slot_num}_after_hierarchy"] = len(sc)

        # ───────────────────────────────
        # STRICT ATTRIBUTE LOGIC
        # ───────────────────────────────

        # LOGIC 1: Cases & Glass (Slots 1, 2, 7, 10)
        if slot_num in [1, 2, 7, 10]:
            if trig_model:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_model, case=False)]

            if slot_num == 1:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                if trig_color:
                    color_lower = trig_color.lower()
                    sc = sc[
                        sc['Χρώμα'].fillna('').str.strip().str.lower().isin(
                            [color_lower, 'διάφανο']
                        )
                    ]

            elif slot_num == 2:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains(
                    "Προστατευτικό οθόνης", case=False
                )]

            elif slot_num == 7:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains(
                    "Προστατευτικό καμερών", case=False
                )]
                # Fallback: cable matching phone's port
                if sc.empty and trig_port:
                    fallback_h = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS']
                    sc = candidates[candidates['Hierarchy'].isin(fallback_h)].copy()
                    sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]

            elif slot_num == 10:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains(
                    "Book Cover|Wallet|360 Full Cover", case=False
                )]

        # LOGIC 2: Chargers (Slot 3)
        elif slot_num == 3:
            if trig_port:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]
            if "γρήγορη φόρτιση" in trig_extras:
                sc = sc[sc['Ισχύς (Watt)'].fillna('').str.contains(
                    "21 - 60|61 - 100", case=False
                )]
            if "ασύρματη φόρτιση" in trig_extras:
                sc = sc[sc['Τύπος3'].fillna('').str.contains(
                    "Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", case=False
                )]
                sc.loc[
                    sc['Τύπος3'].fillna('').str.contains("Ασύρματος Φορτιστής", case=False),
                    'Final_Score',
                ] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[
                        sc['Title'].fillna('').str.contains("MagSafe", case=False),
                        'Final_Score',
                    ] += SMART_BOOST
            else:
                sc = sc[sc['Τύπος3'].fillna('').str.contains(
                    "Φορτιστής Πρίζας|Σετ Φόρτισης", case=False
                )]

        # LOGIC 3: Audio (Slot 4)
        elif slot_num == 4:
            if "3.5mm jack" in trig_extras:
                sc.loc[
                    sc['Τύπος σύνδεσης'].fillna('').str.contains("Jack 3.5mm", case=False),
                    'Final_Score',
                ] += SMART_BOOST
                sc.loc[
                    sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand,
                    'Final_Score',
                ] += SMART_BOOST
            else:
                sc = sc[sc['Τύπος σύνδεσης'].fillna('').str.contains(
                    f"Bluetooth|{trig_port}", case=False
                )]
                sc.loc[
                    sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand,
                    'Final_Score',
                ] += SMART_BOOST

        # LOGIC 4: Powerbank (Slot 5)
        elif slot_num == 5:
            if trig_port:
                sc = sc[sc['Τύπος θύρας'].fillna('').str.contains(trig_port, case=False)]
            if "γρήγορη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Ταχύτητα φόρτισης'].fillna('').str.contains(
                        "Ταχεία|Υπερταχεία", case=False
                    )
                    | sc['Ισχύς (Watt)'].fillna('').str.contains(
                        "20|30|40|50|60", case=False
                    ),
                    'Final_Score',
                ] += SMART_BOOST
            if "ασύρματη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Extra Χαρακτηριστικά'].fillna('').str.contains(
                        "Ασύρματη φόρτιση", case=False
                    ),
                    'Final_Score',
                ] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[
                        sc['Extra Χαρακτηριστικά'].fillna('').str.contains(
                            "Magsafe", case=False
                        ),
                        'Final_Score',
                    ] += SMART_BOOST
            sc.loc[
                sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand,
                'Final_Score',
            ] += SMART_BOOST

        # LOGIC 6: Cross-Sell (Slot 6)
        elif slot_num == 6:
            if "με pen" in trig_extras:
                sc = sc[sc['Τύπος3'].fillna('').str.contains("Γραφίδα", case=False)]
            elif trig_brand == "APPLE":
                sc = sc[sc['Τύπος3'].fillna('').str.contains("AirTag", case=False)]
            else:
                allowed_types = (
                    "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone"
                    "|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού"
                )
                sc = sc[sc['Τύπος3'].fillna('').str.contains(allowed_types, case=False)]

        # LOGIC 5: Wearable (Slot 8)
        elif slot_num == 8:
            if "ios" in trig_os or trig_brand == "APPLE":
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains("Apple iOS", case=False)]
            elif "android" in trig_os or trig_brand in [
                "SAMSUNG", "XIAOMI", "MOTOROLA",
            ]:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(
                    "Google Android", case=False
                )]
            sc.loc[
                sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand,
                'Final_Score',
            ] += SMART_BOOST

        # Car Holder MagSafe (Slot 9)
        elif slot_num == 9:
            if trig_brand == "APPLE" and "ασύρματη φόρτιση" in trig_extras:
                sc.loc[
                    sc['Τρόπος τοποθέτησης'].fillna('').str.contains(
                        "Μαγνητική", case=False
                    ),
                    'Final_Score',
                ] += SMART_BOOST

        # ── Rank & keep ALL valid candidates per slot ──
        slot_diag[f"slot_{slot_num}_after_attr"] = len(sc)

        if not sc.empty:
            sc = sc.sort_values(by='Final_Score', ascending=False).copy()
            sc['Assigned_Slot'] = slot_num
            sc['Slot_Role'] = slot_rule['Slot_Role']
            sc['Item_Rank'] = range(1, len(sc) + 1)
            sc['Draft_Score'] = sc['Item_Rank'] * 100 + slot_num
            all_slot_candidates.append(sc)

    if not all_slot_candidates:
        return pd.DataFrame(), diag, slot_diag

    full_df = pd.concat(all_slot_candidates, ignore_index=True)

    # ─────────────────────────────────────────
    # S1: HIERARCHY DIVERSITY CAP
    # ─────────────────────────────────────────
    hierarchy_cap = config["hierarchy_cap"]
    full_df = full_df.sort_values(by='Draft_Score').reset_index(drop=True)

    selected = []
    hierarchy_counts = {}
    seen_materials = set()

    for _, row in full_df.iterrows():
        h   = row['Hierarchy']
        mat = row['Material']

        if mat in seen_materials:
            continue
        if hierarchy_counts.get(h, 0) >= hierarchy_cap:
            continue

        selected.append(row)
        hierarchy_counts[h] = hierarchy_counts.get(h, 0) + 1
        seen_materials.add(mat)

        if len(selected) >= 10:
            break

    diag['6_final_selected'] = len(selected)

    if selected:
        return pd.DataFrame(selected), diag, slot_diag
    return pd.DataFrame(), diag, slot_diag


# ─────────────────────────────────────────────────────────────
# RUN THE ENGINE
# ─────────────────────────────────────────────────────────────
st.markdown(
    "### <span style='color:#ff5e00; font-weight:bold;'>|</span> "
    "Μαζί με αυτό, οι περισσότεροι αγοράζουν",
    unsafe_allow_html=True,
)

recs, diag, slot_diag = calculate_recommendations(
    trigger, df_products, df_history, df_slots
)

# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS PANEL
# ─────────────────────────────────────────────────────────────
with st.expander("🔍 Debug: Score Breakdown"):
    if not recs.empty:
        debug_cols = [
            'Title', 'Hierarchy', 'Assigned_Slot', 'Slot_Role', 'Item_Rank',
            'History_Score', 'Frequency', 'Avail_Boost', 'Smart_Boost',
            'Final_Score', 'Draft_Score',
        ]
        available_debug = [c for c in debug_cols if c in recs.columns]
        st.dataframe(recs[available_debug], use_container_width=True)
    else:
        st.warning("No recommendations produced.")

with st.expander("🩺 Debug: Guardrail Funnel (where are candidates dropping?)"):
    st.markdown("**Candidate count after each guardrail step:**")
    funnel_data = {
        "Step": [
            "0. Starting pool (excl. trigger Material)",
            "1. After U2a: exact title dedup",
            f"2. After U2b: stock filter ({diag.get('2_stock_note', '?')})",
            "3. After U1: anti-sibling fuzzy match",
            "4. After U3: macro-category wall",
            "5. After U5: non-history price ceiling",
            "6. Final selected (after slots + S1 cap)",
        ],
        "Count": [
            diag.get('0_start', '?'),
            diag.get('1_after_U2a_title_dedup', '?'),
            diag.get('2_after_U2b_stock', '?'),
            diag.get('3_after_U1_siblings', '?'),
            diag.get('4_after_U3_macro_wall', '?'),
            diag.get('5_after_U5_price_ceiling', '?'),
            diag.get('6_final_selected', '?'),
        ],
    }
    st.table(pd.DataFrame(funnel_data))

    st.markdown("**Per-slot candidate counts (hierarchy filter -> attribute filter):**")
    slot_rows = []
    for key in sorted(slot_diag.keys()):
        slot_rows.append({"Check": key, "Count": slot_diag[key]})
    if slot_rows:
        st.table(pd.DataFrame(slot_rows))

with st.expander("📋 Debug: Trigger Attributes"):
    trig_info = {
        "Material": trigger['Material'],
        "Title": trigger.get('Title', ''),
        "Level 1": trigger.get('Level 1', ''),
        "Level 2": trigger.get('Level 2', ''),
        "Hierarchy": trigger.get('Hierarchy', ''),
        "Κατασκευαστής": trigger.get('Κατασκευαστής', ''),
        "Μοντέλο": trigger.get('Μοντέλο', ''),
        "Θύρα USB": trigger.get('Θύρα USB', ''),
        "Χρώμα": trigger.get('Χρώμα', ''),
        "Λειτουργικό σύστημα": trigger.get('Λειτουργικό σύστημα', ''),
        "Extra Χαρακτηριστικά": trigger.get('Extra Χαρακτηριστικά', ''),
        "LIST PRICE": trigger.get('LIST PRICE', ''),
    }
    for k, v in trig_info.items():
        st.text(f"{k}: {v}")


# ─────────────────────────────────────────────────────────────
# VISUALIZATION
# ─────────────────────────────────────────────────────────────
if not recs.empty:
    recs_to_show = recs.head(10)

    # ── Build HTML cards with proper escaping ──
    cards_html = ""
    for _, row in recs_to_show.iterrows():
        img_url    = safe_html(str(row.get('Thumbnails', '')).strip())
        raw_price  = parse_euro_price(row.get('LIST PRICE', 0))
        new_price  = f"{raw_price:.2f}".replace('.', ',')
        old_price  = f"{(raw_price * 1.25):.2f}".replace('.', ',')
        title      = safe_html(str(row.get('Title', '')))
        slot_label = safe_html(str(row.get('Slot_Role', '')))
        slot_num   = int(row.get('Assigned_Slot', 0))

        cards_html += f"""
        <div class="product-card">
            <div class="slot-badge">Slot {slot_num}</div>
            <img src="{img_url}" alt="product">
            <div class="title" title="{title}">{title}</div>
            <div class="slot-role">{slot_label}</div>
            <div class="reviews">
                <span class="score">4.8</span>
                <span class="stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span>
                <span class="count">(305)</span>
            </div>
            <div class="old-price">&Pi;.&Lambda;.&Tau;. : {old_price}&euro;</div>
            <div class="new-price">{new_price.split(',')[0]}<span class="decimals">,{new_price.split(',')[1]}&euro;</span></div>
            <button class="cart-btn">&#128722;</button>
        </div>
        """

    # ── Shared CSS (used by both carousels) ──
    shared_card_css = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: transparent; }
        .product-card {
            background: white; border: 1px solid #f0f0f0; border-radius: 12px;
            padding: 15px; display: flex; flex-direction: column; align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); flex-shrink: 0; position: relative;
        }
        .slot-badge {
            position: absolute; top: 8px; left: 8px; background: #ff5e00;
            color: white; font-size: 10px; font-weight: bold;
            padding: 2px 8px; border-radius: 6px;
        }
        .product-card img { height: 120px; object-fit: contain; margin-bottom: 15px; }
        .title {
            font-size: 13px; color: #333; text-align: center; height: 36px;
            overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2;
            -webkit-box-orient: vertical; margin-bottom: 10px;
        }
        .slot-role { font-size: 10px; color: #888; margin-bottom: 8px; text-align: center; }
        .reviews { font-size: 11px; margin-bottom: 15px; }
        .score { color: #ff5e00; font-weight: bold; }
        .stars { color: #ff5e00; letter-spacing: -2px; }
        .count { color: #1a73e8; }
        .old-price { font-size: 11px; color: #888; text-decoration: line-through; margin-bottom: 2px; }
        .new-price { font-size: 18px; font-weight: bold; color: #ff5e00; margin-bottom: 15px; }
        .decimals { font-size: 12px; }
        .cart-btn {
            background-color: #ff5e00; color: white; border: none; border-radius: 8px;
            width: 40px; height: 35px; font-size: 16px; cursor: pointer;
        }
        .cart-btn:hover { background-color: #e65500; }
    """

    # ── Desktop carousel (standalone HTML -> components.html) ──
    desktop_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{shared_card_css}
.desktop-carousel {{
    display: flex; overflow-x: auto; gap: 15px;
    padding: 10px 5px 15px 5px; scrollbar-width: thin;
}}
.desktop-carousel .product-card {{ width: 200px; min-width: 200px; }}
</style></head><body>
<div class="desktop-carousel">{cards_html}</div>
</body></html>"""

    # ── Mobile mockup (standalone HTML -> components.html) ──
    mobile_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
{shared_card_css}
.mobile-mockup {{
    border: 12px solid #333; border-radius: 36px; padding: 15px 10px;
    background: #fafafa; height: 470px; overflow: hidden; position: relative;
}}
.mobile-header {{
    text-align: center; font-weight: bold; font-size: 18px;
    margin-bottom: 15px; line-height: 1.2;
}}
.mobile-carousel {{
    display: flex; overflow-x: auto; gap: 10px; padding-bottom: 15px;
    scrollbar-width: none;
}}
.mobile-carousel::-webkit-scrollbar {{ display: none; }}
.mobile-carousel .product-card {{
    width: calc(50% - 5px); min-width: calc(50% - 5px); padding: 10px;
}}
.mobile-carousel .product-card img {{ height: 90px; }}
.mobile-carousel .title {{ font-size: 11px; height: 30px; }}
.mobile-carousel .slot-role {{ font-size: 9px; }}
.mobile-carousel .reviews {{ font-size: 10px; }}
.mobile-carousel .old-price {{ font-size: 10px; }}
.mobile-carousel .new-price {{ font-size: 16px; }}
.mobile-carousel .decimals {{ font-size: 11px; }}
.mobile-carousel .cart-btn {{ width: 36px; height: 32px; font-size: 14px; }}
.mobile-carousel .slot-badge {{ font-size: 9px; padding: 2px 6px; }}
</style></head><body>
<div class="mobile-mockup">
    <div class="mobile-header">
        <span style="color:#ff5e00;">&mdash;</span><br>
        &Mu;&alpha;&zeta;ί &mu;&epsilon; &alpha;&upsilon;&tau;ό, &omicron;&iota;<br>
        &pi;&epsilon;&rho;&iota;&sigma;&sigma;ό&tau;&epsilon;&rho;&omicron;&iota; &alpha;&gamma;&omicron;&rho;ά&zeta;&omicron;&upsilon;&nu;
    </div>
    <div class="mobile-carousel">{cards_html}</div>
</div>
</body></html>"""

    # ── Render with components.html (avoids Streamlit markdown truncation) ──
    col_desktop, col_spacer, col_mobile = st.columns([2.5, 0.2, 1.3])

    with col_desktop:
        st.write("##### 💻 Web View (Scroll to see all 10)")
        components.html(desktop_html, height=380, scrolling=True)

    with col_mobile:
        st.write("##### 📱 Mobile View (2 items visible)")
        components.html(mobile_html, height=520, scrolling=False)

else:
    st.warning("No recommendations found. Check the diagnostic panels above.")
