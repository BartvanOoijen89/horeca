import streamlit as st
import pandas as pd
import joblib
import requests
import os
import glob
from datetime import datetime

st.set_page_config(page_title="📊 Verkoopvoorspelling per Product – Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📦 Laad begrotingsdata
@st.cache_data
def load_budget_data():
    df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")
    st.write("📋 Beschikbare kolommen in begroting:", df.columns.tolist())
    if 'Data 2025' not in df.columns:
        raise ValueError("❌ Kolom 'Data 2025' niet gevonden in begrotingsbestand.")
    df['Data 2025'] = pd.to_datetime(df['Data 2025'])
    return df

budget_df = load_budget_data()

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API-key uit secrets
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Weerdata ophalen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date and date.date() != datetime.now().date():
            for day in data['daily']:
                if datetime.fromtimestamp(day['dt']).date() == date.date():
                    temp = day['temp']['day']
                    rain = day.get('rain', 0)
                    return temp, rain
        else:
            temp = data['current']['temp']
            rain = data['daily'][0].get('rain', 0)
            return temp, rain
    return None, None

temperature, rain = get_weather(api_key, date=date_input)

if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
else:
    st.warning("⚠️ Weerdata niet beschikbaar.")

# 🔢 Bezoekersaantal uit begroting
begroting = budget_df.loc[budget_df['Data 2025'] == pd.to_datetime(date_input), 'Begroting aantal bezoekers']
if begroting.empty:
    st.error("❌ Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()
visitors = int(begroting.values[0])
st.info(f"👥 Begroot aantal bezoekers: **{visitors}**")

# 📂 Verkochte producten ophalen
@st.cache_data
def load_sales_data(date):
    sales_folder = "verkoopdata"
    filename = f"Verkochte-Producten_{date.strftime('%d-%m-%Y')}.csv"
    filepath = os.path.join(sales_folder, filename)
    
    if not os.path.exists(filepath):
        return None

    try:
        df = pd.read_csv(filepath, sep=";")
        df['Datum'] = date  # Voeg datum toe
        return df
    except Exception as e:
        st.warning(f"⚠️ Fout bij inlezen verkoopbestand: {e}")
        return None

sales_df = load_sales_data(date_input)
if sales_df is not None:
    st.subheader("🧾 Verkochte producten op deze dag:")
    st.dataframe(sales_df)
else:
    st.info("ℹ️ Geen verkoopdata beschikbaar voor deze datum.")

# 🔮 Voorspelling laden en tonen
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
        st.write(f"- **{label}**: {round(pred)} stuks")

except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(str(e))
