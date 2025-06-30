
import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

st.set_page_config(page_title="Horeca Verkoopvoorspelling – Appeltern", layout="wide")
st.title("📊 Horeca Verkoopvoorspelling – Appeltern")

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🌦️ Weerdata ophalen via OpenWeatherMap API
def get_weather(api_key, lat=51.8421, lon=5.5820):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=hourly,minutely&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        temp = data['current']['temp']
        rain = data['daily'][0].get('rain', 0)
        return temp, rain
    else:
        return None, None

# 🔑 API Key laden uit secrets
try:
    api_key = st.secrets["openweather"]["api_key"]
    temperature, rain = get_weather(api_key)
    st.metric("🌡️ Temperatuur (nu)", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
except Exception as e:
    st.warning("Weerdata niet beschikbaar")

# 👥 Verwacht aantal bezoekers
visitors = st.number_input("👥 Verwacht aantal bezoekers", min_value=0, value=0)

# 📦 Voorspelling
try:
    model = joblib.load("model.pkl")
    features = pd.DataFrame([{
        "bezoekers": visitors,
        "temperatuur": temperature,
        "regen": rain,
        "dag_vd_week": date_input.weekday()
    }])
    predictions = model.predict(features)
    st.success("📦 Verwachte verkopen per categorie:")
    for i, val in enumerate(predictions[0]):
        st.write(f"- Productcategorie {i + 1}: {round(val)} stuks")
except Exception as e:
    st.error("Voorspelling niet mogelijk: model ontbreekt of heeft verkeerde structuur.")
    st.text(f"Details: {e}")
