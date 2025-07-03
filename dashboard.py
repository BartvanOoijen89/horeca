import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime
import os

st.set_page_config(page_title="📊 Verkoopvoorspelling per Product – Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📁 Excel laden
@st.cache_data
def load_budget_data():
    return pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx", parse_dates=True)

budget_df = load_budget_data()

# 📅 Datum selecteren
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API-key ophalen
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Weerdata ophalen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date and date.date() != datetime.now().date():
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

# 🌡️ Weerdata ophalen
temperature, rain = get_weather(api_key, date=date_input)
if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature:.1f} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain:.1f} mm")
else:
    st.warning("Weerdata niet beschikbaar")

# 👥 Begrote bezoekers ophalen
begroting = budget_df.loc[pd.to_datetime(budget_df['Data 2025']).dt.date == date_input, 'Begroting aantal bezoekers']
if begroting.empty:
    st.error("Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()
visitors = int(begroting.values[0])
st.metric("👥 Verwachte bezoekers (begroot)", visitors)

# 🔄 Voorspellen met model
try:
    model = joblib.load("model_per_product.pkl")

    features = pd.DataFrame([{
        "Begroting aantal bezoekers": visitors,
        "Gemiddelde temperatuur (C)": temperature,
        "Gemiddelde neerslag (mm)": rain,
        "Weekdag": date_input.weekday()
    }])

    predictions = model.predict(features)[0]

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

# 📂 Verkoopdata tonen (optioneel)
st.markdown("---")
st.subheader("📦 Verkochte producten per dag – Appeltern")

# Genereer bestandsnaam op basis van datum
file_name = f"Verkochte-Producten_{date_input.strftime('%d-%m-%Y')}.csv"
file_path = os.path.join("verkoopdata", file_name)

if os.path.exists(file_path):
    try:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8")
        df["Datum"] = pd.to_datetime(date_input)
        st.dataframe(df)
    except Exception as e:
        st.warning(f"Kon bestand niet inlezen: {file_path} ({e})")
else:
    st.info("📂 Geen verkoopdata gevonden. Zorg dat er een bestand in de map 'verkoopdata/' staat met de juiste datum.")
