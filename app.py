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
    # Exclude the phone itself from recommendations
    candidates = df_products[df_products['Material'] != trigger['Material']].copy()
    
    # MAGIC FIX 2: Calculate Frequency from raw Sales History
    # Find all customers who bought this exact phone
    trigger_customers = df_history[df_history['Material'] == trigger['Material']]['customerEmail'].unique()
    # Find everything else those specific customers bought
    bought_with = df_history[(df_history['customerEmail'].isin(trigger_customers)) & (df_history['Material'] != trigger['Material'])]
    # Count how many times each item was bought
    frequency_df = bought_with['Material'].value_counts().reset_index()
    frequency_df.columns = ['Next_Item_ID', 'Frequency']
    
    # Merge the counted frequency into our candidates
    candidates = candidates.merge(frequency_df, left_on='Material', right_on='Next_Item_ID', how='left')
    candidates['Frequency'] = candidates['Frequency'].fillna(0)
    
    # Apply the History Score (+2000 for 3 or more purchases together)
    candidates['History_Score'] = candidates['Frequency'].apply(lambda freq: 2000 if freq >= 3 else 0)

    # Apply the Smart Boosts (+100 for matching attributes)
    candidates['Smart_Boost'] = 0
    candidates.loc[candidates['Μοντέλο'] == trigger['Μοντέλο'], 'Smart_Boost'] += 100
    candidates.loc[candidates['Κατασκευαστής'] == trigger['Κατασκευαστής'], 'Smart_Boost'] += 100
    candidates.loc[candidates['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Smart_Boost'] += 50

    # Calculate Final Score
    candidates['Final_Score'] = candidates['History_Score'] + candidates['Frequency'] + candidates['Smart_Boost']

    # --- THE SLOT ASSIGNMENT ENGINE ---
    final_recommendations = []
    
    for index, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_hierarchies = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]
        
        # Filter candidates that belong in this specific slot
        slot_candidates = candidates[candidates['Hierarchy'].isin(allowed_hierarchies)].copy()
        
        # Rank by Final Score
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

# --- VISUALIZATION ---
recs = calculate_recommendations(trigger, df_products, df_history, df_slots)

if not recs.empty:
    for index, row in recs.iterrows():
        with st.container():
            cols = st.columns([1, 4])
            with cols[0]:
                st.write(f"### Slot {int(row['Assigned_Slot'])}")
                st.caption(row['Slot_Role'])
            with cols[1]:
                st.success(f"**{row['Title']}** (Score: {row['Final_Score']}) - €{row['LIST PRICE']}")
else:
    st.warning("No recommendations found. Check your data and compatibility mapping.")
