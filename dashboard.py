import streamlit as st
import pandas as pd
import glob
from datetime import datetime

st.set_page_config(page_title="📦 Verkoophistorie Appeltern", layout="wide")
st.title("📦 Verkochte producten per dag – Appeltern")

# 📁 Map met verkoopbestanden (CSV)
DATA_DIR = "verkoopdata"

@st.cache_data
def load_all_sales_data():
    all_files = glob.glob(f"{DATA_DIR}/*.csv")
    df_list = []

    for file in all_files:
        try:
            df = pd.read_csv(file, sep=";", decimal=",")
            df['Datum'] = pd.to_datetime(df['Datum'], format="%d-%m-%Y")
            df_list.append(df)
        except Exception as e:
            st.warning(f"Kon bestand niet inlezen: {file} ({e})")

    if df_list:
        return pd.concat(df_list, ignore_index=True)
    else:
        return pd.DataFrame()

sales_df = load_all_sales_data()

if sales_df.empty:
    st.error("⚠️ Geen verkoopdata gevonden. Zorg dat er .csv-bestanden in de map 'verkoopdata/' staan.")
    st.stop()

# 📅 Datumselectie
selected_date = st.date_input("📅 Kies een datum", datetime.today())

# 🔍 Filter op datum
filtered_df = sales_df[sales_df['Datum'] == pd.to_datetime(selected_date)]

if filtered_df.empty:
    st.warning(f"Geen verkopen gevonden op {selected_date.strftime('%d-%m-%Y')}.")
else:
    st.success(f"Verkopen op {selected_date.strftime('%d-%m-%Y')}")

    # 📄 Details per product
    st.subheader("🧾 Verkoop per product")
    st.dataframe(filtered_df[['Omzetgroep naam', 'Product Name', 'Aantal']].sort_values(by='Omzetgroep naam'))

    # 📊 Samenvatting per productgroep
    st.subheader("📊 Totale verkoop per productgroep")
    summary = filtered_df.groupby("Omzetgroep naam")['Aantal'].sum().reset_index()
    summary = summary.sort_values(by="Aantal", ascending=False)
    st.dataframe(summary)
