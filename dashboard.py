
import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# Laad Excel met begrotingsdata
@st.cache_data
def load_budget_data():
    return pd.read_excel("Data 2025.xlsx", parse_dates=["Data 2025"])

budget_df = load_budget_data()

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API-key ophalen uit secrets
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Weerdata ophalen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date and datetime.now().date() != date.date():
            forecast = data['daily']
            for day in forecast:
                if datetime.fromtimestamp(day['dt']).date() == date.date():
                    temp = day['temp']['day']
                    rain = day.get('rain', 0)
                    return temp, rain
            return None, None
        else:
            temp = data['current']['temp']
            rain = data['daily'][0].get('rain', 0)
            return temp, rain
    return None, None

# 📊 Haal data op
temperature, rain = get_weather(api_key, date=date_input)

if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
else:
    st.warning("Weerdata niet beschikbaar")

# 🔢 Bezoekersaantal ophalen uit begroting
begroting = budget_df.loc[budget_df['Data 2025'] == pd.to_datetime(date_input), 'Begroting aantal bezoekers']
if begroting.empty:
    st.error("Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()
visitors = int(begroting.values[0])

# 🔍 Model laden en voorspellen
try:
    model = joblib.load("model_per_product.pkl")

    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur (C)": temperature,
        "Gemiddelde neerslag (mm)": rain,
        "Weekdag": date_input.weekday()
    }])

    predictions = model.predict(features)[0]

    # Haal labels uit model of definieer hier als vaste volgorde
    labels = model.feature_names_out_ if hasattr(model, 'feature_names_out_') else [
        "Verkochte aantal broodjes", "Verkochte aantal wraps", "Verkochte aantal gebakjes",
        "Verkochte aantal soepen", "Verkochte aantal kroketten", "Verkochte aantal salades",
        "Verkochte aantal Saucijs-/Kaasbroodjes"
    ]

    st.subheader("📦 Verwachte verkoop per product:")
    for label, pred in zip(labels, predictions):
        st.write(f"- {label.split()[-1]}: {round(pred)} stuks")
except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(str(e))
