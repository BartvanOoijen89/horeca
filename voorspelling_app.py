import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import glob, re, requests, datetime

# ------------- WEERFUNCTIE -------------
def get_weather_forecast_openweather(target_date):
    """Haalt temp_max en neerslag voorspelling voor Appeltern (NL) op voor gegeven datum (max 5 dagen vooruit)."""
    api_key = st.secrets["openweather_key"]
    # Coördinaten Appeltern
    lat, lon = 51.852, 5.601
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=nl"
    r = requests.get(url)
    data = r.json()
    target_date = pd.to_datetime(target_date).date()
    # Zoek alle tijdsblokken van target_date
    blokken = [blok for blok in data["list"] if pd.to_datetime(blok["dt_txt"]).date() == target_date]
    if not blokken:
        return None, None
    temp_max = max(blok["main"]["temp_max"] for blok in blokken)
    rain = [blok.get("rain", {}).get("3h", 0.0) for blok in blokken]
    neerslag = sum(rain)
    return temp_max, neerslag

# --------- DATA INLEZEN -------------
# 1. Verkoopbestanden
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
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)
ALLE_LOCATIES = df['locatie'].unique()
ALLE_OMZETGROEPEN = df['omzetgroep naam'].unique()
ALLE_PRODUCTEN = df['product name'].unique()

# 2. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'
bezoekers_park = bezoekers_df.groupby('datum').agg({
    'begroot aantal bezoekers': 'sum',
    'totaal aantal bezoekers': 'sum'
}).reset_index()

# 3. Weerhistorie
weerdata_knmi = pd.read_csv(
    'Volkel_weerdata.txt',
    skiprows=47, usecols=[1, 11, 21], names=['YYYYMMDD', 'TG', 'RH']
)
weerdata_knmi['YYYYMMDD'] = weerdata_knmi['YYYYMMDD'].astype(str)
weerdata_knmi['datum'] = pd.to_datetime(weerdata_knmi['YYYYMMDD'], format='%Y%m%d', errors='coerce')
weerdata_knmi['Temp'] = pd.to_numeric(weerdata_knmi['TG'], errors='coerce') / 10
weerdata_knmi['Neerslag'] = pd.to_numeric(weerdata_knmi['RH'], errors='coerce').clip(lower=0) / 10
weerdata = weerdata_knmi[['datum', 'Temp', 'Neerslag']].copy()

# 4. Data combineren voor training
df_aggr = pd.merge(df_aggr, bezoekers_park, on='datum', how='left')
df_aggr = pd.merge(df_aggr, weerdata, on='datum', how='left')

# ----------- STREAMLIT APP ------------

st.title("Voorspelling Horeca-omzet & bezoekers (Appeltern)")
st.write("🔎 Bekijk hier de voorspellingen voor de komende 5 dagen, per park of per locatie.")

# --- Kies dag (default: vandaag, max 5 dagen vooruit) ---
vandaag = pd.Timestamp.today().normalize()
keuzedata = [vandaag + pd.Timedelta(days=i) for i in range(5)]
dag_opties = [d.strftime('%A %d-%m-%Y') for d in keuzedata]
dag_dict = dict(zip(dag_opties, keuzedata))
dag_sel = st.selectbox("Kies dag", options=dag_opties, index=0)
datum_sel = dag_dict[dag_sel]

# --- Voorspel bezoekers ---
row_bezoek = bezoekers_park[bezoekers_park['datum'] == datum_sel]
begroot = int(row_bezoek['begroot aantal bezoekers'].values[0]) if not row_bezoek.empty else 0
werkelijk = int(row_bezoek['totaal aantal bezoekers'].values[0]) if not row_bezoek.empty else 0

st.subheader("Bezoekers")
st.write(f"**Begroot aantal bezoekers:** {begroot}")
if datum_sel < vandaag:
    st.write(f"**Werkelijk aantal bezoekers:** {werkelijk}")
