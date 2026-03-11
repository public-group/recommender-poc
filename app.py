import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
from difflib import SequenceMatcher

st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# ═══════════════════════════════════════════════════════════════
# VERSION BANNER — if you don't see this, you're running old code
# ═══════════════════════════════════════════════════════════════
st.info("🟢 **Engine v3.0** — If you don't see this banner, you are running old code. Clear Streamlit cache (⋮ menu → Clear cache) and hard-refresh your browser (Ctrl+Shift+R).")

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

COL_COMPATIBLE = "Συμβατό με"


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
    return df_p, df_h, df_s

df_products, df_history, df_slots = load_data()

st.title("📱 Smartphone Recommendation Tool")


# ─────────────────────────────────────────────────────────────
# TRIGGER SELECTION
# ─────────────────────────────────────────────────────────────
phones = df_products[
    (df_products['Level 2'] == 'Mobiles') &
    (df_products['Hierarchy'] == 'Smart phones')
]
if phones.empty:
    phones = df_products[df_products['Level 2'] == 'Mobiles']
    st.sidebar.warning("⚠ 'Smart phones' hierarchy not found — using all Mobiles")

selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]
st.subheader(f"Building the perfect loadout for: {selected_phone_name}")


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100

def parse_euro_price(val) -> float:
    s = str(val).replace('€', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

def passes_price_ceiling(trigger_price: float, next_price: float, trigger_level1: str) -> bool:
    if next_price <= 0 or trigger_price <= 0:
        return True
    peer_categories = {"Books", "Stationery", "Toys", "Music & Films", "Gaming"}
    if trigger_level1 in peer_categories:
        return next_price <= trigger_price * 1.5
    elif trigger_price <= 30:
        return next_price <= trigger_price * 1.5
    else:
        ceiling = max(trigger_price * 0.40, 45)
        return next_price <= ceiling

def safe(val) -> str:
    return html_lib.escape(str(val))


# ─────────────────────────────────────────────────────────────
# THE ENGINE
# ─────────────────────────────────────────────────────────────
def calculate_recommendations(trigger, df_products, df_history, df_slots):
    config = CLUSTER_CONFIG[ACTIVE_CLUSTER]
    diag = []  # List of (step_name, count, note) tuples

    # ── Trigger attributes ──
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

    c = df_products[df_products['Material'] != trig_material].copy()
    diag.append(("0. Start (excl trigger Material)", len(c), ""))

    # ── U2a: Exact title dedup ──
    c = c[c['Title'] != trig_title]
    diag.append(("1. U2a: exact title dedup", len(c), ""))

    # ── U2b: Ghost SKU (zero stock) — DEFENSIVE ──
    if 'CW Stock Units' in c.columns:
        stock = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        n_with_stock = (stock > 0).sum()
        pct = n_with_stock / len(c) if len(c) > 0 else 0
        if pct >= 0.10:
            c['CW Stock Units'] = stock.fillna(0)
            c = c[c['CW Stock Units'] > 0]
            diag.append(("2. U2b: stock filter", len(c), f"APPLIED ({pct:.0%} had stock)"))
        else:
            diag.append(("2. U2b: stock filter", len(c), f"⚠ SKIPPED (only {pct:.0%} had stock > 0, threshold 10%)"))
    else:
        diag.append(("2. U2b: stock filter", len(c), "⚠ SKIPPED (column missing)"))

    # ── U1: Anti-Sibling ──
    if not config["allow_siblings"]:
        mask = (
            (c['Hierarchy'] == trig_hierarchy) &
            (c['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand)
        )
        n_siblings = mask.sum()
        if mask.any():
            sims = c.loc[mask, 'Title'].apply(lambda t: title_similarity(trig_title, str(t)))
            dupes = sims[sims >= 70].index
            c = c.drop(dupes)
            diag.append(("3. U1: anti-sibling", len(c), f"Checked {n_siblings} siblings, removed {len(dupes)}"))
        else:
            diag.append(("3. U1: anti-sibling", len(c), "No siblings found"))
    else:
        diag.append(("3. U1: anti-sibling", len(c), "Bypassed (allow_siblings=True)"))

    # ── U3: Macro-category wall ──
    before_u3 = len(c)
    if trig_level1 in TECH_CATEGORIES:
        c = c[~c['Level 1'].isin(APPLIANCE_CATEGORIES)]
    elif trig_level1 in APPLIANCE_CATEGORIES:
        c = c[~c['Level 1'].isin(TECH_CATEGORIES)]
    diag.append(("4. U3: macro-category wall", len(c), f"Removed {before_u3 - len(c)} cross-category items"))

    # ── Scoring ──
    trigger_customers = df_history[df_history['Material'] == trig_material]['customerEmail'].unique()
    bought_with = df_history[
        (df_history['customerEmail'].isin(trigger_customers)) &
        (df_history['Material'] != trig_material)
    ]
    freq_df = bought_with['Material'].value_counts().reset_index()
    freq_df.columns = ['Next_Item_ID', 'Frequency']

    c = c.merge(freq_df, left_on='Material', right_on='Next_Item_ID', how='left')
    c['Frequency'] = c['Frequency'].fillna(0).astype(int)
    c['History_Score'] = c['Frequency'].apply(lambda f: HISTORY_BOOST if f >= HISTORY_FREQ_MIN else 0)
    c['Next_Price'] = c['LIST PRICE'].apply(parse_euro_price)

    # Price guardrail on history items
    h_mask = c['History_Score'] > 0
    if h_mask.any():
        ok = c.loc[h_mask].apply(lambda r: passes_price_ceiling(trig_price, r['Next_Price'], trig_level1), axis=1)
        c.loc[ok[~ok].index, 'History_Score'] = 0

    c['Avail_Boost'] = 0
    c.loc[c['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Avail_Boost'] = AVAIL_BOOST

    c['Smart_Boost'] = 0
    c.loc[c['Μοντέλο'] == trigger.get('Μοντέλο', ''), 'Smart_Boost'] += SMART_BOOST
    c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Smart_Boost'] += SMART_BOOST

    c['Final_Score'] = c['History_Score'] + c['Frequency'] + c['Avail_Boost'] + c['Smart_Boost']

    # ── U5: Non-history price ceiling ──
    before_u5 = len(c)
    nh_mask = c['History_Score'] == 0
    if nh_mask.any():
        ok_nh = c.loc[nh_mask].apply(lambda r: passes_price_ceiling(trig_price, r['Next_Price'], trig_level1), axis=1)
        drop_idx = ok_nh[~ok_nh].index
        c = c.drop(drop_idx)
    diag.append(("5. U5: price ceiling", len(c), f"Removed {before_u5 - len(c)} over-priced items (trigger: €{trig_price:.2f}, ceiling: €{max(trig_price*0.40, 45):.2f})"))

    # ─────────────────────────────────────────
    # SLOT ASSIGNMENT
    # ─────────────────────────────────────────
    all_slot = []
    slot_diag = []

    for _, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_h = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]

        sc = c[c['Hierarchy'].isin(allowed_h)].copy()
        after_h = len(sc)

        # ── ATTRIBUTE LOGIC ──
        if slot_num in [1, 2, 7, 10]:
            if trig_model:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_model, case=False)]
            if slot_num == 1:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                if trig_color:
                    sc = sc[sc['Χρώμα'].fillna('').str.strip().str.lower().isin([trig_color.lower(), 'διάφανο'])]
            elif slot_num == 2:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό οθόνης", case=False)]
            elif slot_num == 7:
                sc = sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό καμερών", case=False)]
                if sc.empty and trig_port:
                    fb_h = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS']
                    sc = c[c['Hierarchy'].isin(fb_h)].copy()
                    sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]
            elif slot_num == 10:
                sc = sc[sc['Τύπος Θήκης'].fillna('').str.contains("Book Cover|Wallet|360 Full Cover", case=False)]

        elif slot_num == 3:
            if trig_port:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains(trig_port, case=False)]
            if "γρήγορη φόρτιση" in trig_extras:
                sc = sc[sc['Ισχύς (Watt)'].fillna('').str.contains("21 - 60|61 - 100", case=False)]
            if "ασύρματη φόρτιση" in trig_extras:
                sc = sc[sc['Τύπος3'].fillna('').str.contains("Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", case=False)]
                sc.loc[sc['Τύπος3'].fillna('').str.contains("Ασύρματος Φορτιστής", case=False), 'Final_Score'] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[sc['Title'].fillna('').str.contains("MagSafe", case=False), 'Final_Score'] += SMART_BOOST
            else:
                sc = sc[sc['Τύπος3'].fillna('').str.contains("Φορτιστής Πρίζας|Σετ Φόρτισης", case=False)]

        elif slot_num == 4:
            if "3.5mm jack" in trig_extras:
                sc.loc[sc['Τύπος σύνδεσης'].fillna('').str.contains("Jack 3.5mm", case=False), 'Final_Score'] += SMART_BOOST
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST
            else:
                sc = sc[sc['Τύπος σύνδεσης'].fillna('').str.contains(f"Bluetooth|{trig_port}", case=False)]
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

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
                sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Ασύρματη φόρτιση", case=False), 'Final_Score'] += SMART_BOOST
                if trig_brand == "APPLE":
                    sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Magsafe", case=False), 'Final_Score'] += SMART_BOOST
            sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

        elif slot_num == 6:
            if "με pen" in trig_extras:
                sc = sc[sc['Τύπος3'].fillna('').str.contains("Γραφίδα", case=False)]
            elif trig_brand == "APPLE":
                sc = sc[sc['Τύπος3'].fillna('').str.contains("AirTag", case=False)]
            else:
                sc = sc[sc['Τύπος3'].fillna('').str.contains(
                    "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού", case=False
                )]

        elif slot_num == 8:
            if "ios" in trig_os or trig_brand == "APPLE":
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains("Apple iOS", case=False)]
            elif "android" in trig_os or trig_brand in ["SAMSUNG", "XIAOMI", "MOTOROLA"]:
                sc = sc[sc[COL_COMPATIBLE].fillna('').str.contains("Google Android", case=False)]
            sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper() == trig_brand, 'Final_Score'] += SMART_BOOST

        elif slot_num == 9:
            if trig_brand == "APPLE" and "ασύρματη φόρτιση" in trig_extras:
                sc.loc[sc['Τρόπος τοποθέτησης'].fillna('').str.contains("Μαγνητική", case=False), 'Final_Score'] += SMART_BOOST

        after_attr = len(sc)
        slot_diag.append((slot_num, slot_rule.get('Slot_Role', ''), after_h, after_attr))

        if not sc.empty:
            sc = sc.sort_values(by='Final_Score', ascending=False).copy()
            sc['Assigned_Slot'] = slot_num
            sc['Slot_Role'] = slot_rule['Slot_Role']
            sc['Item_Rank'] = range(1, len(sc) + 1)
            sc['Draft_Score'] = sc['Item_Rank'] * 100 + slot_num
            all_slot.append(sc)

    if not all_slot:
        return pd.DataFrame(), diag, slot_diag

    full = pd.concat(all_slot, ignore_index=True)

    # ── S1: Hierarchy diversity cap ──
    hcap = config["hierarchy_cap"]
    full = full.sort_values(by='Draft_Score').reset_index(drop=True)

    selected = []
    h_counts = {}
    seen = set()

    for _, row in full.iterrows():
        h, mat = row['Hierarchy'], row['Material']
        if mat in seen:
            continue
        if h_counts.get(h, 0) >= hcap:
            continue
        selected.append(row)
        h_counts[h] = h_counts.get(h, 0) + 1
        seen.add(mat)
        if len(selected) >= 10:
            break

    diag.append(("6. Final (after slots + S1 cap)", len(selected), f"Hierarchy cap = {hcap}"))

    if selected:
        return pd.DataFrame(selected), diag, slot_diag
    return pd.DataFrame(), diag, slot_diag


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
st.markdown("### <span style='color:#ff5e00; font-weight:bold;'>|</span> Μαζί με αυτό, οι περισσότεροι αγοράζουν", unsafe_allow_html=True)

