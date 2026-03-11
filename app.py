import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import html as html_lib
import re
from difflib import SequenceMatcher

st.set_page_config(page_title="Smart Recommender POC", layout="wide")
st.info("🟢 **Engine v5.2** — Role-based logic aligned to spec (camera fallback, cross-sell fix)")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"
SMART_BOOST, AVAIL_BOOST, HISTORY_BOOST, HISTORY_FREQ_MIN = 100, 50, 2000, 3
TECH_CATS = {"IT", "Telephony", "TV"}
APPL_CATS = {"MDA", "SDA", "Air Condition", "Personal Care"}
COMPAT_COLS = ["Συμβατό με", "Συμβατή συσκευή"]
CC = "_Compatible"  # Merged compat column

# ─────────────────────────────────────────────────────────────
# ROLE → LOGIC KEY MAPPING
# The Slot_Matrix defines roles like "The Bodyguard (Primary Case)".
# We map role keywords to logic functions so slot numbers don't matter.
# ─────────────────────────────────────────────────────────────
def detect_logic_key(role: str) -> str:
    """Map a slot role string to a logic key based on spec:
    Spec Slot 1  → PRIMARY_CASE   (The Perfect Fit / Back Cover)
    Spec Slot 2  → SCREEN_GLASS   (The Screen Shield / Screen Protector)
    Spec Slot 3  → WALL_CHARGER   (The Power Source / Wall/Wireless Charger)
    Spec Slot 4  → EARBUDS        (The Audio Pivot / Handsfree/Earbuds)
    Spec Slot 5  → POWERBANK      (The Backup Power / Powerbank)
    Spec Slot 6  → CROSS_SELL     (The Lifestyle/Tech Feature / Misc Accessory)
    Spec Slot 7  → CAMERA_GLASS   (The Camera Shield / Camera Protector)
    Spec Slot 8  → SMARTWATCH     (The Wearable / Smartwatch)
    Spec Slot 9  → HOLDER         (The Commute / Car Holder)
    Spec Slot 10 → ALT_CASE       (The Alternative Case / Book Cover / Wallet)
    """
    r = role.lower()
    
    if "perfect fit" in r or "back cover" in r or "primary case" in r:
        return "PRIMARY_CASE"
    
    if "alternative" in r or "alt case" in r or "book cover" in r or "wallet" in r:
        return "ALT_CASE"
    
    if "screen" in r or "shield" in r:
        # Avoid catching 'Camera Shield' by ensuring 'camera' isn't in it
        if "camera" not in r:
            return "SCREEN_GLASS"
            
    if "camera" in r:
        return "CAMERA_GLASS"
        
    if "power source" in r or "wall" in r or "charger" in r:
        # Make sure we don't accidentally catch a car charger if you separate them later
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
# PORT & COLOR HELPERS
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
    dp = pd.read_csv(base+"Products"); dp.columns = dp.columns.str.strip()
    dh = pd.read_csv(base+"History");  dh.columns = dh.columns.str.strip()
    ds = pd.read_csv(base+"Slot_Matrix"); ds.columns = ds.columns.str.strip()
    # Merge compat columns
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
    return dp, dh, ds, found

df_products, df_history, df_slots, compat_cols_found = load_data()
st.title("📱 Smartphone Recommendation Tool")

# ─────────────────────────────────────────────────────────────
# TRIGGER
# ─────────────────────────────────────────────────────────────
phones = df_products[(df_products['Level 2']=='Mobiles')&(df_products['Hierarchy']=='Smartphones')]
if phones.empty:
    phones = df_products[df_products['Level 2']=='Mobiles']
    st.sidebar.warning("⚠ Fallback to all Mobiles")
sel = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())
trigger = phones[phones['Title']==sel].iloc[0]
st.subheader(f"Building the perfect loadout for: {sel}")

