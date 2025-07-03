import streamlit as st
import pandas as pd
import joblib
import requests
import os
from datetime import datetime

st.set_page_config(page_title="📦 Verkochte producten per dag – Appeltern", layout="wide")
st.title("📦 Verkochte producten per dag – Appeltern")

# 🔢 Selecteer datum
datum = st.date_input("📅 Kies een datum", datetime.today())

# 📁 Verkoopbestand inlezen
@st.cache_data
def load_sales_data(selected_date):
    date_str = selected_date.strftime("%d-%m-%Y")
    filename = f"verkoopdata/Verkochte-Producten_{date_str}.csv"

    if not os.path.exists(filename):
        st.warning(f"⚠️ Geen verkoopdata gevonden. Zorg dat er .csv-bestanden in de map 'verkoopdata/' staan.")
        return None

    try:
        df = pd.read_csv(filename)
        if 'Datum' not in df.columns:
            st.error(f"Kon bestand niet inlezen: {filename} (ontbrekende kolom 'Datum')")
            return None
        df['Datum'] = pd.to_datetime(df['Datum'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Fout bij inlezen van bestand: {filename}")
        st.text(str(e))
        return None

# 📊 Toon verkoopdata
sales_df = load_sales_data(datum)

if sales_df is not None and not sales_df.empty:
    st.subheader(f"📆 Verkoopoverzicht voor {datum.strftime('%d-%m-%Y')}")
    st.dataframe(sales_df)
else:
    st.warning("Geen data beschikbaar voor deze datum.")
