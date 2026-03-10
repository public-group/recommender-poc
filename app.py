import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Smart Recommender POC", layout="wide")

# 1. CONNECT TO YOUR GOOGLE SHEET
# Streamlit will use this connection to read your live data
conn = st.connection("gsheets", type=GSheetsConnection)

# Replace this URL with your actual Google Sheet link
SHEET_URL = "https://docs.google.com/spreadsheets/d/1PeLckGFNH-l9GrEvSs3ZQ0N0mXrEYwzA_JwO1wTzJWo/edit?usp=sharing"

# Read the three tabs we created
df_products = conn.read(spreadsheet=SHEET_URL, worksheet="Products")
df_history = conn.read(spreadsheet=SHEET_URL, worksheet="History")
df_slots = conn.read(spreadsheet=SHEET_URL, worksheet="Slot_Matrix")

st.title("📱 Smartphone Recommendation Tool")

# 2. SELECT THE TRIGGER (The phone the customer is buying)
phones = df_products[df_products['Level 2'] == 'Mobiles']
selected_phone_name = st.sidebar.selectbox("Select a Smartphone:", phones['Title'].unique())

# Get all the details of the selected phone
trigger = phones[phones['Title'] == selected_phone_name].iloc[0]

st.subheader(f"Building the perfect loadout for: {selected_phone_name}")

# --- THE CALCULATION ENGINE ---

def calculate_recommendations(trigger, df_products, df_history, df_slots):
    # Start with all available products (excluding the trigger phone itself)
    candidates = df_products[df_products['Material'] != trigger['Material']].copy()
    
    # ---------------------------------------------------------
    # PART 1: THE HISTORY SCORE (+2000)
    # ---------------------------------------------------------
    # Find how many times items were bought with this specific phone
    history_matches = df_history[df_history['Trigger_ID'] == trigger['Material']]
    
    # Merge the frequency data into our candidates list
    candidates = candidates.merge(
        history_matches[['Next_Item_ID', 'Frequency']], 
        left_on='Material', 
        right_on='Next_Item_ID', 
        how='left'
    )
    candidates['Frequency'] = candidates['Frequency'].fillna(0) # Replace blanks with 0
    
    # Apply the strict history rule
    candidates['History_Score'] = candidates['Frequency'].apply(lambda freq: 2000 if freq >= 3 else 0)

    # ---------------------------------------------------------
    # PART 2: THE ATTRIBUTE LOGIC (+100 Smart Boosts)
    # ---------------------------------------------------------
    candidates['Smart_Boost'] = 0
    
    # Logic 1: The "Mirror" Rule (Model Matching for cases/glass)
    candidates.loc[candidates['Μοντέλο'] == trigger['Μοντέλο'], 'Smart_Boost'] += 100
    
    # Logic 2: Brand Ecosystem Match
    candidates.loc[candidates['Κατασκευαστής'] == trigger['Κατασκευαστής'], 'Smart_Boost'] += 100
    
    # Availability Boost (Assuming "Άμεσα Διαθέσιμο" means Available)
    candidates.loc[candidates['AVAILABILITY'] == 'Άμεσα Διαθέσιμο', 'Smart_Boost'] += 50

    # Calculate Final Score
    candidates['Final_Score'] = candidates['History_Score'] + candidates['Frequency'] + candidates['Smart_Boost']

    # ---------------------------------------------------------
    # PART 3: THE SLOT ASSIGNMENT & DRAFT SCORE
    # ---------------------------------------------------------
    final_recommendations = []
    
    # Loop through the rules in your Slot_Matrix tab
    for index, slot_rule in df_slots.iterrows():
        slot_num = slot_rule['Slot_Number']
        allowed_hierarchies = [h.strip() for h in slot_rule['Allowed_Hierarchies'].split(",")]
        
        # Find candidates that match the allowed hierarchies for this slot
        slot_candidates = candidates[candidates['Hierarchy'].isin(allowed_hierarchies)].copy()
        
        # Rank them by their Final Score
        slot_candidates = slot_candidates.sort_values(by='Final_Score', ascending=False)
        
        # Take the absolute best one for this specific slot
        if not slot_candidates.empty:
            best_match = slot_candidates.iloc[0].copy()
            best_match['Assigned_Slot'] = slot_num
            best_match['Slot_Role'] = slot_rule['Slot_Role']
            # The Magic Formula:
            best_match['Draft_Score'] = (1 * 100) + slot_num 
            final_recommendations.append(best_match)

    # Convert the final list back to a dataframe and sort it by Draft Score
    return pd.DataFrame(final_recommendations).sort_values(by='Draft_Score')

# --- VISUALIZATION ---
recs = calculate_recommendations(trigger, df_products, df_history, df_slots)

# Display the results in a grid
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
