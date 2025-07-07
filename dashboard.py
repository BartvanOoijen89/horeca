import streamlit as st
import pandas as pd
import os
from datetime import datetime, date as dt_date
import joblib

# === CONFIG ===
DATA_FOLDER = "verkoopdata"
MODEL_PATH = "model_per_product.pkl"
EXCEL_BESTAND = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"

# === LAAD MODEL ===
model_dict = joblib.load(MODEL_PATH)

# === HULPFUNCTIES ===

@st.cache_data
def load_budget_data():
    df = pd.read_excel(EXCEL_BESTAND)
    if "Datum" not in df.columns:
        raise ValueError("❌ Kolom 'Datum' niet gevonden in begrotingsbestand.")
    df["Datum"] = pd.to_datetime(df["Datum"]).dt.date
    return df

def load_verkoopdata_for_date(selected_date):
    filename = f"Verkochte-Producten_{selected_date.strftime('%d-%m-%Y')}.csv"
    filepath = os.path.join(DATA_FOLDER, filename)

    if not os.path.exists(filepath):
        return None, f"❌ Bestand niet gevonden: {filepath}"

    try:
        df = pd.read_csv(filepath, sep=";", encoding="utf-8")
    except Exception as e:
        return None, f"❌ Fout bij inlezen van {filepath}: {e}"

    df["Datum"] = pd.to_datetime(selected_date)
    return df, None

def extract_productgroepen(df):
    groepen = []
    for index, row in df.iterrows():
        naam = str(row.get("Omzetgroep naam", ""))
        if "Broodje" in naam or "Gebak" in naam or "Kroket" in naam:
            groepen.append("Broodjes")
        elif "Soep" in naam:
            groepen.append("Soepen")
        elif "Wrap" in naam:
            groepen.append("Wraps")
        elif "Salade" in naam:
            groepen.append("Salades")
        else:
            groepen.append("Overig")
    return groepen

def get_weather(api_key: str = "", date: datetime = None):
    today = dt_date.today()
    if date and date.date() != today:
        return 20, 0  # standaard weer voor historische dagen
    # Voor live weerdata implementatie (optioneel)
    return 22, 1  # voorbeeld: 22°C en 1 mm regen

def predict_verkoop(productgroepen, bezoekers, temperatuur, regen_mm):
    voorspellingen = []
    for groep in productgroepen:
        if isinstance(groep, str) and groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([[bezoekers, temperatuur, regen_mm]], columns=["Bezoekers", "Temperatuur", "Neerslag"])
            voorspelling = model.predict(X)[0]
            voorspellingen.append((groep, round(voorspelling)))
        else:
            voorspellingen.append((groep, "⚠️ Geen model"))
    return pd.DataFrame(voorspellingen, columns=["Productgroep", "Voorspelling"])

# === STREAMLIT APP ===
st.set_page_config(page_title="Verkoopvoorspelling per Product – Appeltern")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# Datum selectie
date_input = st.date_input("📅 Kies een datum", dt_date.today())

# Laad begroting
try:
    budget_df = load_budget_data()
    st.subheader("📋 Beschikbare kolommen in begroting:")
    st.json(list(budget_df.columns))
except Exception as e:
    st.error(str(e))
    st.stop()

# Bezoekersaantal ophalen
try:
    bezoekers_row = budget_df[budget_df["Datum"] == date_input]
    if bezoekers_row.empty:
        st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
        bezoekers = 0
    else:
        bezoekers = int(bezoekers_row["Bezoekers"].values[0])
except Exception as e:
    st.error(f"Fout bij ophalen bezoekersdata: {e}")
    st.stop()

# Verkoopdata voor huidige dag ophalen
verkoop_df, foutmelding = load_verkoopdata_for_date(date_input)
if foutmelding:
    st.warning(foutmelding)
    verkoop_df = pd.DataFrame()

# Productgroepen ophalen uit CSV
if not verkoop_df.empty:
    productgroepen = extract_productgroepen(verkoop_df)
else:
    productgroepen = list(model_dict.keys())  # fallback: alle bekende groepen

# Weerdata ophalen
temperature, rain_mm = get_weather(date=date_input)

# Voorspellingen genereren
st.subheader("🔮 Voorspellingen")
voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperature, rain_mm)
st.dataframe(voorspelling_df)
