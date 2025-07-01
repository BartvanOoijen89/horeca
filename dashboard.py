import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

date_input = st.date_input("📅 Kies een datum", datetime.today())

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

try:
    api_key = st.secrets["weather"]["api_key"]
    temperature, rain = get_weather(api_key)
    st.metric("🌡️ Temp. vandaag", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
except Exception:
    st.warning("Weerinfo niet geladen")

visitors = st.number_input("👥 Verwachte bezoekers", min_value=0, value=0)

try:
    model = joblib.load("model.pkl")
    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur": temperature,
        "Neerslag": rain,
        "Weekdag": date_input.weekday()
    }])
    predictions = model.predict(features)[0]
    labels = ['Broodjes', 'Wraps', 'Gebak', 'Soep', 'Kroketten', 'Salades', 'Snacks']
    st.subheader("📦 Verwachte verkoop per product:")
    for label, pred in zip(labels, predictions):
        st.write(f"- {label}: {round(pred)} stuks")
except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(e)
