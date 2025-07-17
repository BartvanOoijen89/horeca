import streamlit as st
import pandas as pd
import numpy as np
import requests
import glob
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression

# ---- CONSTANTS ----
PRODUCTGROEPEN = ['Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak']
STAD = 'Appeltern,NL'
VOORUITDAGEN = 5

# ---- WEERFUNCTIES ----
def get_weather_forecast_openweather(target_date):
    api_key = st.secrets["openweather_key"]
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={STAD}&appid={api_key}&units=metric&lang=nl"
    resp = requests.get(url).json()
    forecast = resp.get('list', [])
    max_temp = None
    sum_rain = 0.0
    blokken = 0
    for blok in forecast:
        blok_dt = datetime.fromtimestamp(blok['dt'])
        if blok_dt.date() == target_date.date():
            t_max = blok['main']['temp_max']
            max_temp = max(max_temp, t_max) if max_temp is not None else t_max
            rain = blok.get('rain', {}).get('3h', 0.0)
            sum_rain += rain
            blokken += 1
    return (max_temp, sum_rain) if blokken > 0 else (None, None)

def get_historical_weather(weerdata, target_date):
    row = weerdata.loc[weerdata['datum'].dt.date == target_date.date()]
    if not row.empty:
        temp = row['Temp'].iloc[0]
        neerslag = row['Neerslag'].iloc[0]
        return temp, neerslag
    return None, None

def voorspel_bezoekers(begroot, temp, neerslag):
    if np.isnan(temp): temp = 20
    if np.isnan(neerslag): neerslag = 0
    voorspeld = int(round(begroot * (1 + (temp-20)/100 - neerslag/50)))
    voorspeld = max(0, voorspeld)
    return voorspeld

def voorspelling_per_groep(begroot, temp, neerslag, df_aggr):
    results = []
    for groep in PRODUCTGROEPEN:
        df_groep = df_aggr[df_aggr['omzetgroep naam'] == groep]
        producten = df_groep['product name'].unique()
        aantal = 0
        for prod in producten:
            df_p = df_groep[df_groep['product name'] == prod]
            for col in ['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal']:
                if col not in df_p.columns: df_p[col] = np.nan
            df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
            if len(df_p) < 3: continue
            X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_p['aantal']
            model = LinearRegression().fit(X, y)
            X_new = pd.DataFrame({'begroot aantal bezoekers':[begroot], 'Temp':[temp], 'Neerslag':[neerslag]})
            n = int(round(model.predict(X_new)[0]))
            if n > 0: aantal += n
        results.append({'groep': groep, 'voorspeld': aantal})
    return results

# ---- DATA INLEZEN ----
bestanden = glob.glob('verkopen/Verkochte-Producten-*.csv')
dfs = []
for f in bestanden:
    match = re.search(r'Verkochte-Producten-(.*)_(\d{2}-\d{2}-\d{4})\.csv', f)
    locatie = match.group(1) if match else 'Onbekend'
    datum = pd.to_datetime(match.group(2), format='%d-%m-%Y') if match else pd.NaT
    df_temp = pd.read_csv(f, sep=';', decimal=',')
    df_temp['locatie'] = locatie
    df_temp['datum'] = datum
    df_temp.columns = df_temp.columns.str.strip().str.lower()
    dfs.append(df_temp)
df = pd.concat(dfs, ignore_index=True)
for col in ['aantal', 'netto omzet incl. btw']:
    df[col] = pd.to_numeric(df[col], errors='coerce')
df['aantal'] = df['aantal'].fillna(0).astype(int)
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal':'sum', 'netto omzet incl. btw':'sum'}).reset_index()
)

bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
weerdata_knmi = pd.read_csv('Volkel_weerdata.txt', skiprows=47, usecols=[1, 11, 21], names=['YYYYMMDD', 'TG', 'RH'])
weerdata_knmi['YYYYMMDD'] = weerdata_knmi['YYYYMMDD'].astype(str)
weerdata_knmi['datum'] = pd.to_datetime(weerdata_knmi['YYYYMMDD'], format='%Y%m%d', errors='coerce')
weerdata_knmi['Temp'] = pd.to_numeric(weerdata_knmi['TG'], errors='coerce') / 10
weerdata_knmi['Neerslag'] = pd.to_numeric(weerdata_knmi['RH'], errors='coerce').clip(lower=0) / 10
weerdata = weerdata_knmi[['datum', 'Temp', 'Neerslag']].copy()

# ---- DATUM SELECTIE (historisch + max 5 dagen vooruit) ----
historisch_data = sorted(bezoekers_df['datum'].dt.date.unique())
vandaag = datetime.now().date()
vooruit = [vandaag + timedelta(days=i) for i in range(VOORUITDAGEN+1)]
alle_data = sorted(set(list(historisch_data) + vooruit))
datum_sel = st.selectbox("Kies datum", alle_data, index=alle_data.index(vandaag) if vandaag in alle_data else 0)

# ---- KENGETALLEN ----
bezoek = bezoekers_df.loc[bezoekers_df['datum'].dt.date == datum_sel]
begroot = int(bezoek['begroot aantal bezoekers'].iloc[0]) if not bezoek.empty else 0
if not bezoek.empty and 'totaal aantal bezoekers' in bezoek.columns:
    waarde = bezoek['totaal aantal bezoekers'].iloc[0]
    werkelijk = 0 if pd.isna(waarde) else int(waarde)
else:
    werkelijk = 0

# ---- WEER ----
if datum_sel >= vandaag:
    temp, neerslag = get_weather_forecast_openweather(pd.Timestamp(datum_sel))
    weerbron = "OpenWeather (forecast)"
else:
    temp, neerslag = get_historical_weather(weerdata, pd.Timestamp(datum_sel))
    weerbron = "KNMI Volkel (historisch)"
if temp is None: temp = 20
if neerslag is None: neerslag = 0

# ---- VOORSPELLINGEN ----
voorspeld = voorspel_bezoekers(begroot, temp, neerslag)
voorspeld_per_groep = voorspelling_per_groep(begroot, temp, neerslag, df_aggr)
totaal_voorspeld = sum([x['voorspeld'] for x in voorspeld_per_groep])

# ---- STREAMLIT UI ----
st.title("Park horeca omzet- & verkoopvoorspelling")
st.write(f"## {datum_sel.strftime('%d-%m-%Y')}")
col1, col2, col3 = st.columns(3)
col1.metric("Begroot aantal bezoekers", begroot)
col2.metric("Voorspeld aantal bezoekers", voorspeld)
col3.metric("Werkelijk aantal bezoekers", werkelijk)

st.info(f"**Weersvoorspelling:** max temp {temp:.1f}°C, neerslag {neerslag:.1f} mm  \n*bron: {weerbron}*")

st.subheader("Voorspeld aantal verkochte producten (per productgroep):")
for x in voorspeld_per_groep:
    st.write(f"- **{x['groep']}**: {x['voorspeld']} stuks")
st.write(f"### Totaal voorspelde verkoop (bovenstaande groepen): {totaal_voorspeld}")
