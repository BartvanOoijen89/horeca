import streamlit as st
import pandas as pd
import pickle
from datetime import datetime
import requests

# Functie om weerdata op te halen via OpenWeather API
def get_weather_forecast(api_key, lat, lon):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# UI
st.set_page_config(layout="wide")
st.title("📊 Horeca Verkoopvoorspelling – Appeltern")

# Datumselectie
datum = st.date_input("📅 Kies een datum", datetime.now())

# Weerdata ophalen
api_key = st.secrets["weather_api_key"] if "weather_api_key" in st.secrets else "VUL_HIER_JE_API_KEY_IN"
lat, lon = 51.8421, 5.5820
weerdata = get_weather_forecast(api_key, lat, lon)

# Toon weerdata
if weerdata:
    today = weerdata["daily"][0]
    temp = today["temp"]["day"]
    rain = today.get("rain", 0.0)

    st.metric("🌡️ Temperatuur (verwacht)", f"{temp:.2f} °C")
    st.metric("🌧️ Neerslag (mm)", f"{rain} mm")
else:
    st.warning("Weerdata niet beschikbaar")

# Simulatie van bezoekersdata
bezoekers = st.number_input("👥 Verwacht aantal bezoekers", min_value=0, value=500)

# Laden model
try:
    with open("model.pkl", "rb") as f:
        model = pickle.load(f)

    # Voorbewerking en voorspelling
    weekday = datum.weekday()
    voorspelling = model.predict([[bezoekers, temp, rain, weekday]])
    st.success(f"📦 Verwachte dagomzet: €{voorspelling[0]:.2f}")
except Exception as e:
    st.error("Voorspelling niet mogelijk: model ontbreekt of heeft verkeerde structuur.")
    st.caption(f"Details: {e}")