recs, diag, slot_diag = calculate_recommendations(trigger, df_products, df_history, df_slots)


# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS — ALWAYS VISIBLE (not in expanders)
# ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🩺 Diagnostics")

# Guardrail funnel
st.markdown("### Guardrail Funnel")
funnel_df = pd.DataFrame(diag, columns=["Step", "Candidates Left", "Note"])
st.dataframe(funnel_df, use_container_width=True, hide_index=True)

# Slot breakdown
st.markdown("### Per-Slot Breakdown")
slot_df = pd.DataFrame(slot_diag, columns=["Slot", "Role", "After Hierarchy Filter", "After Attribute Filter"])
st.dataframe(slot_df, use_container_width=True, hide_index=True)

# Trigger info
with st.expander("📋 Trigger Attributes"):
    cols_to_show = ['Material', 'Title', 'Level 1', 'Level 2', 'Hierarchy',
                    'Κατασκευαστής', 'Μοντέλο', 'Θύρα USB', 'Χρώμα',
                    'Λειτουργικό σύστημα', 'Extra Χαρακτηριστικά', 'LIST PRICE']
    for col in cols_to_show:
        st.text(f"{col}: {trigger.get(col, 'N/A')}")

# Score breakdown
if not recs.empty:
    st.markdown("### Score Breakdown (Selected Recommendations)")
    debug_cols = ['Title', 'Hierarchy', 'Assigned_Slot', 'Slot_Role', 'Item_Rank',
                  'History_Score', 'Frequency', 'Avail_Boost', 'Smart_Boost',
                  'Final_Score', 'Draft_Score']
    avail = [c for c in debug_cols if c in recs.columns]
    st.dataframe(recs[avail], use_container_width=True)

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
        .score{color:#ff5e00;font-weight:700}
        .stars{color:#ff5e00;letter-spacing:-2px}
        .count{color:#1a73e8}
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
        .m-carousel .slot-role{{font-size:9px}}
        .m-carousel .reviews{{font-size:10px}}
        .m-carousel .old-price{{font-size:10px}}
        .m-carousel .new-price{{font-size:16px}}
        .m-carousel .decimals{{font-size:11px}}
        .m-carousel .cart-btn{{width:36px;height:32px;font-size:14px}}
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
        st.write("##### 💻 Web View (Scroll to see all 10)")
        components.html(desktop_page, height=380, scrolling=True)

    with col_m:
        st.write("##### 📱 Mobile View (2 items visible)")
        components.html(mobile_page, height=520, scrolling=False)

else:
    st.error("❌ No recommendations found. Check the diagnostics above to see where candidates are dropping off.")
