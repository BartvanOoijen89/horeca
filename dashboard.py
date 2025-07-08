import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
from pathlib import Path
from utils import get_weather

# Configuratie
MODEL_PATH = "model_per_product.pkl"
EXCEL_PATH = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
VERKOOPDATA_DIR = "verkoopdata"

# Titel en layout
st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# ⏳ 1. Datumkeuze
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 📊 2. Excel inladen
@st.cache_data
def load_begroting():
    return pd.read_excel(EXCEL_PATH, parse_dates=["Datum"])

df = load_begroting()
st.subheader("📋 Beschikbare kolommen in begroting:")
st.json(list(df.columns))

# 🧠 3. Model inladen
@st.cache_resource
def load_model_dict():
    return joblib.load(MODEL_PATH)

model_dict = load_model_dict()

# 🔎 4. Zoek rijniveau uit Excel
row = df[df["Datum"] == pd.to_datetime(date_input)]
if row.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    st.stop()

# 👥 5. Kies aantal bezoekers
if not pd.isna(row.iloc[0]["Werkelijk aantal bezoekers"]):
    bezoekers = int(row.iloc[0]["Werkelijk aantal bezoekers"])
else:
    bezoekers = int(row.iloc[0]["Begroot aantal bezoekers"])
    st.info("ℹ️ Werkelijk bezoekersaantal ontbreekt, gebruik gemaakt van begroting.")

# 🌦️ 6. Weerdata ophalen
api_key = st.secrets["weather"]["api_key"]
temperatuur, neerslag = get_weather(api_key=api_key, date=date_input)
st.metric("🌡️ Temperatuur", f"{temperatuur:.2f}°C")
st.metric("🌧️ Neerslag", f"{neerslag:.2f} mm")

# 📁 7. Verkoophistorie ophalen (optioneel)
verkoopfile = Path(VERKOOPDATA_DIR) / f"Verkochte-Producten-Entree_{date_input.strftime('%d-%m-%Y')}.csv"
if verkoopfile.exists():
    verkoop_df = pd.read_csv(verkoopfile, sep=";")  # <-- belangrijk: juiste scheiding
    st.subheader("🧾 Verkoopdata vandaag")
    st.dataframe(verkoop_df)

    if "Omzetgroep naam" in verkoop_df.columns:
        productgroepen = verkoop_df["Omzetgroep naam"].unique()
    else:
        st.warning("⚠️ Kolom 'Omzetgroep naam' ontbreekt. Fallback naar alle modelgroepen.")
        productgroepen = list(model_dict.keys())
else:
    st.warning(f"❌ Bestand niet gevonden: {verkoopfile.name}")
    productgroepen = list(model_dict.keys())

# 🔮 8. Voorspellingen per productgroep
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
            try:
                y_pred = model.predict(X)[0]
                resultaten.append((groep, round(y_pred)))
            except Exception as e:
                resultaten.append((groep, f"❌ Fout: {str(e)}"))
    return pd.DataFrame(resultaten, columns=["Productgroep", "Voorspelling"])

# 🚀 9. Uitvoeren
st.subheader("🔮 Voorspellingen")
if bezoekers:
    voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperatuur, neerslag)
    st.dataframe(voorspelling_df)
else:
    st.info("ℹ️ Bezoekersaantal nodig om voorspellingen te doen.")
