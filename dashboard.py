import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime
import os
import glob

st.set_page_config(page_title="📊 Verkoopvoorspelling per Product – Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 📄 Begrotingsdata laden
@st.cache_data
def load_budget_data():
    return pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx", parse_dates=["Data 2025"])

budget_df = load_budget_data()

# 🔢 Bezoekersaantal ophalen
begroting = budget_df.loc[budget_df['Data 2025'].dt.date == date_input, 'Begroting aantal bezoekers']
if begroting.empty:
    st.error("❌ Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()
visitors = int(begroting.values[0])
st.metric("👥 Begroot aantal bezoekers", f"{visitors}")

# 🔑 API-key ophalen uit secrets
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Weerdata ophalen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date and date != datetime.now().date():
            forecast = data['daily']
            for day in forecast:
                if datetime.fromtimestamp(day['dt']).date() == date:
                    temp = day['temp']['day']
                    rain = day.get('rain', 0)
                    return temp, rain
            return None, None
        else:
            temp = data['current']['temp']
            rain = data['daily'][0].get('rain', 0)
            return temp, rain
    return None, None

# 🌡️ Weer ophalen
temperature, rain = get_weather(api_key, date=date_input.date())

if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
else:
    st.warning("⚠️ Weerdata niet beschikbaar.")

# 🔍 Verkoopdata van vandaag tonen (indien beschikbaar)
@st.cache_data
def load_sales_data(date: datetime.date):
    folder = "verkoopdata"
    pattern = os.path.join(folder, f"Verkochte-Producten_{date.strftime('%d-%m-%Y')}.csv")
    files = glob.glob(pattern)
    if not files:
        return None
    try:
        df = pd.read_csv(files[0], sep=";", encoding="utf-8", on_bad_lines='skip')
        df["Datum"] = pd.to_datetime(date)
        return df
    except Exception as e:
        st.warning(f"Kon bestand niet inlezen: {files[0]} ({str(e)})")
        return None

sales_df = load_sales_data(date_input)
if sales_df is not None:
    st.subheader("📦 Verkochte producten vandaag")
    st.dataframe(sales_df)
else:
    st.info("ℹ️ Geen verkoophistorie beschikbaar voor deze datum.")

# 🔮 Voorspelling uitvoeren
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

    st.subheader("📈 Verwachte verkoop per product:")
    for label, pred in zip(labels, predictions):
        product = label.split()[-1]
        st.write(f"- {product}: {round(pred)} stuks")

except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(str(e))