else:
    st.write("**Werkelijk aantal bezoekers:** Nog niet bekend")

# --- Weerinfo (OpenWeather voor toekomst, KNMI voor historie) ---
if datum_sel >= vandaag:
    temp, neerslag = get_weather_forecast_openweather(datum_sel)
    if temp is not None:
        st.info(f"**Weersvoorspelling Appeltern:** Piektemp {temp:.1f}°C, neerslag {neerslag:.1f} mm")
    else:
        st.warning("Geen weersvoorspelling beschikbaar.")
else:
    r = weerdata[weerdata['datum'] == datum_sel]
    temp = r['Temp'].values[0] if not r.empty else None
    neerslag = r['Neerslag'].values[0] if not r.empty else None
    st.info(f"**Weer gemeten (KNMI):** Temp {temp:.1f}°C, neerslag {neerslag:.1f} mm" if temp is not None else "Geen data.")

# --- Voorspel omzet/verkopen PARK-TOTAAL ---
st.header("📈 Park-totaal omzet & verkoopprognose")
def voorspel_park(begroot, temp, neerslag, datum_sel, min_dagen=3):
    totaal_omzet = 0
    totaal_verkoop = 0
    # Over alle locaties/producten
    resultaten = []
    for prod in ALLE_PRODUCTEN:
        df_p = df_aggr[(df_aggr['product name'] == prod)]
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
        omzet = model_omzet.predict(x_voorspel)[0]
        if aantal < 1 or omzet < 0:
            continue  # Alleen tonen als positief én voldoende data
        totaal_omzet += max(0, omzet)
        totaal_verkoop += aantal
    return totaal_omzet, totaal_verkoop

if temp is not None and neerslag is not None:
    voorspeld_omzet, voorspeld_aantal = voorspel_park(begroot, temp, neerslag, datum_sel)
    st.metric("Verwachte omzet (park-totaal)", f"€ {voorspeld_omzet:,.2f}")
    st.metric("Voorspeld aantal verkochte producten (totaal)", f"{voorspeld_aantal}")
else:
    st.warning("Niet genoeg data voor voorspelling.")

# --- Locatie-details tonen als je aanvinkt ---
st.header("📍 Locatie(s): details per locatie")
toon_locaties = st.multiselect("Selecteer locaties om details te tonen", options=list(ALLE_LOCATIES), default=[])
def voorspel_per_locatie(locatie, begroot, temp, neerslag, min_dagen=3):
    totaal_omzet = 0
    totaal_verkoop = 0
    resultaten = []
    for omzetgroep in ALLE_OMZETGROEPEN:
        producten = df_aggr.loc[
            (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == omzetgroep),
            'product name'
        ].unique()
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
            omzet = model_omzet.predict(x_voorspel)[0]
            if aantal < 1 or omzet < 0:
                continue
            resultaten.append({
                'product name': prod,
                'verwacht aantal': aantal,
                'status': 'voorspeld'
            })
            totaal_omzet += max(0, omzet)
            totaal_verkoop += aantal
    return resultaten, totaal_omzet, totaal_verkoop

for locatie in toon_locaties:
    st.subheader(f"📍 {locatie}")
    resultaten, omzet, aantal = voorspel_per_locatie(locatie, begroot, temp, neerslag)
    if resultaten:
        df_res = pd.DataFrame(resultaten)
        st.dataframe(df_res[['product name', 'verwacht aantal', 'status']].sort_values('verwacht aantal', ascending=False), use_container_width=True)
        st.metric("Totale omzet (voorspeld)", f"€ {omzet:,.2f}")
        st.metric("Totaal verkocht (voorspeld)", f"{aantal}")
    else:
        st.info("Geen voorspellingen mogelijk (onvoldoende data of alle voorspellingen negatief/0).")

# Eventuele extra logging/debug-info kan je hieronder kwijt:
# st.write(df_aggr.head())
