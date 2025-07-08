import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
from pathlib import Path
from utils import get_weather

# 📁 Configuratie
MODEL_PATH = "model_per_product.pkl"
EXCEL_PATH = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
VERKOOPDATA_DIR = "verkoopdata"

# 🧠 Model inladen
@st.cache_resource
def load_model_dict():
    return joblib.load(MODEL_PATH)

model_dict = load_model_dict()

# 📄 Excel laden
@st.cache_data
def load_begroting():
    return pd.read_excel(EXCEL_PATH, parse_dates=["Datum"])

df = load_begroting()

# 🗓️ Datumkeuze
st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔍 Rij ophalen
row = df[df["Datum"] == pd.to_datetime(date_input)]

if row.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    st.stop()

# 👥 Bezoekersaantal bepalen
if not pd.isna(row.iloc[0]["Werkelijk aantal bezoekers"]):
    bezoekers = int(row.iloc[0]["Werkelijk aantal bezoekers"])
    st.success(f"👥 Werkelijk bezoekersaantal: {bezoekers}")
else:
    bezoekers = int(row.iloc[0]["Begroot aantal bezoekers"])
    st.info(f"ℹ️ Werkelijk bezoekersaantal ontbreekt, gebruik gemaakt van begroting: {bezoekers}")

# 🌦️ Weerdata ophalen
api_key = st.secrets["weather"]["api_key"]
temperatuur, neerslag = get_weather(api_key=api_key, date=date_input)

col1, col2 = st.columns(2)
with col1:
    st.metric("🌡️ Temperatuur", f"{temperatuur:.2f}°C")
with col2:
    st.metric("🌧️ Neerslag", f"{neerslag:.2f} mm")

# 🧾 Verkoopdata laden
verkoopfile = Path(VERKOOPDATA_DIR) / f"Verkochte-Producten-Entree_{date_input.strftime('%d-%m-%Y')}.csv"

if verkoopfile.exists():
    verkoop_df = pd.read_csv(verkoopfile, sep=";")
    st.subheader("🧾 Verkoopdata vandaag")
    st.dataframe(verkoop_df)

    if "Omzetgroep naam" in verkoop_df.columns:
        productgroepen = verkoop_df["Omzetgroep naam"].dropna().unique()
    else:
        st.error("❌ Kolom 'Omzetgroep naam' ontbreekt in verkoopdata.")
        productgroepen = []
else:
    st.warning(f"⚠️ Geen verkoopbestand gevonden: {verkoopfile.name}")
    productgroepen = list(model_dict.keys())

# 🔮 Voorspellingen
def predict_verkoop(productgroepen, bezoekers, temperatuur, neerslag):
    resultaten = []
    for groep in productgroepen:
        if isinstance(groep, str) and groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([{
                "Bezoekers": bezoekers,
                "Gemiddelde temperatuur (C)": temperatuur,
                "Gemiddelde neerslag (mm)": neerslag,
                "Weekdag": date_input.weekday()
            }])
            y_pred = model.predict(X)[0]
            resultaten.append((groep, round(y_pred)))
    return pd.DataFrame(resultaten, columns=["Productgroep", "Voorspelling"])

# 📈 Resultaten tonen
st.subheader("🔮 Voorspellingen")
if len(productgroepen) > 0:
    voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperatuur, neerslag)
    if not voorspelling_df.empty:
        st.dataframe(voorspelling_df)
    else:
        st.error("⚠️ Geen voorspellingen mogelijk voor geselecteerde productgroepen.")
else:
    st.info("ℹ️ Geen productgroepen beschikbaar om voorspellingen op te doen.")
