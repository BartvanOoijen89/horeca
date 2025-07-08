import streamlit as st
import pandas as pd
import joblib
import os
from datetime import datetime
from glob import glob

# ===== Instellingen =====
EXCEL_BESTAND = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"
SHEET_NAAM = "Blad1"
VERKOOPDATA_DIR = "verkoopdata"
MODEL_BESTAND = "model_per_product.pkl"

# ===== Functies =====
@st.cache_data
def load_budget_data():
    df = pd.read_excel(EXCEL_BESTAND, sheet_name=SHEET_NAAM)
    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Datum"])
    return df

@st.cache_data
def load_model():
    return joblib.load(MODEL_BESTAND)

def get_bezoekers_for_date(df, gekozen_datum):
    rij = df[df["Datum"].dt.date == gekozen_datum]
    if not rij.empty:
        return int(rij["Begroot aantal bezoekers"].values[0])
    return None

def load_verkochte_producten(datum):
    datum_str = datum.strftime("%d-%m-%Y")
    bestandsnaam = f"{VERKOOPDATA_DIR}/Verkochte-Producten_{datum_str}.csv"
    if os.path.exists(bestandsnaam):
        df = pd.read_csv(bestandsnaam, sep=";", encoding="utf-8")
        df["Datum"] = pd.to_datetime(datum)
        return df
    else:
        return None

def predict_verkoop(productgroepen, bezoekers, temperature, rain_mm, model_dict):
    voorspellingen = []
    for groep in productgroepen:
        if isinstance(groep, str) and groep in model_dict:
            model = model_dict[groep]
            X = pd.DataFrame([{
                "Bezoekers": bezoekers,
                "Temperatuur": temperature,
                "Neerslag": rain_mm
            }])
            voorspeld = int(model.predict(X)[0])
            voorspellingen.append({"Productgroep": groep, "Voorspeld aantal": voorspeld})
    return pd.DataFrame(voorspellingen)

# ===== Streamlit UI =====
st.set_page_config(page_title="Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# == Stap 1: Kies datum ==
st.subheader("📅 Kies een datum")
datum_input = st.date_input("Datum", value=datetime.now().date())

# == Stap 2: Begrotingsdata ==
st.subheader("📋 Beschikbare kolommen in begroting:")
begroting_df = load_budget_data()
st.write(begroting_df.columns.tolist())

# == Stap 3: Haal bezoekers op ==
bezoekers = get_bezoekers_for_date(begroting_df, datum_input)
if bezoekers is None:
    st.warning("⚠️ Geen bezoekersdata gevonden voor deze datum.")
else:
    st.success(f"✅ Begroot aantal bezoekers: {bezoekers}")

# == Stap 4: Laad historische verkoop ==
verkoop_df = load_verkochte_producten(datum_input)
if verkoop_df is not None:
    st.subheader("🧾 Verkochte producten op deze datum")
    st.dataframe(verkoop_df)
else:
    st.error(f"❌ Bestand niet gevonden: {VERKOOPDATA_DIR}/Verkochte-Producten_{datum_input.strftime('%d-%m-%Y')}.csv")

# == Stap 5: Voorspelling (alleen als bezoekers beschikbaar zijn) ==
st.subheader("🔮 Voorspellingen")
if bezoekers is None:
    st.info("Bezoekersaantal nodig om voorspellingen te doen.")
else:
    model_dict = load_model()
    productgroepen = list(model_dict.keys())  # gebruik productgroepen uit model
    temperatuur = 20  # Placeholder waarde
    regen_mm = 0      # Placeholder waarde

    voorspelling_df = predict_verkoop(productgroepen, bezoekers, temperatuur, regen_mm, model_dict)
    st.dataframe(voorspelling_df)

# Extra: Toon foutmelding als model ontbreekt
if not os.path.exists(MODEL_BESTAND):
    st.error(f"❌ Modelbestand niet gevonden: {MODEL_BESTAND}")
