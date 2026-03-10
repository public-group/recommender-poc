import streamlit as st
import pandas as pd

st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# The Bulletproof Direct CSV Links
SHEET_ID = "1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo"

@st.cache_data
def load_data():
    url_products = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Products"
    url_history = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=History"
    url_slots = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Slot_Matrix"
    
    df_p = pd.read_csv(url_products)
    df_h = pd.read_csv(url_history)
    df_s = pd.read_csv(url_slots)
    
    # MAGIC FIX 1: Strip accidental spaces from column names (fixes the KeyError)
    df_p.columns = df_p.columns.str.strip()
    df_h.columns = df_h.columns.str.strip()
    df_s.columns = df_s.columns.str.strip()
    
    return df_p, df_h, df_s

df_products, df_history, df_slots = load_data()

st.title("📱 Smartphone Recommendation Tool")

# 1. SELECT THE TRIGGER
# Ensure we only look at Mobile Phones
phones = df_products[df_products['Level 2'] == 'Mobiles']
selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())

# Get the specific phone row
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]

st.subheader(f"Building the perfect loadout for: {selected_phone_name}")


# --- THE CALCULATION ENGINE ---
def calculate_recommendations(trigger, df_products, df_history, df_slots):
    candidates = df_products[df_products['Material'] != trigger['Material']].copy()
    
    # 1. HISTORY SCORE
    trigger_customers = df_history[df_history['Material'] == trigger['Material']]['customerEmail'].unique()
    bought_with = df_history[(df_history['customerEmail'].isin(trigger_customers)) & (df_history['Material'] != trigger['Material'])]
    frequency_df = bought_with['Material'].value_counts().reset_index()
    frequency_df.columns = ['Next_Item_ID', 'Frequency']
    
    candidates = candidates.merge(frequency_df, left_on='Material', right_on='Next_Item_ID', how='left')
    candidates['Frequency'] = candidates['Frequency'].fillna(0)
    candidates['History_Score'] = candidates['Frequency'].apply(lambda freq: 2000 if freq >= 3 else 0)

    # Base Smart Boosts
    candidates['Smart_Boost'] = 0
    candidates.loc[candidates['Μοντέλο'] == trigger.get('Μοντέλο', ''), 'Smart_Boost'] += 100
    candidates.loc[candidates['Κατασκευαστής'] == trigger.get('Κατασκευαστής', ''), 'Smart_Boost'] += 100
    candidates.loc[candidates['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Smart_Boost'] += 50

    candidates['Final_Score'] = candidates['History_Score'] + candidates['Frequency'] + candidates['Smart_Boost']

    # --- THE SLOT ASSIGNMENT ENGINE (STRICT ATTRIBUTE LOGIC) ---
    final_recommendations = []
    
    # Safe Trigger Extraction
    trig_model = str(trigger.get('Μοντέλο', '')).strip()
    trig_brand = str(trigger.get('Κατασκευαστής', '')).strip().upper()
    trig_port = str(trigger.get('Θύρα USB', '')).strip()
    trig_color = str(trigger.get('Χρώμα', '')).strip()
    trig_extras = str(trigger.get('Extra Χαρακτηριστικά', '')).lower()
    trig_os = str(trigger.get('Λειτουργικό σύστημα', '')).lower()
    
    for index, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_hierarchies = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]
        
        # Base filter by Hierarchy
        slot_candidates = candidates[candidates['Hierarchy'].isin(allowed_hierarchies)].copy()
        
        # -----------------------------------------------------------------
        # STRICT ATTRIBUTE LOGIC
        # -----------------------------------------------------------------
        
        # LOGIC 1: Cases & Glass (Slots 1, 2, 7, 10)
        if slot_num in [1, 2, 7, 10]:
            if trig_model:  # FORCE Model Match
                slot_candidates = slot_candidates[slot_candidates['Συμβατό με'].fillna('').str.contains(trig_model, case=False)]
            
            if slot_num == 1:
                slot_candidates = slot_candidates[slot_candidates['Τύπος Θήκης'].fillna('').str.contains("Back Cover", case=False)]
                if trig_color:
                    slot_candidates = slot_candidates[slot_candidates['Χρώμα'].fillna('').str.contains(f"{trig_color}|Διάφανο", case=False)]
            elif slot_num == 2:
                slot_candidates = slot_candidates[slot_candidates['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό οθόνης", case=False)]
            elif slot_num == 7:
                slot_candidates = slot_candidates[slot_candidates['Τύπος προϊόντος'].fillna('').str.contains("Προστατευτικό καμερών", case=False)]
                
                # FIX 1: Slot 7 Fallback — if no Camera Protector found, fall back to a matching Cable
                if slot_candidates.empty and trig_port:
                    fallback_hierarchies = ['CABLE-CHARGER', 'APPLE ORIGINAL IPHONE CABLE-ADAPTORS']
                    slot_candidates = candidates[candidates['Hierarchy'].isin(fallback_hierarchies)].copy()
                    slot_candidates = slot_candidates[slot_candidates['Συμβατό με'].fillna('').str.contains(trig_port, case=False)]
                    
            elif slot_num == 10:
                slot_candidates = slot_candidates[slot_candidates['Τύπος Θήκης'].fillna('').str.contains("Book Cover|Wallet|360 Full Cover", case=False)]

        # LOGIC 2: Chargers (Slot 3)
        elif slot_num == 3:
            if trig_port:  # PORT MATCH
                slot_candidates = slot_candidates[slot_candidates['Συμβατό με'].fillna('').str.contains(trig_port, case=False)]
            
            # SPEED MATCH
            if "γρήγορη φόρτιση" in trig_extras:
                slot_candidates = slot_candidates[slot_candidates['Ισχύς (Watt)'].fillna('').str.contains("21 - 60|61 - 100", case=False)]
            
            # WIRELESS UPSELL
            if "ασύρματη φόρτιση" in trig_extras:
                slot_candidates = slot_candidates[slot_candidates['Τύπος'].fillna('').str.contains("Φορτιστής Πρίζας|Ασύρματος Φορτιστής|Σετ Φόρτισης", case=False)]
                slot_candidates.loc[slot_candidates['Τύπος'].fillna('').str.contains("Ασύρματος Φορτιστής", case=False), 'Final_Score'] += 150
                # Apple MagSafe Bonus
                if trig_brand == "APPLE":
                    slot_candidates.loc[slot_candidates['Title'].fillna('').str.contains("MagSafe", case=False), 'Final_Score'] += 200
            else:
                slot_candidates = slot_candidates[slot_candidates['Τύπος'].fillna('').str.contains("Φορτιστής Πρίζας|Σετ Φόρτισης", case=False)]

        # LOGIC 3: Audio (Slot 4)
        elif slot_num == 4:
            if "3.5mm jack" in trig_extras:
                slot_candidates.loc[slot_candidates['Τύπος σύνδεσης'].fillna('').str.contains("Jack 3.5mm", case=False), 'Final_Score'] += 200
            else:
                # STRICT FILTER for Bluetooth or matching USB port
                slot_candidates = slot_candidates[slot_candidates['Τύπος σύνδεσης'].fillna('').str.contains(f"Bluetooth|{trig_port}", case=False)]
            
            # Brand Lock (applies to both branches)
            slot_candidates.loc[slot_candidates['Κατασκευαστής'] == trig_brand, 'Final_Score'] += 200

        # LOGIC 4: Powerbank (Slot 5)
        elif slot_num == 5:
            if trig_port:  # FILTER Port
                slot_candidates = slot_candidates[slot_candidates['Τύπος θύρας'].fillna('').str.contains(trig_port, case=False)]
            
            if "γρήγορη φόρτιση" in trig_extras:
                slot_candidates.loc[slot_candidates['Ταχύτητα φόρτισης'].fillna('').str.contains("Ταχεία|Υπερταχεία", case=False) | slot_candidates['Ισχύς (Watt)'].fillna('').str.contains("20|30|40|50|60", case=False), 'Final_Score'] += 100
            
            if "ασύρματη φόρτιση" in trig_extras:
                slot_candidates.loc[slot_candidates['Extra Χαρακτηριστικά'].fillna('').str.contains("Ασύρματη φόρτιση", case=False), 'Final_Score'] += 150
                if trig_brand == "APPLE":
                    slot_candidates.loc[slot_candidates['Extra Χαρακτηριστικά'].fillna('').str.contains("Magsafe", case=False), 'Final_Score'] += 200
            
            # General Rule Brand Lock
            slot_candidates.loc[slot_candidates['Κατασκευαστής'] == trig_brand, 'Final_Score'] += 150

        # LOGIC 6: Cross-Sell (Slot 6)
        elif slot_num == 6:
            if "με pen" in trig_extras:
                slot_candidates = slot_candidates[slot_candidates['Τύπος'].fillna('').str.contains("Γραφίδα", case=False)]
            elif trig_brand == "APPLE":
                slot_candidates = slot_candidates[slot_candidates['Τύπος'].fillna('').str.contains("AirTag", case=False)]
            else:
                # FIX 2: Explicit allowlist matching the spec exactly
                allowed_types = "Λουράκι Λαιμού|Λουράκι Καρπού|Αξεσουάρ Smartphone|Αξεσουάρ Κάμερας|Αξεσουάρ Καθαρισμού"
                slot_candidates = slot_candidates[slot_candidates['Τύπος'].fillna('').str.contains(allowed_types, case=False)]

        # LOGIC 5: Wearable (Slot 8)
        elif slot_num == 8:
            if "ios" in trig_os or trig_brand == "APPLE":
                slot_candidates = slot_candidates[slot_candidates['Συμβατό με'].fillna('').str.contains("Apple iOS", case=False)]
            elif "android" in trig_os or trig_brand in ["SAMSUNG", "XIAOMI", "MOTOROLA"]:
                slot_candidates = slot_candidates[slot_candidates['Συμβατό με'].fillna('').str.contains("Google Android", case=False)]
            
            # Boost Brand Lock
            slot_candidates.loc[slot_candidates['Κατασκευαστής'] == trig_brand, 'Final_Score'] += 150

        # Logic 4 Part 2: Car Holder MagSafe Boost (Slot 9)
        elif slot_num == 9:
            if trig_brand == "APPLE" and "ασύρματη φόρτιση" in trig_extras:
                slot_candidates.loc[slot_candidates['Τρόπος τοποθέτησης'].fillna('').str.contains("Μαγνητική", case=False), 'Final_Score'] += 150

        # -----------------------------------------------------------------
        # RANKING & FINAL SELECTION
        # -----------------------------------------------------------------
        slot_candidates = slot_candidates.sort_values(by='Final_Score', ascending=False)
        
        if not slot_candidates.empty:
            best_match = slot_candidates.iloc[0].copy()
            best_match['Assigned_Slot'] = slot_num
            best_match['Slot_Role'] = slot_rule['Slot_Role']
            best_match['Draft_Score'] = (1 * 100) + slot_num
            final_recommendations.append(best_match)

    if final_recommendations:
        return pd.DataFrame(final_recommendations).sort_values(by='Draft_Score')
    return pd.DataFrame()


# --- VISUALIZATION WITH E-COMMERCE UI ---
st.markdown("### <span style='color:#ff5e00; font-weight:bold;'>|</span> Μαζί με αυτό, οι περισσότεροι αγοράζουν", unsafe_allow_html=True)

recs = calculate_recommendations(trigger, df_products, df_history, df_slots)

if not recs.empty:
    # Get up to 10 items
    recs_to_show = recs.head(10)
    
    # 1. GENERATE THE HTML CARDS
    cards_html = ""
    for index, row in recs_to_show.iterrows():
        img_url = str(row.get('Thumbnails', ''))
        
        # Format the prices
        # Safely parse European prices (handles commas and € symbols)
        price_str = str(row.get('LIST PRICE', '0')).replace('€', '').strip()
        if ',' in price_str and '.' in price_str:
            price_str = price_str.replace('.', '') # Remove thousands separator
        price_str = price_str.replace(',', '.') # Change decimal comma to dot
        
        try:
            raw_price = float(price_str)
        except ValueError:
            raw_price = 0.0
        new_price = f"{raw_price:.2f}".replace('.', ',')
        old_price = f"{(raw_price * 1.25):.2f}".replace('.', ',') # Mocking a 25% higher original price
        
        # Truncate title cleanly
        title = str(row.get('Title', ''))
        
        # Build the individual card HTML
        cards_html += f"""
        <div class="product-card">
            <img src="{img_url}" alt="product">
            <div class="title" title="{title}">{title}</div>
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

    # 2. INJECT CSS & RENDER THE LAYOUT
    st.markdown(f"""
    <style>
        /* Hide Streamlit's default padding to maximize space */
        .block-container {{ padding-top: 2rem; }}
        
        /* Shared Card Styling */
        .product-card {{
            background: white;
            border: 1px solid #f0f0f0;
            border-radius: 12px;
            padding: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            flex-shrink: 0; /* Prevents squishing */
            position: relative;
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
        .product-card .reviews {{
            font-size: 11px;
            margin-bottom: 15px;
        }}
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

        /* Desktop Carousel (Scrollable) */
        .desktop-carousel {{
            display: flex;
            overflow-x: auto;
            gap: 15px;
            padding-bottom: 15px;
            scrollbar-width: thin;
        }}
        .desktop-carousel .product-card {{
            width: 200px; /* Fixed width for desktop cards */
        }}

        /* Mobile Mockup Wrapper */
        .mobile-mockup {{
            border: 12px solid #333;
            border-radius: 36px;
            padding: 15px 10px;
            background: #fafafa;
            height: 500px;
            overflow: hidden;
            position: relative;
        }}
        /* Mobile Carousel (Scrollable, forces 2 items) */
        .mobile-carousel {{
            display: flex;
            overflow-x: auto;
            gap: 10px;
            padding-bottom: 15px;
            scrollbar-width: none; /* Hide scrollbar for mobile feel */
        }}
        .mobile-carousel::-webkit-scrollbar {{ display: none; }}
        .mobile-carousel .product-card {{
            width: calc(50% - 5px); /* Exactly 2 cards visible */
            padding: 10px;
        }}
        .mobile-carousel .product-card img {{ height: 90px; }}
    </style>
    """, unsafe_allow_html=True)

    # 3. CREATE THE SPLIT VIEW IN STREAMLIT
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
