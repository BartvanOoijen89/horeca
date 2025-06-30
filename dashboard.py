
import streamlit as st
import pandas as pd
import requests
import joblib
from datetime import datetime

# === CONFIGURATIE ===
API_KEY = "8cfa2a466b95000471c4788b60601298"
LAT = 51.8421  # Coördinaten voor Appeltern
LON = 5.5820

# === LAYOUT ===
st.set_page_config(page_title="Horeca Voorspelling", layout="wide")
st.title("📊 Horeca Verkoopvoorspelling – Appeltern")

# === SELECTEER DATUM ===
selected_date = st.date_input("📅 Kies een datum", datetime.today())

# === LAAD DATA ===
@st.cache_data
def load_data():
    return pd.read_csv("data.csv")

data = load_data()

# Zoek bezoekersaantal bij gekozen datum
datum_str = selected_date.strftime("%Y-%m-%d")
dag_data = data[data["datum"] == datum_str]

if dag_data.empty:
    st.warning("Geen bezoekersdata gevonden voor deze datum.")
    bezoekers = st.number_input("Voer zelf bezoekersaantal in:", min_value=0, step=10)
else:
    bezoekers = int(dag_data["begroot_bezoekers"].values[0])
    st.success(f"Begrote bezoekers op {datum_str}: {bezoekers}")

# === HAAL HUIDIGE WEER OP (OpenWeather API) ===
def get_weather(api_key, lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={api_key}"
    response = requests.get(url)
    data = response.json()
    temp = data["main"]["temp"]
    rain = data.get("rain", {}).get("1h", 0.0)
    return temp, rain

try:
    temperatuur, neerslag = get_weather(API_KEY, LAT, LON)
    st.metric("🌡 Temperatuur (nu)", f"{temperatuur} °C")
    st.metric("🌧 Neerslag (laatste uur)", f"{neerslag} mm")
except Exception as e:
    st.error(f"Fout bij ophalen weerdata: {e}")
    temperatuur = st.number_input("Voer temperatuur handmatig in:", value=20.0)
    neerslag = st.number_input("Voer neerslag handmatig in (mm):", value=0.0)

# === LAAD MODEL EN VOORSPEL ===
try:
    model = joblib.load("model.pkl")
    X = pd.DataFrame([{
        "begroot_bezoekers": bezoekers,
        "temperatuur": temperatuur,
        "neerslag": neerslag
    }])
    voorspelling = model.predict(X)[0]

    st.subheader("📦 Voorspelde verkopen per product")
    df_out = pd.DataFrame.from_dict(voorspelling, orient="index", columns=["Aantal"])
    st.dataframe(df_out)

except Exception as e:
    st.warning("Voorspelling niet mogelijk: modelbestand ontbreekt of heeft verkeerde structuur.")
    st.text(f"Details: {e}")
