import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import glob
import re

st.set_page_config(page_title="Horeca Voorspelling", layout="wide")

# --- Functie: OpenWeather 5-daagse voorspelling voor Appeltern,NL (piektemp & neerslag) ---
def get_weather_forecast_openweather(target_date):
    api_key = st.secrets["openweather_key"]
    locatie = "Appeltern,NL"
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={locatie}&appid={api_key}&units=metric&lang=nl"
    response = requests.get(url)
    data = response.json()

    # Selecteer juiste datum
    temps, neerslag = [], 0.0
    for blok in data.get('list', []):
        blok_dt = datetime.fromtimestamp(blok['dt'])
        if blok_dt.date() == target_date.date():
            temps.append(blok['main']['temp_max'])
            rain = blok.get('rain', {}).get('3h', 0)
            neerslag += rain
    if temps:
        return max(temps), neerslag
    return None, None

# --- Inlezen data ---
# 1. Verkoopdata
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
df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
for col in ['aantal', 'netto omzet incl. btw']:
    if col in df:
        df[col] = pd.to_numeric(df[col], errors='coerce')
if 'aantal' in df:
    df['aantal'] = df['aantal'].fillna(0).astype(int)

# 2. Agregeren
if not df.empty:
    df_aggr = (
        df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
        .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
        .reset_index()
    )
    ALLE_LOCATIES = sorted(df['locatie'].unique())
    ALLE_OMZETGROEPEN = df['omzetgroep naam'].unique()
    ALLE_PRODUCTEN = df['product name'].unique()
else:
    df_aggr = pd.DataFrame()
    ALLE_LOCATIES, ALLE_OMZETGROEPEN, ALLE_PRODUCTEN = [], [], []

# 3. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

# 4. Weerdata (historisch, Volkel)
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

# 5. Koppelen bezoekers/weer aan verkoopdata
bezoekers_park = bezoekers_df.groupby('datum').agg({
    'begroot aantal bezoekers': 'sum',
    'totaal aantal bezoekers': 'sum'
}).reset_index()
if not df_aggr.empty:
    df_aggr = pd.merge(df_aggr, bezoekers_park, on='datum', how='left')
    df_aggr = pd.merge(df_aggr, weerdata, on='datum', how='left')

# --- STREAMLIT UI ---

st.title("Horeca Voorspelling App")

# --- Datumselectie (keuzelijst vandaag t/m +4 dagen, of een bestaande dag uit verkoopdata) ---
vandaag = datetime.now().date()
keuzedata = [d.date() for d in pd.date_range(vandaag, vandaag + timedelta(days=4))]
historisch_data = [d.date() for d in bezoekers_park['datum']]
alle_data = sorted(set(keuzedata + historisch_data))
datum_sel = st.date_input("Kies een dag", min_value=min(alle_data), max_value=max(alle_data), value=vandaag)

# --- Weer-informatie ---
if datum_sel >= vandaag and (datum_sel - vandaag).days <= 4:
    # OpenWeather: voorspelling
    temp, neerslag = get_weather_forecast_openweather(datum_sel)
    if temp is not None:
        st.info(f"🌤️ **Weersvoorspelling voor {datum_sel}**: piektemperatuur {temp:.1f}°C, neerslag {neerslag:.1f} mm (Appeltern)")
    else:
        st.warning("Geen OpenWeather-data beschikbaar voor deze dag.")
else:
    # Historisch: Volkel
    temp = weerdata.loc[weerdata['datum'].dt.date == datum_sel, 'Temp']
    temp = temp.iloc[0] if not temp.empty else np.nan
    neerslag = weerdata.loc[weerdata['datum'].dt.date == datum_sel, 'Neerslag']
    neerslag = neerslag.iloc[0] if not neerslag.empty else np.nan
    st.info(f"🌤️ **Weerdata voor {datum_sel}** (KNMI Volkel): temp {temp:.1f}°C, neerslag {neerslag:.1f} mm")

# --- Bezoekersaantallen (begroot, voorspeld, werkelijk) ---
begroot = bezoekers_park.loc[bezoekers_park['datum'].dt.date == datum_sel, 'begroot aantal bezoekers']
begroot = int(begroot.iloc[0]) if not begroot.empty else 0
werkelijk = bezoekers_park.loc[bezoekers_park['datum'].dt.date == datum_sel, 'totaal aantal bezoekers']
werkelijk = int(werkelijk.iloc[0]) if not werkelijk.empty else 0

