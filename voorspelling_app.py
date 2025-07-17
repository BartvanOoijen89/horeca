import streamlit as st
import pandas as pd
import numpy as np
import glob
import re
import os
from datetime import datetime, timedelta
import requests
from sklearn.linear_model import LinearRegression

# === Functie: OpenWeather API ophalen voor vandaag ===
def haal_openweather_weer(api_key, plaats="Volkel", land="NL"):
    """Haalt de actuele weersvoorspelling op voor vandaag (temperatuur & neerslag in mm)"""
    url = f"https://api.openweathermap.org/data/2.5/weather?q={plaats},{land}&appid={api_key}&units=metric&lang=nl"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, None
        data = response.json()
        temp = data["main"]["temp"]
        try:
            neerslag = data["rain"].get("1h", 0) if "rain" in data else 0
        except Exception:
            neerslag = 0
        return temp, neerslag
    except Exception:
        return None, None

st.set_page_config(page_title="Horeca Voorspellingen", layout="wide")
st.title("🌳 Horeca Voorspellingen — Park Totaal & Locaties")

# 1. Verkoopdata
verkoop_bestanden = glob.glob('verkopen/Verkochte-Producten-*.csv')
dfs = []
for f in verkoop_bestanden:
    match = re.search(r'Verkochte-Producten-(.*)_(\d{2}-\d{2}-\d{4})\.csv', f)
    if match:
        locatie = match.group(1)
        datum = pd.to_datetime(match.group(2), format='%d-%m-%Y')
    else:
        locatie = 'Onbekend'
        datum = pd.NaT
    df_temp = pd.read_csv(f, sep=';', decimal=',')
    df_temp['locatie'] = locatie
    df_temp['datum'] = datum
    df_temp.columns = df_temp.columns.str.strip().str.lower()
    dfs.append(df_temp)
if dfs:
    df = pd.concat(dfs, ignore_index=True)
    for col in ['aantal', 'netto omzet incl. btw']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['aantal'] = df['aantal'].fillna(0).astype(int)
else:
    st.warning("⚠️ Geen verkoopbestanden gevonden in map 'verkopen'.")
    st.stop()
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)
ALLE_LOCATIES = df['locatie'].unique()
ALLE_OMZETGROEPEN = df['omzetgroep naam'].unique()

# 2. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

# 3. KNMI weerdata (voor historie)
weerdata_knmi = pd.read_csv(
    'Volkel_weerdata.txt',
    skiprows=47, usecols=[1, 11, 21], names=['YYYYMMDD', 'TG', 'RH']
)
weerdata_knmi['YYYYMMDD'] = weerdata_knmi['YYYYMMDD'].astype(str)
weerdata_knmi['datum'] = pd.to_datetime(weerdata_knmi['YYYYMMDD'], format='%Y%m%d', errors='coerce')
weerdata_knmi['TG'] = pd.to_numeric(weerdata_knmi['TG'], errors='coerce')
weerdata_knmi['RH'] = pd.to_numeric(weerdata_knmi['RH'], errors='coerce')
weerdata_knmi['Temp'] = weerdata_knmi['TG'] / 10
weerdata_knmi['Neerslag'] = weerdata_knmi['RH'].clip(lower=0) / 10
weerdata = weerdata_knmi[['datum', 'Temp', 'Neerslag']].copy()

bezoekers_park = bezoekers_df.groupby('datum').agg({
    'begroot aantal bezoekers': 'sum',
    'totaal aantal bezoekers': 'sum'
}).reset_index()
df_aggr = pd.merge(df_aggr, bezoekers_park, on='datum', how='left')
df_aggr = pd.merge(df_aggr, weerdata, on='datum', how='left')

# === Streamlit interface ===
col1, col2, col3 = st.columns([2, 2, 4])
with col1:
    datums_beschikbaar = sorted(list(set(df_aggr['datum'].dropna().unique()) | set(bezoekers_park['datum'].unique())))
    datum = st.date_input("Kies dag voor voorspelling", value=max(datums_beschikbaar), min_value=min(datums_beschikbaar), max_value=max(datums_beschikbaar))
