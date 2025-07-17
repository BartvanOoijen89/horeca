import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import glob
import re
import datetime
import requests

### ---- SETTINGS ----

GEWENSTE_GROEPEN = ['Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak']
STAD = "Appeltern,NL"

### ---- DATA INLEZEN ----

# 1. Verkoopbestanden
bestanden = glob.glob('verkopen/Verkochte-Producten-*.csv')
dfs = []
for f in bestanden:
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
df = pd.concat(dfs, ignore_index=True)
for col in ['aantal', 'netto omzet incl. btw']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['aantal'] = df['aantal'].fillna(0).astype(int)
df['netto omzet incl. btw'] = df['netto omzet incl. btw'].fillna(0)

# 2. Agregeren op dag/locatie/omzetgroep/product
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)

# 3. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
bezoekers_park = bezoekers_df.groupby('datum').agg({
    'begroot aantal bezoekers': 'sum',
    'totaal aantal bezoekers': 'sum'
}).reset_index()

# 4. Weerdata (KNMI)
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

# Historische dagen (met data)
historisch_data = list(bezoekers_park['datum'].dt.date)

### ---- OPENWEATHER API FUNCTIE ----

def get_weather_forecast_openweather(datum):
    api_key = st.secrets["openweather_key"]
    base_url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": STAD,
        "appid": api_key,
        "units": "metric",
        "cnt": 40
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    if "list" not in data:
        return None, None
    blokken = data["list"]
    blocks_per_day = {}
    for b in blokken:
        dt_txt = b["dt_txt"]
        dt = pd.to_datetime(dt_txt)
        d = dt.date()
        t_max = b["main"].get("temp_max", np.nan)
        rain = b.get("rain", {}).get("3h", 0.0)
        if d not in blocks_per_day:
            blocks_per_day[d] = {"temp_max": [], "neerslag": []}
        blocks_per_day[d]["temp_max"].append(t_max)
        blocks_per_day[d]["neerslag"].append(rain)
    target = pd.to_datetime(datum).date()
    if target not in blocks_per_day:
        return None, None
    temp_max = np.nanmax(blocks_per_day[target]["temp_max"])
    neerslag = np.nansum(blocks_per_day[target]["neerslag"])
    return temp_max, neerslag

### ---- PRODUCTGROEP VOORSPELLING (PARK-TOTAAL) ----

def voorspelling_per_groep(begroot, temp, neerslag, datum_sel, min_dagen=3):
    resultaten = {groep: 0 for groep in GEWENSTE_GROEPEN}
    for groep in GEWENSTE_GROEPEN:
        producten = df_aggr[df_aggr['omzetgroep naam'] == groep]['product name'].unique()
        for prod in producten:
            df_p = df_aggr[(df_aggr['product name'] == prod)]
            df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
            if len(df_p) < min_dagen:
                continue
            X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_p['aantal']
            model = LinearRegression().fit(X, y)
            x_voorspel = pd.DataFrame({
                'begroot aantal bezoekers': [begroot],
                'Temp': [temp],
                'Neerslag': [neerslag]
            })
            aantal = int(round(model.predict(x_voorspel)[0]))
            if aantal < 1:
                continue
            resultaten[groep] += aantal
    return resultaten

### ---- STREAMLIT INTERFACE ----

st.title("Park horeca omzet- & verkoopvoorspelling")

# --- Datum kiezen, alleen historische + max 5 dagen vooruit (OpenWeather)
vandaag = pd.Timestamp.today().normalize()
keuzedata = [(vandaag + pd.Timedelta(days=d)).date() for d in range(0, 5)]
alle_data = sorted(set(keuzedata + historisch_data))
datum_sel = st.date_input("Kies datum", value=vandaag.date(), min_value=min(alle_data), max_value=max(alle_data))

# --- BEZOEKERS & WEER DATA ---
bezoekdata = bezoekers_park[bezoekers_park['datum'].dt.date == datum_sel]
begroot = int(bezoekdata['begroot aantal bezoekers'].values[0]) if len(bezoekdata) else 0
werkelijk = int(bezoekdata['totaal aantal bezoekers'].values[0]) if len(bezoekdata) else 0

if datum_sel <= vandaag.date():
    # Historisch
    weer_dag = weerdata[weerdata['datum'].dt.date == datum_sel]
    temp = float(weer_dag['Temp'].values[0]) if len(weer_dag) else None
    neerslag = float(weer_dag['Neerslag'].values[0]) if len(weer_dag) else None
else:
    # Voorspelling
    temp, neerslag = get_weather_forecast_openweather(datum_sel)

cols = st.columns(3)
cols[0].metric("Begroot aantal bezoekers", begroot)
cols[1].metric("Voorspeld aantal bezoekers", begroot)  # Hier evt. ML-model invullen als je die hebt!
cols[2].metric("Werkelijk aantal bezoekers", werkelijk if datum_sel <= vandaag.date() else "-")

if temp is not None and neerslag is not None:
    if datum_sel > vandaag.date():
        st.info(f"Weersvoorspelling: max temperatuur {temp:.1f}°C, neerslag {neerslag:.1f} mm (Appeltern, 09:00-21:00, OpenWeather)")
    else:
        st.info(f"Weer: temperatuur {temp:.1f}°C, neerslag {neerslag:.1f} mm (KNMI/Volkel)")
else:
    st.warning("Geen weerdata gevonden.")

### ---- PRODUCTGROEP WEERGAVE ----

if temp is not None and neerslag is not None:
    voorspeld_per_groep = voorspelling_per_groep(begroot, temp, neerslag, datum_sel)
    st.subheader("Verwacht aantal verkochte producten per productgroep")
    totaal = 0
    for groep in GEWENSTE_GROEPEN:
        aantal = voorspeld_per_groep[groep]
        st.write(f"**{groep}**: {aantal}")
        totaal += aantal
    st.write(f"**Totaal (som van deze groepen): {totaal}**")
else:
    st.warning("Niet genoeg data voor voorspelling.")
