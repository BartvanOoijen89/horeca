import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📄 1. Laad Excelbestand (zonder parse_dates)
@st.cache_data
def load_budget_data():
    df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")
    df.columns = df.columns.str.strip()  # verwijder spaties rondom kolomnamen
    return df

budget_df = load_budget_data()
st.write("🧾 Beschikbare kolommen in Excel-bestand:", budget_df.columns.tolist())

# 📅 2. Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 3. API-key ophalen
api_key = st.secrets["weather"]["api_key"]

# 🌤️ 4. Weerdata ophalen
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

temperature, rain = get_weather(api_key, date=date_input)

if temperature is not None:
    st.metric("🌡️ Verwachte temperatuur", f"{temperature} °C")
    st.metric("🌧️ Verwachte neerslag", f"{rain} mm")
else:
    st.warning("⚠️ Weerdata niet beschikbaar")

# 🔢 5. Bezoekersaantal ophalen op basis van geselecteerde datum
try:
    budget_df["Data 2025"] = pd.to_datetime(budget_df["Data 2025"], errors="coerce")
    begroting = budget_df.loc[budget_df['Data 2025'] == pd.to_datetime(date_input), 'Begroting aantal bezoekers']
except Exception as e:
    st.error("❌ Kon 'Data 2025' niet converteren naar datumformaat.")
    st.text(str(e))
    st.stop()

if begroting.empty:
    st.error("📅 Geen begrotingsgegevens gevonden voor deze datum.")
    st.stop()

visitors = int(begroting.values[0])
st.success(f"👥 Begroot aantal bezoekers: {visitors}")

# 📦 6. Voorspelling
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

    st.subheader("🍽️ Verkoopverwachting per product:")
    for label, pred in zip(labels, predictions):
        st.write(f"- {label.split()[-1]}: {round(pred)} stuks")

except Exception as e:
    st.error("❌ Voorspelling mislukt")
    st.text(str(e))
