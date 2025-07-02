import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

# Pagina configuratie
st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 🔒 API-key uit secrets ophalen
api_key = st.secrets["weather"]["api_key"]

# 📊 Excel inladen met begroting
@st.cache_data
def load_budget_data():
    return pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx", parse_dates=["Data 2025"])

budget_df = load_budget_data()

# 📅 Datum kiezen
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🌦️ Weerdata ophalen via OpenWeather API
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date and datetime.now().date() != date.date():
            # Zoek datum in forecast
            forecast = data['daily']
            for day in forecast:
                if datetime.fromtimestamp(day['dt']).date() == date.date():
                    return day['temp']['day'], day.get('rain', 0)
            return None, None
        else:
            return data['current']['temp'], data['daily'][0].get('rain', 0)
    return None, None

# 🧊 Ophalen temperatuur en neerslag
temperature, rain = get_weather(api_key, date=date_input)

# 🌡️ Toon weerdata of waarschuwing
if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
else:
    st.warning("Weerdata niet beschikbaar")

# 👥 Bezoekersaantal automatisch ophalen uit Excel
begroting = budget_df.loc[budget_df['Data 2025'] == pd.to_datetime(date_input), 'Begroting aantal bezoekers']
if begroting.empty:
    st.error("Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()
visitors = int(begroting.values[0])
st.metric("👥 Verwachte bezoekers", visitors)

# 🧠 Model laden en voorspelling uitvoeren
try:
    model = joblib.load("model_per_product.pkl")

    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur (C)": temperature,
        "Gemiddelde neerslag (mm)": rain,
        "Weekdag": date_input.weekday()
    }])

    predictions = model.predict(features)[0]

    # ❗ Labelvolgorde (zorg dat deze precies overeenkomt met model-trainingsoutput)
    labels = [
        "Verkochte aantal broodjes",
        "Verkochte aantal wraps",
        "Verkochte aantal gebakjes",
        "Verkochte aantal soepen",
        "Verkochte aantal kroketten",
        "Verkochte aantal salades",
        "Verkochte aantal Saucijs-/Kaasbroodjes"
    ]

    # 📦 Toon voorspellingen
    st.subheader("📦 Verwachte verkoop per product:")
    for label, pred in zip(labels, predictions):
        naam = label.replace("Verkochte aantal ", "")
        st.write(f"- {naam}: {round(pred)} stuks")

except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(str(e))
