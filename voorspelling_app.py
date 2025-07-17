import streamlit as st
import pandas as pd
import numpy as np
import glob
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import requests

st.set_page_config(layout="wide", page_title="Park horeca omzet- & verkoopvoorspelling")

# ---- DATA INLEZEN ----

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

# 2. Aggregatie op dag/locatie/omzetgroep/product
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)

# 3. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

# 4. Weerdata historisch
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

# 5. Productgroepen volgorde
PRODUCTGROEPEN = [
    'Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak'
]

# 6. Locatie mapping voor selectie
LOCATIE_MAPPING = {
    'Onze Entree': 'Entree',
    'Oranjerie': 'Oranjerie',
    'Bloemenkas': 'Bloemenkas'
}

ALLE_OMZETGROEPEN = PRODUCTGROEPEN  # Alleen deze tonen
ALLE_LOCATIES = df['locatie'].unique()

# ---- DATUM SELECTIE ----

vandaag = datetime.now().date()
min_datum = min(bezoekers_df['datum'].dt.date.unique())
max_datum = vandaag + timedelta(days=5)

datum_sel = st.date_input(
    "Kies datum",
    value=vandaag if vandaag <= max_datum else max_datum,
    min_value=min_datum,
    max_value=max_datum
)
datum_sel = pd.Timestamp(datum_sel)

# ---- LOCATIE SELECTIE ----

gekozen_locaties = st.multiselect(
    "Selecteer locatie(s):",
    options=list(LOCATIE_MAPPING.keys()),
    default=['Onze Entree']
)
gekozen_locaties_data = [LOCATIE_MAPPING[loc] for loc in gekozen_locaties]
if not gekozen_locaties_data:
    st.warning("Selecteer minimaal één locatie om voorspellingen te tonen.")
    st.stop()

# ---- HELPER: WEERVOORSPELLING (OpenWeather) ----

def get_weather_forecast_openweather(target_date):
    api_key = st.secrets["openweather_key"]
    plaats = "Appeltern,NL"
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={plaats}&appid={api_key}&units=metric&lang=nl"
    r = requests.get(url)
    data = r.json()
    temps = []
    rain = []
    for blok in data["list"]:
        blok_dt = datetime.fromtimestamp(blok["dt"])
        if blok_dt.date() == target_date.date():
            temps.append(blok["main"].get("temp_max", blok["main"].get("temp", 20)))
            rainval = 0.0
            if blok.get("rain"):
                rainval = blok["rain"].get("3h", 0.0)
            rain.append(rainval)
    if temps:
        return max(temps), sum(rain)
    return 20.0, 0.0

def get_weer_voor_dag(datum):
    if datum.date() < vandaag:
        match = weerdata[weerdata['datum'].dt.date == datum.date()]
        if len(match):
            temp = float(match['Temp'].iloc[0])
            neerslag = float(match['Neerslag'].iloc[0])
            bron = "KNMI (historisch)"
        else:
            temp, neerslag = 20.0, 0.0
            bron = "Geen data"
    else:
        temp, neerslag = get_weather_forecast_openweather(datum)
        bron = "OpenWeather (forecast)"
    return temp, neerslag, bron

# ---- NIEUWE FUNCTIE: voorspelling per groep én product ----

def voorspelling_per_groep_en_product(begroot, temp, neerslag, datum_sel, locaties):
    groep_totaal = {groep: 0 for groep in PRODUCTGROEPEN}
    producten_per_groep = {groep: [] for groep in PRODUCTGROEPEN}
    totaal = 0
    for omzetgroep in PRODUCTGROEPEN:
        df_p = df_aggr[
            (df_aggr['datum'] < datum_sel) &
            (df_aggr['omzetgroep naam'] == omzetgroep) &
            (df_aggr['locatie'].isin(locaties))
        ]
        if len(df_p) < 3:
            continue
        df_p = pd.merge(df_p, bezoekers_df[['datum', 'begroot aantal bezoekers']], on='datum', how='left')
        df_p = pd.merge(df_p, weerdata, on='datum', how='left')
        df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
        if len(df_p) < 3:
            continue
        producten = df_p['product name'].unique()
        for product in producten:
            df_prod = df_p[df_p['product name'] == product]
            if len(df_prod) < 3:
                continue
            X = df_prod[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_prod['aantal']
            model = LinearRegression().fit(X, y)
            x_voorspel = pd.DataFrame({'begroot aantal bezoekers': [begroot], 'Temp': [temp], 'Neerslag': [neerslag]})
            aantal = int(round(model.predict(x_voorspel)[0]))
            aantal = max(0, aantal)
            if aantal > 0:
                producten_per_groep[omzetgroep].append((product, aantal))
                groep_totaal[omzetgroep] += aantal
                totaal += aantal
    return groep_totaal, producten_per_groep, totaal

# ---- START UI ----

st.markdown(f"""
# Park horeca omzet- & verkoopvoorspelling

### {datum_sel.strftime('%d-%m-%Y')}
""")

col1, col2, col3 = st.columns(3)

# Begroot, Voorspeld, Werkelijk aantal bezoekers
bezoek = bezoekers_df[bezoekers_df['datum'] == datum_sel]
begroot = int(bezoek['begroot aantal bezoekers'].iloc[0]) if not bezoek.empty else 0
if not bezoek.empty and 'totaal aantal bezoekers' in bezoek.columns and pd.notna(bezoek['totaal aantal bezoekers'].iloc[0]):
    werkelijk = int(bezoek['totaal aantal bezoekers'].iloc[0])
else:
    werkelijk = 0
voorspeld = begroot  # Eenvoudig, model hier toepassen als je wilt

col1.metric("Begroot aantal bezoekers", begroot)
col2.metric("Voorspeld aantal bezoekers", voorspeld)
col3.metric("Werkelijk aantal bezoekers", werkelijk)

# Weersvoorspelling tonen
temp, neerslag, weer_bron = get_weer_voor_dag(datum_sel)
st.markdown(f"""
<div style='background-color:#314259; padding: 1em; border-radius: 8px; color:#fff'>
<b>Weersvoorspelling:</b> max temp {temp:.1f}°C, neerslag {neerslag:.1f} mm<br>
<i>bron: {weer_bron}</i>
</div>
""", unsafe_allow_html=True)

# ---- PRODUCTVOORSPELLING ----

st.markdown("## Voorspeld aantal verkochte producten (per productgroep):")

groep_totaal, producten_per_groep, totaal_voorspeld = voorspelling_per_groep_en_product(
    begroot, temp, neerslag, datum_sel, gekozen_locaties_data
)

for groep in PRODUCTGROEPEN:
    aantal = groep_totaal[groep]
    if aantal > 0:
        st.markdown(
            f"<span style='font-size:1.08em; font-weight:bold; color:#314259'>{groep}: {aantal} stuks</span>",
            unsafe_allow_html=True
        )
        table_html = "<table style='margin-left:2em;font-size:1em;'>"
        for product, a in producten_per_groep[groep]:
            table_html += f"<tr><td style='padding-right:1em;'>- {product}:</td><td style='font-weight:600;'>{a}</td></tr>"
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)
        st.markdown("")  # witregel

st.markdown(
    f"<b>Totaal voorspelde verkoop (bovenstaande groepen): {totaal_voorspeld}</b>",
    unsafe_allow_html=True
)
