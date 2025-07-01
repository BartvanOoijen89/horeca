import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API Key uit secrets
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Functie om weer op te halen
def get_weather_forecast(api_key, date, lat=51.8421, lon=5.5820):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        today = datetime.today().date()
        days_ahead = (date - today).days

        if days_ahead < 0:
            st.warning("⛔️ Je hebt een datum in het verleden gekozen. We gebruiken het weer van vandaag.")
            days_ahead = 0

        if days_ahead > 7:
            st.warning("⚠️ Geen voorspelling beschikbaar voor meer dan 7 dagen vooruit. Laatste bekende voorspelling wordt gebruikt.")
            days_ahead = 7

        forecast = data["daily"][days_ahead]
        temperature = forecast["temp"]["day"]
        rain = forecast.get("rain", 0.0)
        return temperature, rain

    except Exception as e:
        st.error("❌ Kan weerdata niet ophalen.")
        st.text(f"Foutmelding: {e}")
        return None, None

# 🌡️ Weer ophalen
temperature, rain = get_weather_forecast(api_key, date_input)

# 📊 Toon weergegevens als ze beschikbaar zijn
if temperature is not None and rain is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature:.1f} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain:.1f} mm")
else:
    st.warning("Weergegevens ontbreken, voorspelling mogelijk minder nauwkeurig.")

# 👥 Aantal verwachte bezoekers
visitors = st.number_input("👥 Verwachte bezoekers", min_value=0, value=0)

# 🤖 Laad model en voorspel
try:
    model = joblib.load("model_per_product.pkl")
    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur": temperature if temperature is not None else 0,
        "Neerslag": rain if rain is not None else 0,
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