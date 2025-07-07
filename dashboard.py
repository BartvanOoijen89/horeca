import streamlit as st
import pandas as pd
import os
import joblib
from datetime import datetime
import glob

st.set_page_config(page_title="Verkoopvoorspelling – Appeltern", layout="wide")

# === Laden van modellen ===
model_path = "model_per_product.pkl"
model_dict = joblib.load(open(model_path, "rb"))

# === Functie: begrotingsdata laden ===
@st.cache_data
def load_budget_data():
    df = pd.read_excel("Horeca-data 2025 (Tot 19 mei 2025).xlsx")
    st.write("📋 Beschikbare kolommen in begroting:", df.columns.tolist())
    if 'Datum' not in df.columns:
        raise ValueError("❌ Kolom 'Datum' niet gevonden in begrotingsbestand.")
    df['Datum'] = pd.to_datetime(df['Datum'])
    return df

# === Functie: verkoopdata laden vanuit CSV-bestand ===
def load_verkoopdata(date_input):
    folder = "verkoopdata"
    pattern = os.path.join(folder, f"Verkochte-Producten_{date_input.strftime('%d-%m-%Y')}.csv")
    matches = glob.glob(pattern)

    if not matches:
        return pd.DataFrame()

    verkoop_df = pd.read_csv(matches[0], sep=";", engine="python", header=0)
    verkoop_df["Datum"] = date_input
    return verkoop_df

# === Functie: voorspelling per productgroep ===
def predict_verkoop(productgroepen, bezoekers, temperature, rain_mm):
    resultaten = []
    for groep in productgroepen:
        if groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([{
                "Bezoekers": bezoekers,
                "Temperatuur": temperature,
                "Neerslag": rain_mm
            }])
            voorspelling = model.predict(X)[0]
            resultaten.append({
                "Productgroep": groep,
                "Voorspeld aantal": round(voorspelling)
            })
        else:
            resultaten.append({
                "Productgroep": groep,
                "Voorspeld aantal": "⚠️ Geen model"
            })
    return pd.DataFrame(resultaten)

# === Functie: weer ophalen ===
def get_weather(api_key, date):
    date = pd.to_datetime(date)
    today = datetime.now().date()
    if date.date() != today:
        return 20, 0  # Statische waarden voor historische dagen
    return st.secrets.get("TEMPERATURE", 21), st.secrets.get("RAIN_MM", 0)

# === UI ===
st.title("📊 Verkoopvoorspelling per Product – Appeltern")
st.write("📅 Kies een datum")
date_input = st.date_input("Datum", datetime.today())

# === Laden gegevens ===
budget_df = load_budget_data()
verkoop_df = load_verkoopdata(date_input)
temperature, rain_mm = get_weather(api_key="", date=date_input)

# === Aantal bezoekers uit begroting ===
begroting = budget_df.loc[budget_df['Datum'] == pd.to_datetime(date_input), 'Bezoekers']
bezoekers = int(begroting.values[0]) if not begroting.empty else 100  # fallback

productgroepen = sorted(set(budget_df["Productgroep"]))

st.subheader("🔮 Voorspellingen")
voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperature, rain_mm)

# Voeg echte verkoop toe (indien beschikbaar)
if not verkoop_df.empty and "Omzetgroep naam" in verkoop_df.columns and "Aantal" in verkoop_df.columns:
    verkoop_telling = verkoop_df.groupby("Omzetgroep naam")["Aantal"].sum().reset_index()
    verkoop_telling.columns = ["Productgroep", "Verkocht aantal"]
    voorspelling_df = voorspelling_df.merge(verkoop_telling, on="Productgroep", how="left")

st.dataframe(voorspelling_df)

# === Info ===
st.markdown("---")
st.markdown(f"👥 Begroot aantal bezoekers: **{bezoekers}**")
st.markdown(f"🌡️ Temperatuur: **{temperature}°C**")
st.markdown(f"🌧️ Neerslag: **{rain_mm} mm**")

if not verkoop_df.empty:
    st.markdown("📦 Verkoopgegevens van deze dag (terugkoppeling):")
    st.dataframe(verkoop_df)
