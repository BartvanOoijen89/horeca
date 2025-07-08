import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
import os
from utils import get_weather

# 🔧 Configuratie
MODEL_PATH = "model_per_product.pkl"
DATA_PATH = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📂 Data inladen
@st.cache_data
def load_budget_data():
    df = pd.read_excel(DATA_PATH)
    df.columns = df.columns.str.strip()
    if "Datum" not in df.columns:
        raise ValueError("❌ Kolom 'Datum' niet gevonden in het bestand.")
    df["Datum"] = pd.to_datetime(df["Datum"])
    return df

try:
    df = load_budget_data()
    st.subheader("📋 Beschikbare kolommen in begroting:")
    st.json(list(df.columns))
except Exception as e:
    st.error(f"❌ Kon begrotingsbestand niet laden: {e}")
    st.stop()

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🎯 Filter data voor de geselecteerde datum
row = df[df["Datum"] == pd.to_datetime(date_input)]

if row.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    st.stop()

# 👥 Bezoekers
if "Werkelijk aantal bezoekers" in row.columns and not pd.isna(row.iloc[0]["Werkelijk aantal bezoekers"]):
    bezoekers = int(row.iloc[0]["Werkelijk aantal bezoekers"])
else:
    st.info("ℹ️ Werkelijk bezoekersaantal ontbreekt, gebruik gemaakt van begroting.")
    bezoekers = int(row.iloc[0]["Begroot aantal bezoekers"])

# 🌤️ Weerdata ophalen
try:
    temperatuur, neerslag = get_weather(api_key=st.secrets["weather"]["api_key"], date=date_input)
    st.metric("🌡️ Temperatuur", f"{temperatuur:.2f}°C")
    st.metric("🌧️ Neerslag", f"{neerslag:.2f} mm")
except Exception as e:
    st.error(f"❌ Weerdata kon niet worden opgehaald: {e}")
    temperatuur, neerslag = None, None

# 🤖 Voorspellen
st.subheader("🔮 Voorspellingen")

if bezoekers is None or temperatuur is None or neerslag is None:
    st.info("ℹ️ Bezoekersaantal en weersinformatie nodig om voorspellingen te doen.")
    st.stop()

try:
    model = joblib.load(MODEL_PATH)

    input_df = pd.DataFrame([{
        "Begroting aantal bezoekers": bezoekers,
        "Gemiddelde temperatuur (C)": temperatuur,
        "Gemiddelde neerslag (mm)": neerslag,
        "Weekdag": date_input.weekday()
    }])

    predictions = model.predict(input_df)[0]

    labels = [
        "Verkochte aantal broodjes",
        "Verkochte aantal wraps",
        "Verkochte aantal gebakjes",
        "Verkochte aantal soepen",
        "Verkochte aantal kroketten",
        "Verkochte aantal salades",
        "Verkochte aantal Saucijs-/Kaasbroodjes"
    ]

    resultaat = pd.DataFrame({
        "Product": labels,
        "Voorspelde verkoop (stuks)": [round(p) for p in predictions]
    })

    st.dataframe(resultaat, use_container_width=True)

except Exception as e:
    st.error("❌ Fout bij het doen van voorspellingen")
    st.text(str(e))