# --- Voorspel het aantal bezoekers (ML-model/Lineair, op basis van historie) ---
def voorspel_bezoekers():
    df_b = bezoekers_park.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'totaal aantal bezoekers'])
    df_b = pd.merge(df_b, weerdata, on='datum', how='left')
    if len(df_b) >= 3:
        X = df_b[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
        y = df_b['totaal aantal bezoekers']
        model = LinearRegression().fit(X, y)
        x_voorspel = pd.DataFrame({
            'begroot aantal bezoekers': [begroot],
            'Temp': [temp],
            'Neerslag': [neerslag]
        })
        voorspeld = int(round(model.predict(x_voorspel)[0]))
        return max(0, voorspeld)
    else:
        return None

voorspeld_bezoek = voorspel_bezoekers()
st.subheader("Parktotaal bezoekers")
col1, col2, col3 = st.columns(3)
col1.metric("Begroot aantal bezoekers", begroot)
col2.metric("Voorspeld aantal bezoekers", voorspeld_bezoek if voorspeld_bezoek is not None else "n.v.t.")
col3.metric("Werkelijk aantal bezoekers", werkelijk if werkelijk > 0 else "-")

# --- Omzet-voorspelling ---
def voorspel_omzet_park():
    if not df_aggr.empty:
        df_omzet = df_aggr.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'netto omzet incl. btw'])
        if len(df_omzet) >= 3:
            X = df_omzet[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_omzet['netto omzet incl. btw']
            model = LinearRegression().fit(X, y)
            x_voorspel = pd.DataFrame({
                'begroot aantal bezoekers': [begroot],
                'Temp': [temp],
                'Neerslag': [neerslag]
            })
            omzet = model.predict(x_voorspel)[0]
            return max(0, omzet)
    return None

voorspeld_omzet = voorspel_omzet_park()

col4, col5 = st.columns(2)
col4.metric("Voorspelde omzet (park)", f"€ {voorspeld_omzet:,.2f}" if voorspeld_omzet else "-")
if werkelijk > 0 and not df_aggr.empty:
    omzet_werk = df_aggr.loc[df_aggr['datum'].dt.date == datum_sel, 'netto omzet incl. btw'].sum()
    col5.metric("Werkelijke omzet (park)", f"€ {omzet_werk:,.2f}")
else:
    col5.metric("Werkelijke omzet (park)", "-")

# --- Locatie-keuze ---
st.subheader("Bekijk voorspelling per locatie (optioneel)")
actief = st.multiselect("Kies locaties om te tonen", ALLE_LOCATIES, default=ALLE_LOCATIES[:1] if ALLE_LOCATIES else [])

# --- Voorspelling per locatie ---
def voorspel_per_locatie(
    locatie, datum, begroot, temp, neerslag, min_dagen=3
):
    totaal_omzet = 0
    resultaten_per_omzetgroep = {}
    for omzetgroep in ALLE_OMZETGROEPEN:
        producten = df_aggr.loc[
            (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == omzetgroep),
            'product name'
        ].unique()
        resultaten = []
        for prod in producten:
            df_p = df_aggr[
                (df_aggr['locatie'] == locatie) &
                (df_aggr['omzetgroep naam'] == omzetgroep) &
                (df_aggr['product name'] == prod)
            ]
            df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal', 'netto omzet incl. btw'])
            if len(df_p) < min_dagen:
                continue
            X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_p['aantal']
            y_omzet = df_p['netto omzet incl. btw']
            model = LinearRegression().fit(X, y)
            model_omzet = LinearRegression().fit(X, y_omzet)
            x_voorspel = pd.DataFrame({
                'begroot aantal bezoekers': [begroot],
                'Temp': [temp],
                'Neerslag': [neerslag]
            })
            aantal = int(round(model.predict(x_voorspel)[0]))
            aantal = max(0, aantal)
            if aantal == 0:
                continue  # geen negatieve/lege
            omzet = model_omzet.predict(x_voorspel)[0]
            omzet = max(0, omzet)
            totaal_omzet += omzet
            resultaten.append({'product name': prod, 'verwacht aantal': aantal})
        if resultaten:
            resultaten_per_omzetgroep[omzetgroep] = resultaten
    return resultaten_per_omzetgroep, totaal_omzet

# --- Toon resultaten per locatie ---
for locatie in actief:
    st.markdown(f"### Voorspelling voor **{locatie}** op {datum_sel}")
    resultaten, totaal_omzet = voorspel_per_locatie(locatie, datum_sel, begroot, temp, neerslag)
    for omzetgroep, reslist in resultaten.items():
        st.write(f"**-- {omzetgroep} --**")
        df_res = pd.DataFrame(reslist)
        st.dataframe(df_res, hide_index=True)
        st.caption(f"Totaal aantal: {df_res['verwacht aantal'].sum()}")
    if totaal_omzet:
        st.info(f"**Verwachte omzet {locatie}: € {totaal_omzet:,.2f}**")
    else:
        st.info("Onvoldoende data voor omzetvoorspelling op deze locatie/dag.")

# --- Einde ---
