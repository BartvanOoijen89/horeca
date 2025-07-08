import streamlit as st
import pandas as pd
import joblib
import os
from datetime import datetime
from utils import get_weather

# Pad naar modellenbestand
MODEL_PATH = "model_per_product.pkl"

# === FUNCTIES ===

@st.cache_data
def load_model_dict():
    return joblib.load(MODEL_PATH)

@st.cache_data
def load_budget_data():
    df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")
    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Datum"])

def predict_verkoop(productgroepen, bezoekers, temperatuur, neerslag, model_dict):
    voorspellingen = []
    for groep in productgroepen:
        if groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([[temperatuur, neerslag, bezoekers]], columns=["temp", "rain", "visitors"])
            y_pred = model.predict(X)[0]
            voorspellingen.append({"Productgroep": groep, "Voorspeld aantal": round(y_pred)})
    return pd.DataFrame(voorspellingen)

# === START DASHBOARD ===

st.set_page_config(page_title="Verkoopvoorspelling", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📅 Kies datum
date_input = st.date_input("📅 Kies een datum", value=datetime.today())

# 🔍 Laad gegevens
model_dict = load_model_dict()
begroting_df = load_budget_data()

# ℹ️ Toon kolommen
st.subheader("📋 Beschikbare kolommen in begroting:")
st.code(begroting_df.columns.tolist())

# 🔎 Zoek rijen voor gekozen datum
begroting_rij = begroting_df[begroting_df["Datum"].dt.date == date_input]

if begroting_rij.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = None
else:
    bezoekers = begroting_rij["Werkelijk aantal bezoekers"].values[0]
    if pd.isna(bezoekers) or bezoekers == 0:
        st.warning("⚠️ Geen werkelijk bezoekersaantal beschikbaar. Voorspelling niet mogelijk.")
        bezoekers = None
    else:
        st.info(f"✅ Aantal werkelijke bezoekers: {int(bezoekers)}")

# 🌦️ Weerdata ophalen
try:
    api_key = st.secrets["weather"]["api_key"]
except Exception:
    st.error("❌ API-sleutel voor weerdata ontbreekt in secrets.")
    st.stop()

temperatuur, neerslag = get_weather(api_key=api_key, date=date_input)
st.markdown(f"🌡️ Temperatuur: `{temperatuur}°C` | 🌧️ Neerslag: `{neerslag} mm`")

# 🔮 Voorspellingen tonen
st.subheader("🔮 Voorspellingen")

if bezoekers is not None:
    productgroepen = list(model_dict.keys())
    voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperatuur, neerslag, model_dict)
    st.dataframe(voorspelling_df)
else:
    st.info("ℹ️ Bezoekersaantal nodig om voorspellingen te doen.")

# 📁 Toon ontbrekende verkoopdata als waarschuwing (optioneel)
datum_str = date_input.strftime("%d-%m-%Y")
pad_verkoop = f"verkoopdata/Verkochte-Producten_{datum_str}.csv"
if not os.path.exists(pad_verkoop):
    st.error(f"❌ Bestand niet gevonden: `{pad_verkoop}`")
