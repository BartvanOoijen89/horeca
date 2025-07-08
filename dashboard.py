import streamlit as st
import pandas as pd
import datetime
import os
import joblib
from utils import get_weather  # zorg dat deze in utils.py staat

# 📂 Pad naar je begroting en map met verkoopdata
BEGROTING_PATH = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
VERKOOPDATA_DIR = "verkoopdata/"
MODEL_PATH = "modellen/model_dict.pkl"  # zorg dat dit modelbestand bestaat

# 📦 Model laden
@st.cache_data
def load_model_dict():
    return joblib.load(MODEL_PATH)

# 📄 Begrotingsdata laden
@st.cache_data
def load_budget_data():
    df = pd.read_excel(BEGROTING_PATH)
    df.columns = df.columns.str.strip()
    df['Datum'] = pd.to_datetime(df['Datum'], dayfirst=True, errors='coerce')
    return df

# 📄 Verkoopdata (optioneel)
def load_verkoopdata(datum):
    bestandsnaam = f"Verkochte-Producten_{datum.strftime('%d-%m-%Y')}.csv"
    pad = os.path.join(VERKOOPDATA_DIR, bestandsnaam)
    if os.path.exists(pad):
        return pd.read_csv(pad, sep=";")
    else:
        return None

# 🤖 Voorspellingsfunctie
def predict_verkoop(productgroepen, temperatuur, neerslag_mm, model_dict):
    voorspellingen = []
    for groep in productgroepen:
        if groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([[temperatuur, neerslag_mm]], columns=["temperatuur", "neerslag_mm"])
            voorspelling = model.predict(X)[0]
            voorspellingen.append({
                "Productgroep": groep,
                "Voorspelde verkoop": round(voorspelling)
            })
    return pd.DataFrame(voorspellingen)

# 🌦️ Weer ophalen met fallback
@st.cache_data
def fetch_weather_data(date, api_key=""):
    try:
        today = datetime.datetime.now().date()
        if date.date() != today:
            return get_weather(api_key=api_key, date=date)
        else:
            return get_weather(api_key=api_key)  # vandaag = zonder datum
    except Exception as e:
        return None, None

# 🖥️ Streamlit dashboard
st.title("📊 Verkoopvoorspelling per Product – Appeltern")
st.write("📅 Kies een datum")

# 📅 Datumselectie
datum_input = st.date_input("Datum", value=datetime.date.today())

# 📥 Data laden
model_dict = load_model_dict()
begroting_df = load_budget_data()

# 📌 Begrotingsdata check
st.subheader("📋 Beschikbare kolommen in begroting:")
st.write(list(begroting_df.columns))

# 🎯 Zoek rijniveau van datum
rij = begroting_df[begroting_df["Datum"] == pd.to_datetime(datum_input)]

# 🧾 Toon waarschuwing als geen bezoekersdata
if rij.empty:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = None
else:
    bezoekers = rij.iloc[0].get("Werkelijk aantal bezoekers")
    if pd.isna(bezoekers):
        st.warning("⚠️ Geen werkelijk aantal bezoekers bekend.")
        bezoekers = None

# 📦 Verkoopdata ophalen
verkoopdata = load_verkoopdata(datum_input)
if verkoopdata is None:
    st.error(f"❌ Bestand niet gevonden: {VERKOOPDATA_DIR}Verkochte-Producten_{datum_input.strftime('%d-%m-%Y')}.csv")

# 🌦️ Weerdata ophalen
temperatuur, regen_mm = fetch_weather_data(datum_input)

# 💡 Productgroepen uit model nemen
productgroepen = list(model_dict.keys())

# 🔮 Voorspelling uitvoeren
st.subheader("🔮 Voorspellingen")
if temperatuur is None or regen_mm is None:
    st.info("Weerdata ontbreekt of kon niet opgehaald worden.")
elif bezoekers is None:
    voorspelling_df = predict_verkoop(productgroepen, temperatuur, regen_mm, model_dict)
    st.dataframe(voorspelling_df)
else:
    st.info("Bezoekersaantal al bekend – voorspelling is niet nodig.")
