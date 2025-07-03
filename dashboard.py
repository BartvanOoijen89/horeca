import streamlit as st
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="📦 Verkochte producten per dag – Appeltern", layout="wide")
st.title("📦 Verkochte producten per dag – Appeltern")

# 📁 Map waar verkoopdata staat
DATA_FOLDER = "verkoopdata"

# 📅 Selecteer datum
selected_date = st.date_input("📅 Kies een datum", datetime.today())

# 🧠 Functie om bestand te laden
def load_data_for_date(date):
    filename = f"Verkochte-Producten_{date.strftime('%d-%m-%Y')}.csv"
    filepath = os.path.join(DATA_FOLDER, filename)

    if not os.path.exists(filepath):
        st.error(f"⚠️ Geen verkoopdata gevonden voor deze datum: {filename}")
        return None

    try:
        df = pd.read_csv(filepath)

        # Voeg kolom Datum toe (uit bestandsnaam)
        df["Datum"] = pd.to_datetime(date)

        return df
    except Exception as e:
        st.error(f"❌ Fout bij inlezen van {filename}: {e}")
        return None

# 📊 Data inlezen
df = load_data_for_date(selected_date)

# 🖼️ Data tonen als het bestaat
if df is not None and not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.warning("Geen data beschikbaar voor deze datum.")