with col2:
    locaties_te_kiezen = list(ALLE_LOCATIES)
    locaties_selected = st.multiselect("Toon locaties (standaard Park totaal)", opties:=["Park Totaal"] + locaties_te_kiezen, default=["Park Totaal"])
with col3:
    tonen_omzet = st.checkbox("Toon omzetvoorspelling", value=True)

dag = pd.Timestamp(datum)

# Weerdata kiezen op basis van dag
if dag == pd.Timestamp(datetime.now().date()):
    # Vandaag: live weer van OpenWeather
    api_key = st.secrets.get("OPENWEATHER_API_KEY", None)
    if not api_key:
        st.warning("OpenWeather API key ontbreekt. Zet deze in Settings > Secrets > OPENWEATHER_API_KEY.")
        temp, neerslag = 20.0, 0.0
    else:
        temp, neerslag = haal_openweather_weer(api_key)
        if temp is None:
            temp, neerslag = 20.0, 0.0
        st.info(f"Weersvoorspelling voor vandaag: {temp:.1f}°C, {neerslag:.1f} mm neerslag (OpenWeather)")
else:
    dag_weer = weerdata.loc[weerdata['datum'] == dag]
    if not dag_weer.empty:
        temp = float(dag_weer['Temp'].values[0])
        neerslag = float(dag_weer['Neerslag'].values[0])
    else:
        temp = 20.0
        neerslag = 0.0

# Begroot/werkelijk bezoekers voor deze dag
dag_bezoek = bezoekers_park.loc[bezoekers_park['datum'] == dag]
if not dag_bezoek.empty:
    begroot = int(dag_bezoek['begroot aantal bezoekers'].values[0])
    werkelijk = int(dag_bezoek['totaal aantal bezoekers'].values[0])
else:
    begroot = 0
    werkelijk = 0

# === ML-model voor bezoekersvoorspelling trainen (gebaseerd op verleden) ===
# Gebruik alleen historie-dagen met volledige data
bezoek_train = bezoekers_park.copy()
bezoek_train = pd.merge(bezoek_train, weerdata, on='datum', how='left')
bezoek_train = bezoek_train.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'totaal aantal bezoekers'])
if len(bezoek_train) > 4:
    X = bezoek_train[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
    y = bezoek_train['totaal aantal bezoekers']
    bezoek_model = LinearRegression().fit(X, y)
    bezoek_X = pd.DataFrame({'begroot aantal bezoekers': [begroot], 'Temp': [temp], 'Neerslag': [neerslag]})
    voorspeld_bezoek = int(round(bezoek_model.predict(bezoek_X)[0]))
    voorspeld_bezoek = max(0, voorspeld_bezoek)
else:
    voorspeld_bezoek = None

with st.expander("🚩 Park totaal — bezoekers en omzet", expanded=True):
    st.write(f"### Park totaal voor: {dag.date()}")
    st.write(f"Begroot aantal bezoekers: **{begroot}**")
    st.write(f"Voorspeld aantal bezoekers: **{voorspeld_bezoek if voorspeld_bezoek is not None else 'onvoldoende data'}**")
    st.write(f"Werkelijk aantal bezoekers: **{werkelijk}**")
    st.write(f"Weersverwachting: temperatuur **{temp:.1f}°C**, neerslag **{neerslag:.1f} mm**")
    if tonen_omzet:
        werkelijke_omzet = df_aggr[df_aggr['datum'] == dag]['netto omzet incl. btw'].sum()
        st.write(f"Werkelijke omzet (alle locaties): **€ {werkelijke_omzet:,.2f}**")
    st.info("Product- en omzetvoorspelling volgt per locatie hieronder. Selecteer locaties in het menu.")

# Productprognoses en omzetvoorspellingen per locatie kun je hieronder verder uitwerken (zie vorige code).
