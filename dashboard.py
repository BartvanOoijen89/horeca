import streamlit as st
import pandas as pd
import os
import pickle
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Verkoopvoorspelling per Product – Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# Padinstellingen
BEGROTING_XLSX = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
MODEL_PKL = "model_per_product.pkl"
VERKOOPDATA_FOLDER = "verkoopdata"

# 🔁 Functies
@st.cache_data
def load_budget_data():
    df = pd.read_excel(BEGROTING_XLSX)
    kolommen = df.columns.str.lower()
    if "datum" not in kolommen or "bezoekers" not in kolommen:
        raise ValueError("❌ Vereiste kolommen 'Datum' en/of 'Bezoekers' ontbreken in begrotingsbestand.")
    df.columns = df.columns.str.strip()
    df['Datum'] = pd.to_datetime(df['Datum']).dt.date
    return df

@st.cache_data
def load_model():
    with open(MODEL_PKL, "rb") as f:
        model_dict = pickle.load(f)
    return model_dict

def load_verkoop_csv(datum: datetime.date):
    bestandsnaam = f"Verkochte-Producten_{datum.strftime('%d-%m-%Y')}.csv"
    pad = os.path.join(VERKOOPDATA_FOLDER, bestandsnaam)
    if not os.path.exists(pad):
        return None, f"❌ Bestand niet gevonden: {pad}"
    try:
        df = pd.read_csv(pad, sep=";", encoding="utf-8", engine="python")
    except Exception as e:
        return None, f"⚠️ Fout bij inlezen CSV: {e}"
    df["Datum"] = datum
    return df, None

def get_weather(datum):
    # Simuleer dummy weerdata
    np.random.seed(int(datum.strftime("%Y%m%d")))
    temperatuur = np.random.uniform(15, 28)
    regen_mm = np.random.uniform(0, 5)
    return temperatuur, regen_mm

def predict_verkoop(productgroepen, bezoekers, temperatuur, regen_mm):
    model_dict = load_model()
    voorspellingen = []
    for groep in productgroepen:
        if isinstance(groep, str) and groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([{
                "bezoekers": bezoekers,
                "temperatuur": temperatuur,
                "regen_mm": regen_mm
            }])
            aantal = model.predict(X)[0]
            voorspellingen.append({
                "Productgroep": groep,
                "Voorspelling": round(aantal)
            })
    return pd.DataFrame(voorspellingen)

# 🗓️ Datumkeuze
datum_input = st.date_input("📅 Kies een datum", value=datetime.today())

# 📥 Data inladen
try:
    begroting_df = load_budget_data()
except Exception as e:
    st.error(f"Fout bij inladen begrotingsdata: {e}")
    st.stop()

st.subheader("📋 Beschikbare kolommen in begroting:")
st.json(list(begroting_df.columns))

# 🔎 Filter bezoekersaantal
bezoekers_rij = begroting_df[begroting_df["Datum"] == datum_input]
if bezoekers_rij.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = None
else:
    bezoekers = int(bezoekers_rij["Bezoekers"].values[0])

# 📦 Verkochte producten van die dag (optioneel)
verkoop_df, verkoop_error = load_verkoop_csv(datum_input)
if verkoop_error:
    st.error(verkoop_error)
else:
    st.subheader("🧾 Verkochte producten (toegevoegd aan dashboard)")
    st.dataframe(verkoop_df)

# 🌦️ Simuleer of haal weer op
temperatuur, regen_mm = get_weather(datum_input)

# 🔮 Voorspellen
st.subheader("🔮 Voorspellingen")
if bezoekers is None:
    st.warning("Bezoekersaantal nodig om voorspellingen te doen.")
    st.stop()

# Haal productgroepen op
if verkoop_df is not None and "Productgroep" in verkoop_df.columns:
    productgroepen = verkoop_df["Productgroep"].unique().tolist()
else:
    model_dict = load_model()
    productgroepen = list(model_dict.keys())  # fallback: alle bekende groepen

try:
    voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperatuur, regen_mm)
    st.dataframe(voorspelling_df)
except Exception as e:
    st.error(f"❌ Fout tijdens voorspellen: {e}")
