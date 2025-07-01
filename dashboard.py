import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

# Pagina-instellingen
st.set_page_config(page_title="📊 Horeca Voorspelling", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📅 Datumkeuze
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API key ophalen uit .streamlit/secrets.toml
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Functie om weerdata op te halen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly&units=metric&appid={api_key}"
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
    
    data = response.json()
    if date == datetime.today().date():
        temp = data.get("current", {}).get("temp", None)
        rain = data.get("daily", [{}])[0].get("rain", 0)
    else:
        # Zoek juiste dag in daily forecast
        for day in data.get("daily", []):
            forecast_date = datetime.fromtimestamp(day["dt"]).date()
            if forecast_date == date:
                temp = day.get("temp", {}).get("day", None)
                rain = day.get("rain", 0)
                break
        else:
            temp, rain = None, None
    return temp, rain

# 🌦️ Haal weerdata op
temperature, rain = get_weather(api_key, date=date_input)

# Toon weerdata of waarschuwing
if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature:.1f} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain:.1f} mm")
else:
    st.warning("Weerinfo niet beschikbaar voor deze datum.")
    temperature = 0
    rain = 0

# 👥 Aantal verwachte bezoekers
visitors = st.number_input("👥 Verwachte bezoekers", min_value=0, value=0)

# 📦 Voorspelling genereren
try:
    model = joblib.load("model_per_product.pkl")

    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur (C)": temperature,
        "Gemiddelde neerslag (mm)": rain,
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
