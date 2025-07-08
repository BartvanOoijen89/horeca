import streamlit as st
import pandas as pd
import joblib
from datetime import datetime
from utils import get_weather  # Zorg dat dit in utils.py staat

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📁 Instellingen
EXCEL_PATH = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
MODEL_PATH = "model_per_product.pkl"

# 📊 Data laden met caching
@st.cache_data
def load_budget_data():
    df = pd.read_excel(EXCEL_PATH)
    df.columns = [col.strip() for col in df.columns]  # verwijder spaties in kolomnamen
    return df

@st.cache_data
def load_model():
    return joblib.load(MODEL_PATH)

# ⏱️ Datum kiezen
date_input = st.date_input("📅 Kies een datum", value=datetime.today())
date_str = pd.to_datetime(date_input).strftime("%Y-%m-%d")

# 📋 Laad begrotingsdata
df = load_budget_data()
st.subheader("📋 Beschikbare kolommen in begroting:")
st.write(df.columns.tolist())

# 🔍 Zoek rij voor geselecteerde datum
row = df.loc[df["Datum"] == pd.to_datetime(date_input)]

if row.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = None
else:
    row = row.iloc[0]
    bezoekers = None
    if pd.notna(row.get("Werkelijk aantal bezoekers")):
        bezoekers = int(row["Werkelijk aantal bezoekers"])
    elif pd.notna(row.get("Begroot aantal bezoekers")):
        bezoekers = int(row["Begroot aantal bezoekers"])
        st.info("ℹ️ Werkelijk bezoekersaantal ontbreekt, gebruik gemaakt van begroting.")
    else:
        st.warning("⚠️ Geen bezoekersaantal beschikbaar (werkelijk of begroot).")

# 🌦️ Weerdata ophalen
try:
    api_key = st.secrets["weather"]["api_key"]
    temperatuur, neerslag = get_weather(api_key=api_key, date=date_input)
    st.metric("🌡️ Temperatuur", f"{temperatuur:.2f}°C")
    st.metric("🌧️ Neerslag", f"{neerslag:.2f} mm")
except Exception as e:
    st.error("❌ Fout bij ophalen weerdata")
    st.text(str(e))
    temperatuur, neerslag = None, None

# 🔮 Voorspellen
st.subheader("🔮 Voorspellingen")
if bezoekers is None:
    st.info("ℹ️ Bezoekersaantal nodig om voorspellingen te doen.")
else:
    try:
        model = load_model()
        input_df = pd.DataFrame([{
            "Begroot aantal bezoekers": bezoekers,
            "Gemiddelde temperatuur (C)": temperatuur,
            "Gemiddelde neerslag (mm)": neerslag,
            "Weekdag": date_input.weekday()
        }])

        predictions = model.predict(input_df)[0]

        labels = model.feature_names_out_ if hasattr(model, 'feature_names_out_') else [
            "Verkochte aantal broodjes", "Verkochte aantal wraps", "Verkochte aantal gebakjes",
            "Verkochte aantal soepen", "Verkochte aantal kroketten", "Verkochte aantal salades",
            "Verkochte aantal Saucijs-/Kaasbroodjes"
        ]

        for label, pred in zip(labels, predictions):
            st.write(f"- {label.split()[-1]}: {round(pred)} stuks")

    except Exception as e:
        st.error("❌ Fout bij het doen van voorspellingen")
        st.text(str(e))