# ─────────────────────────────────────────────────────────────
# ENGINE
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

    c = df_products[df_products['Material']!=tm].copy()
    diag.append(("0. Start", len(c), ""))

    # U2a: title dedup
    c = c[c['Title']!=tt]; diag.append(("1. U2a: title dedup", len(c), ""))

    # U2b: stock
    if 'CW Stock Units' in c.columns:
        st_col = pd.to_numeric(c['CW Stock Units'], errors='coerce')
        pct = (st_col>0).sum()/len(c) if len(c)>0 else 0
        if pct >= 0.10:
            c['CW Stock Units']=st_col.fillna(0); c=c[c['CW Stock Units']>0]
            diag.append(("2. U2b: stock", len(c), f"Applied ({pct:.0%})"))
        else: diag.append(("2. U2b: stock", len(c), f"⚠ SKIPPED ({pct:.0%})"))
    else: diag.append(("2. U2b: stock", len(c), "⚠ SKIPPED (no col)"))

    # U1: siblings
    mask = (c['Hierarchy']==thier) & (c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb)
    ns = mask.sum()
    if ns > 0:
        sims = c.loc[mask,'Title'].apply(lambda t: title_sim(tt,str(t)))
        dupes = sims[sims>=70].index; c=c.drop(dupes)
        diag.append(("3. U1: siblings", len(c), f"Checked {ns}, removed {len(dupes)}"))
    else: diag.append(("3. U1: siblings", len(c), "No siblings"))

    # U3: macro wall
    b4=len(c)
    if tl1 in TECH_CATS: c=c[~c['Level 1'].isin(APPL_CATS)]
    elif tl1 in APPL_CATS: c=c[~c['Level 1'].isin(TECH_CATS)]
    diag.append(("4. U3: macro wall", len(c), f"Removed {b4-len(c)}"))

    # Scoring
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
    c.loc[c['Μοντέλο']==trigger.get('Μοντέλο',''),'Smart_Boost']+=SMART_BOOST
    c.loc[c['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Smart_Boost']+=SMART_BOOST
    c['Final_Score']=c['History_Score']+c['Frequency']+c['Avail_Boost']+c['Smart_Boost']

    b4u5=len(c)
    nhm=c['History_Score']==0
    if nhm.any():
        ok2=c.loc[nhm].apply(lambda r: price_ok(tprice,r['Next_Price'],tl1), axis=1)
        c=c.drop(ok2[~ok2].index)
    diag.append(("5. U5: price ceiling", len(c), f"Removed {b4u5-len(c)} (ceil: €{max(tprice*0.40,45):.0f})"))

    # ── SLOT ASSIGNMENT ──
    all_slot = []
    for _, sr in df_slots.iterrows():
        sn = sr['Slot_Number']
        role = str(sr.get('Slot_Role',''))
        lk = detect_logic_key(role)
        ah = [h.strip() for h in str(sr['Allowed_Hierarchies']).split(",")]
        sc = c[c['Hierarchy'].isin(ah)].copy()
        afh = len(sc)
        notes = [f"Logic: {lk}"]

        # ───────────────────────────────────────
        # PRIMARY CASE: model match + Back Cover + color
        # ───────────────────────────────────────
        if lk == "PRIMARY_CASE":
            if tmod:
                b4=len(sc); m=sc[sc[CC].fillna('').str.contains(tmod, case=False, regex=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                if not m.empty: sc=m
                else: notes.append(f"  ⚠ kept all (sample: {sample(sc,CC,3)})")
            if not sc.empty:
                b4=len(sc); f=sc[sc['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                notes.append(f"Back Cover: {b4}→{len(f)}")
                if not f.empty: sc=f
            if not sc.empty and tcol:
                b4=len(sc); sc=sc[sc['Χρώμα'].fillna('').str.strip().str.lower().isin(ccols)]
                notes.append(f"Color {ccols[:3]}: {b4}→{len(sc)}")

        # ───────────────────────────────────────
        # ALT CASE: model match + Book/Wallet/Folio
        # ───────────────────────────────────────
        elif lk == "ALT_CASE":
            if tmod:
                b4=len(sc); m=sc[sc[CC].fillna('').str.contains(tmod, case=False, regex=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                if not m.empty: sc=m
                else: notes.append(f"  ⚠ kept all")
            if not sc.empty:
                b4=len(sc)
                f=sc[sc['Τύπος Θήκης'].fillna('').str.contains("Book Cover|Wallet|360 Full Cover|Folio|Flip", case=False)]
                notes.append(f"Book/Wallet/Folio: {b4}→{len(f)}")
                if not f.empty: sc=f

        # ───────────────────────────────────────
        # SCREEN GLASS: model match (via _Compatible)
        # Hierarchy already limits to screen protectors
        # ───────────────────────────────────────
        elif lk == "SCREEN_GLASS":
            if tmod:
                b4=len(sc); m=sc[sc[CC].fillna('').str.contains(tmod, case=False, regex=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                if not m.empty: sc=m
                else: notes.append(f"  ⚠ kept all (sample: {sample(sc,CC,3)})")
            # Optional type filter — data shows most are "Προστατευτικό οθόνης"
            if not sc.empty and has_data(sc, 'Τύπος προϊόντος'):
                b4=len(sc)
                f=sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό οθόνης|Προστατευτικό Οθόνης|Screen Protector", case=False)]
                notes.append(f"Screen Protector type: {b4}→{len(f)}")
                if not f.empty: sc=f

        # ───────────────────────────────────────
        # CAMERA_GLASS (Spec Slot 7, Logic 1):
        # FORCE model match, FILTER Προστατευτικό καμερών
        # Fallback: Extra Charging Cable matching phone's port
        # ───────────────────────────────────────
        elif lk == "CAMERA_GLASS":
            if tmod:
                b4=len(sc); m=sc[sc[CC].fillna('').str.contains(tmod, case=False, regex=False)]
                notes.append(f"Model '{tmod}': {b4}→{len(m)}")
                if not m.empty: sc=m
                else: notes.append(f"  ⚠ kept all")
            if not sc.empty and has_data(sc, 'Τύπος προϊόντος'):
                b4=len(sc)
                f=sc[sc['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό καμερών|Camera", case=False)]
                notes.append(f"Camera type: {b4}→{len(f)}")
                if not f.empty: sc=f
            # Spec fallback: if no camera protector, try charging cable matching port
            if sc.empty and tport:
                fb_h = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS', 'ΚΑΛΩΔΙΑ ΔΕΔΟΜΕΝΩΝ', 'MOBILE CABLE-ADAPTORS', 'IPHONE CABLE-ADAPTORS']
                fb = c[c['Hierarchy'].isin(fb_h)].copy()
                if tmod:
                    fb_model = fb[fb[CC].fillna('').str.contains(tmod, case=False, regex=False)]
                    if not fb_model.empty: fb = fb_model
                fb_port = fb[fb[CC].fillna('').str.lower().str.contains(tport.lower(), regex=False) | fb['Title'].fillna('').str.lower().str.contains(tport.lower(), regex=False)]
                notes.append(f"Cable fallback ({tport}): {len(fb_port)}")
                if not fb_port.empty: sc = fb_port

        # ───────────────────────────────────────
        # WALL CHARGER: compat (model/universal/port) + watt + type
        # Data: Συμβατή συσκευή has "USB Type-C", "Universal", model lists
        # Τύπος3 has "Φορτιστής Πρίζας" (113), "Ασύρματος" (30) etc.
        # ───────────────────────────────────────
        elif lk == "WALL_CHARGER":
            if not sc.empty:
                b4=len(sc)
                cv = sc[CC].fillna('').str.lower()
                keep = cv.str.contains("universal", regex=False) | (cv=='')
                if tmod: keep = keep | cv.str.contains(tmod.lower(), regex=False)
                if tport: keep = keep | cv.str.contains(tport.lower(), regex=False) | cv.str.contains("usb-c", regex=False)
                m=sc[keep]
                notes.append(f"Compat (model/universal/port): {b4}→{len(m)}")
                if not m.empty: sc=m

            if "γρήγορη φόρτιση" in tex and not sc.empty and has_data(sc, 'Ισχύς (Watt)'):
                b4=len(sc)
                f=sc[sc['Ισχύς (Watt)'].fillna('').str.contains("21 - 60|61 - 100|101", case=False)]
                notes.append(f"Fast charge watt: {b4}→{len(f)}")
                if not f.empty: sc=f

            if not sc.empty and has_data(sc, 'Τύπος3'):
                if "ασύρματη φόρτιση" in tex:
                    b4=len(sc)
                    f=sc[sc['Τύπος3'].fillna('').str.contains("Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", case=False)]
                    notes.append(f"Wireless charger types: {b4}→{len(f)}")
                    if not f.empty: sc=f
                    sc.loc[sc['Τύπος3'].fillna('').str.contains("Ασύρματος", case=False),'Final_Score']+=SMART_BOOST
                    if tb=="APPLE":
                        sc.loc[sc['Title'].fillna('').str.contains("MagSafe", case=False),'Final_Score']+=SMART_BOOST
                else:
                    b4=len(sc)
                    f=sc[sc['Τύπος3'].fillna('').str.contains("Φορτιστής Πρίζας|Σετ Φόρτισης", case=False)]
                    notes.append(f"Wall charger types: {b4}→{len(f)}")
                    if not f.empty: sc=f

        # ───────────────────────────────────────
        # POWERBANK (Spec Slot 5, Logic 4):
        # FILTER port, BOOST speed, wireless, MagSafe, brand
        # ───────────────────────────────────────
        elif lk == "POWERBANK":
            # Port match via compat or Τύπος σύνδεσης
            if tport and not sc.empty:
                cv = sc[CC].fillna('').str.lower()
                ts = sc['Τύπος σύνδεσης'].fillna('').str.lower() if 'Τύπος σύνδεσης' in sc.columns else pd.Series('', index=sc.index)
                keep = cv.str.contains(tport.lower(), regex=False) | cv.str.contains("usb-c", regex=False) | cv.str.contains("universal", regex=False) | (cv=='')
                keep = keep | ts.str.contains(tport.lower(), regex=False) | ts.str.contains("usb-c", regex=False) | ts.str.contains("usb type-c", regex=False)
                b4=len(sc); m=sc[keep]
                notes.append(f"Port compat: {b4}→{len(m)}")
                if not m.empty: sc=m

            if "γρήγορη φόρτιση" in tex and not sc.empty and has_data(sc, 'Ισχύς (Watt)'):
                sc.loc[sc['Ισχύς (Watt)'].fillna('').str.contains("21 - 60|61 - 100|101|30|40|50", case=False),'Final_Score']+=SMART_BOOST
                notes.append("Fast charge boost")
            if "ασύρματη φόρτιση" in tex and not sc.empty:
                sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Ασύρματη φόρτιση", case=False),'Final_Score']+=SMART_BOOST
                if tb=="APPLE":
                    sc.loc[sc['Extra Χαρακτηριστικά'].fillna('').str.contains("Magsafe", case=False),'Final_Score']+=SMART_BOOST
            if not sc.empty:
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Final_Score']+=SMART_BOOST

        # ───────────────────────────────────────
        # SMARTWATCH: OS compat + brand boost
        # Data: Συμβατό με has "Google Android, Apple iOS", "iOS 26.0..."
        # ───────────────────────────────────────
        elif lk == "SMARTWATCH":
            if not sc.empty and has_data(sc, CC):
                b4=len(sc)
                if "ios" in tos or tb=="APPLE":
                    f=sc[sc[CC].fillna('').str.contains("iOS|Apple", case=False)]
                elif "android" in tos or tb in ["SAMSUNG","XIAOMI","MOTOROLA"]:
                    f=sc[sc[CC].fillna('').str.contains("Android", case=False)]
                else:
                    f=sc
                notes.append(f"OS compat: {b4}→{len(f)}")
                if not f.empty: sc=f
                else: notes.append(f"  ⚠ kept all (sample: {sample(sc,CC,3)})")
            sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Final_Score']+=SMART_BOOST

        # ───────────────────────────────────────
        # EARBUDS: connection type + brand boost
        # Data: Τύπος σύνδεσης has "3.5mm Jack"(45), "USB-C"(38), "Bluetooth"(5), "Jack 3.5mm"(5)
        # ───────────────────────────────────────
        elif lk == "EARBUDS":
            if "3.5mm jack" in tex:
                if has_data(sc, 'Τύπος σύνδεσης'):
                    sc.loc[sc['Τύπος σύνδεσης'].fillna('').str.contains("3.5mm|Jack", case=False),'Final_Score']+=SMART_BOOST
                    notes.append("3.5mm boost applied")
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Final_Score']+=SMART_BOOST
            else:
                if has_data(sc, 'Τύπος σύνδεσης'):
                    b4=len(sc)
                    # Match Bluetooth, USB-C, Type-C, Ασύρματη
                    f=sc[sc['Τύπος σύνδεσης'].fillna('').str.contains("Bluetooth|USB-C|Type-C|Ασύρματη", case=False)]
                    notes.append(f"BT/USB-C/Wireless: {b4}→{len(f)}")
                    if not f.empty: sc=f
                    else: notes.append(f"  ⚠ kept all")
                else:
                    notes.append("Connection filter: SKIPPED (col empty)")
                sc.loc[sc['Κατασκευαστής'].fillna('').str.strip().str.upper()==tb,'Final_Score']+=SMART_BOOST

        # ───────────────────────────────────────
        # HOLDER (Spec Slot 9):
        # IF Apple + wireless charging → BOOST Μαγνητική/Magsafe
        # (from spec Logic 4: BOOST Slot 9 Βάσεις where Τρόπος τοποθέτησης = Μαγνητική)
        # ───────────────────────────────────────
        elif lk == "HOLDER":
            if tb=="APPLE" and "ασύρματη φόρτιση" in tex:
                sc.loc[sc['Τρόπος τοποθέτησης'].fillna('').str.contains("Μαγνητική|Magsafe", case=False),'Final_Score']+=SMART_BOOST
            notes.append(f"No hard filter, {len(sc)} remain")

        # ───────────────────────────────────────
        # CROSS_SELL (Spec Slot 6, Logic 6):
        # IF Pen → Γραφίδα Αφής
        # ELIF APPLE → Apple AirTag
        # ELSE → Λουράκι, Αξεσουάρ, Καθαρισμού
        # ───────────────────────────────────────
        elif lk == "CROSS_SELL":
            b4=len(sc)
            if "με pen" in tex:
                f=sc[sc['Τύπος3'].fillna('').str.contains("Γραφίδα", case=False)]
                notes.append(f"Stylus: {b4}→{len(f)}")
                if not f.empty: sc=f
            elif tb=="APPLE":
                # Search Τύπος3, Title, and Hierarchy
                f=sc[
                    sc['Τύπος3'].fillna('').str.contains("AirTag|Air Tag|Smart Tag", case=False) |
                    sc['Title'].fillna('').str.contains("AirTag", case=False) |
                    sc['Hierarchy'].fillna('').str.contains("AIRTAG", case=False)
                ]
                notes.append(f"AirTag (Τύπος3/Title/Hierarchy): {b4}→{len(f)}")
                if not f.empty: sc=f
                else:
                    # Fallback: Apple accessories
                    f2=sc[sc['Τύπος3'].fillna('').str.contains("Λουράκι|Αξεσουάρ|Μπρελόκ", case=False)]
                    notes.append(f"Apple acc fallback: {b4}→{len(f2)}")
                    if not f2.empty: sc=f2
            else:
                f=sc[sc['Τύπος3'].fillna('').str.contains(
                    "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού|Μπρελόκ", case=False)]
                notes.append(f"Misc acc: {b4}→{len(f)}")
                if not f.empty: sc=f

        else:
            notes.append(f"⚠ UNKNOWN logic key '{lk}' — no filters applied")

        # ── Rank ──
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
        return pd.DataFrame(), diag, slot_diag, slot_notes

    full = pd.concat(all_slot, ignore_index=True).sort_values('Draft_Score').reset_index(drop=True)

    # S1: Hierarchy cap (2 for smartphones)
    sel, hc, seen = [], {}, set()
    for _, r in full.iterrows():
        h, mat = r['Hierarchy'], r['Material']
        if mat in seen: continue
        if hc.get(h,0)>=2: continue
        sel.append(r); hc[h]=hc.get(h,0)+1; seen.add(mat)
        if len(sel)>=10: break

    diag.append(("6. Final", len(sel), f"Hierarchy cap=2"))
    return (pd.DataFrame(sel) if sel else pd.DataFrame()), diag, slot_diag, slot_notes


# ─────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────
st.markdown("### <span style='color:#ff5e00; font-weight:bold;'>|</span> Μαζί με αυτό, οι περισσότεροι αγοράζουν", unsafe_allow_html=True)
recs, diag, slot_diag, slot_notes = run_engine(trigger, df_products, df_history, df_slots)

# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🩺 Diagnostics")

tpr = str(trigger.get('Θύρα USB','')).strip()
tp2 = extract_base_port(tpr)
tc2 = str(trigger.get('Χρώμα','')).strip()
cc2 = get_case_colors(tc2)
st.markdown(f"**Port:** `{tpr}` → **`{tp2}`** | **Color:** `{tc2}` → **{cc2}** | **Compat cols:** {compat_cols_found}")

st.markdown("### Guardrail Funnel")
st.dataframe(pd.DataFrame(diag, columns=["Step","Left","Note"]), use_container_width=True, hide_index=True)

st.markdown("### Per-Slot Breakdown")
st.dataframe(pd.DataFrame(slot_diag, columns=["Slot","Role","Logic","After Hierarchy","After Attributes"]), use_container_width=True, hide_index=True)

st.markdown("### Slot Filter Details")
for sn, notes in sorted(slot_notes.items()):
    if notes:
        with st.expander(f"Slot {sn} — {' | '.join(notes[:2])}"):
            for n in notes: st.text(n)

with st.expander("📋 Trigger"):
    for col in ['Material','Title','Level 1','Level 2','Hierarchy','Κατασκευαστής','Μοντέλο',
                'Θύρα USB','Χρώμα','Λειτουργικό σύστημα','Extra Χαρακτηριστικά','LIST PRICE']:
        st.text(f"{col}: {trigger.get(col,'N/A')}")

if not recs.empty:
    st.markdown("### Score Breakdown")
    dc=['Title','Hierarchy','Assigned_Slot','Slot_Role','Item_Rank','History_Score','Frequency','Avail_Boost','Smart_Boost','Final_Score','Draft_Score']
    st.dataframe(recs[[c for c in dc if c in recs.columns]], use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────
# VISUALIZATION
# ─────────────────────────────────────────────────────────────
if not recs.empty:
    rts = recs.head(10)
    ch = ""
    for _, r in rts.iterrows():
        iu=safe(str(r.get('Thumbnails','')).strip())
        rp=parse_euro_price(r.get('LIST PRICE',0))
        np=f"{rp:.2f}".replace('.',','); op=f"{(rp*1.25):.2f}".replace('.',',')
        ti=safe(str(r.get('Title',''))); sl=safe(str(r.get('Slot_Role',''))); sn=int(r.get('Assigned_Slot',0))
        ch+=f"""<div class="pc"><div class="sb">Slot {sn}</div><img src="{iu}" alt="p">
        <div class="ti" title="{ti}">{ti}</div><div class="sr">{sl}</div>
        <div class="rv"><span class="sc">4.8</span> <span class="st">&#9733;&#9733;&#9733;&#9733;&#9733;</span> <span class="ct">(305)</span></div>
        <div class="op">&#928;.&#923;.&#932;. : {op}&#8364;</div>
        <div class="np">{np.split(',')[0]}<span class="dm">,{np.split(',')[1]}&#8364;</span></div>
        <button class="cb">&#128722;</button></div>"""

    css="""*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:transparent}
    .pc{background:#fff;border:1px solid #f0f0f0;border-radius:12px;padding:15px;display:flex;flex-direction:column;align-items:center;box-shadow:0 4px 6px rgba(0,0,0,.05);flex-shrink:0;position:relative}
    .sb{position:absolute;top:8px;left:8px;background:#ff5e00;color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:6px}
    .pc img{height:120px;object-fit:contain;margin-bottom:15px}
    .ti{font-size:13px;color:#333;text-align:center;height:36px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-bottom:10px}
    .sr{font-size:10px;color:#888;margin-bottom:8px;text-align:center}.rv{font-size:11px;margin-bottom:15px}
    .sc{color:#ff5e00;font-weight:700}.st{color:#ff5e00;letter-spacing:-2px}.ct{color:#1a73e8}
    .op{font-size:11px;color:#888;text-decoration:line-through;margin-bottom:2px}
    .np{font-size:18px;font-weight:700;color:#ff5e00;margin-bottom:15px}.dm{font-size:12px}
    .cb{background:#ff5e00;color:#fff;border:none;border-radius:8px;width:40px;height:35px;font-size:16px;cursor:pointer}.cb:hover{background:#e65500}"""

    dp=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}
    .car{{display:flex;overflow-x:auto;gap:15px;padding:10px 5px 15px;scrollbar-width:thin}}.car .pc{{width:200px;min-width:200px}}</style></head>
    <body><div class="car">{ch}</div></body></html>"""

    mp=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}
    .mk{{border:12px solid #333;border-radius:36px;padding:15px 10px;background:#fafafa;height:470px;overflow:hidden}}
    .mh{{text-align:center;font-weight:700;font-size:18px;margin-bottom:15px;line-height:1.2}}
    .mc{{display:flex;overflow-x:auto;gap:10px;padding-bottom:15px;scrollbar-width:none}}.mc::-webkit-scrollbar{{display:none}}
    .mc .pc{{width:calc(50% - 5px);min-width:calc(50% - 5px);padding:10px}}.mc .pc img{{height:90px}}.mc .ti{{font-size:11px;height:30px}}
    .mc .sr{{font-size:9px}}.mc .rv{{font-size:10px}}.mc .op{{font-size:10px}}.mc .np{{font-size:16px}}.mc .dm{{font-size:11px}}.mc .cb{{width:36px;height:32px;font-size:14px}}.mc .sb{{font-size:9px;padding:2px 6px}}
    </style></head><body><div class="mk"><div class="mh"><span style="color:#ff5e00">&#8212;</span><br>
    &#924;&#945;&#950;&#943; &#956;&#949; &#945;&#965;&#964;&#972;, &#959;&#953;<br>&#960;&#949;&#961;&#953;&#963;&#963;&#972;&#964;&#949;&#961;&#959;&#953; &#945;&#947;&#959;&#961;&#940;&#950;&#959;&#965;&#957;</div>
    <div class="mc">{ch}</div></div></body></html>"""

    cd, _, cm = st.columns([2.5, 0.2, 1.3])
    with cd:
        st.write("##### 💻 Web View"); components.html(dp, height=380, scrolling=True)
    with cm:
        st.write("##### 📱 Mobile View"); components.html(mp, height=520, scrolling=False)
else:
    st.error("❌ No recommendations. Check diagnostics above.")
