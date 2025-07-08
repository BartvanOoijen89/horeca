import streamlit as st
import pandas as pd
import joblib
import os
from datetime import datetime
from utils import get_weather

# Pad naar modelbestand
MODEL_PATH = "model_per_product.pkl"

# Laad ML-model(len)
@st.cache_data
def load_model_dict():
    return joblib.load(MODEL_PATH)

# Laad begrotingsdata
@st.cache_data
def load_budget_data():
    df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")
    df['Datum'] = pd.to_datetime(df['Datum'], dayfirst=True)
    return df

# Laad verkoopdata (optioneel)
@st.cache_data
def load_verkoop_data(datum):
    bestandsnaam = f"verkoopdata/Verkochte-Producten_{datum.strftime('%d-%m-%Y')}.csv"
    if os.path.exists(bestandsnaam):
        return pd.read_csv(bestandsnaam)
    else:
        return None

# Genereer voorspelling per productgroep
def predict_verkoop(model_dict, bezoekers, temperatuur, regen_mm):
    voorspellingen = []
    for productgroep, model in model_dict.items():
        X = pd.DataFrame({
            'temperatuur': [temperatuur],
            'regen_mm': [regen_mm],
            'bezoekers': [bezoekers]
        })
        aantal = model.predict(X)[0]
        voorspellingen.append({
            'Productgroep': productgroep,
            'Verwacht aantal': round(aantal)
        })
    return pd.DataFrame(voorspellingen)

# App-start
st.set_page_config(page_title="Verkoopvoorspelling – Appeltern", layout="centered")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# Datumselectie
st.subheader("📅 Kies een datum")
date_input = st.date_input("Datum", value=datetime.today())

# Laad data
model_dict = load_model_dict()
budget_df = load_budget_data()
verkoop_df = load_verkoop_data(date_input)

# Toon kolommen begrotingsbestand
st.subheader("📋 Beschikbare kolommen in begroting:")
st.json(list(budget_df.columns))

# Zoek bezoekersaantal op
bezoekersrij = budget_df[budget_df['Datum'] == pd.to_datetime(date_input)]
if bezoekersrij.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = None
else:
    bezoekers = int(bezoekersrij.iloc[0]["Werkelijk aantal bezoekers"])
    if pd.isna(bezoekers) or bezoekers == 0:
        st.info("ℹ️ Geen werkelijk aantal bezoekers bekend. Voorspellingen worden op basis van weer gedaan.")
        bezoekers = None

# Haal weerdata op
try:
    api_key = st.secrets["weather"]["api_key"]
except:
    st.error("❌ Geen API-sleutel gevonden. Voeg deze toe via [weather] → api_key in Streamlit secrets.")
    st.stop()

temperatuur, regen_mm = get_weather(api_key=api_key, date=date_input)
st.write(f"🌤️ Verwachte temperatuur: **{temperatuur}°C**, neerslag: **{regen_mm} mm**")

# Voorspellingen
st.subheader("🔮 Voorspellingen")

if bezoekers is None:
    st.info("Bezoekersaantal nodig om voorspellingen te doen.")
else:
    voorspelling_df = predict_verkoop(model_dict, bezoekers, temperatuur, regen_mm)
    st.dataframe(voorspelling_df)

# Verkoopdata tonen (optioneel)
if verkoop_df is None:
    st.error(f"❌ Bestand niet gevonden: verkoopdata/Verkochte-Producten_{date_input.strftime('%d-%m-%Y')}.csv")
else:
    st.subheader("📦 Verkoopdata (werkelijk)")
    st.dataframe(verkoop_df)
