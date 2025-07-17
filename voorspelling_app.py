import streamlit as st
import pandas as pd
import numpy as np
import glob, re
import datetime
import requests
from sklearn.linear_model import LinearRegression

# ---- FUNCTIE: OpenWeather max temp & neerslag ----
def get_weather_forecast_openweather(target_date):
    import pytz
    api_key = st.secrets["openweather_key"]
    locatie = "Appeltern,NL"
    url = (
        f"https://api.openweathermap.org/data/2.5/forecast?q={locatie}"
        f"&appid={api_key}&units=metric"
    )
    resp = requests.get(url)
    data = resp.json()
    st.write("OpenWeather data:", data)  # DEBUG: hele JSON tonen

    # Datum checken in UTC, want OpenWeather is UTC!
    dt_today = pd.Timestamp(target_date).replace(hour=0, minute=0, second=0, tzinfo=datetime.timezone.utc)
    temp_max = -99
    rain_total = 0.0
    gevonden = False
    for blok in data.get("list", []):
        blok_dt = pd.to_datetime(blok["dt"], unit="s", utc=True)
        if blok_dt.date() == dt_today.date():
            gevonden = True
            temp_max = max(temp_max, blok["main"].get("temp_max", -99))
            rain_total += blok.get("rain", {}).get("3h", 0.0)
    if not gevonden:
        return None, None
    return temp_max, rain_total

# ---- INLEZEN DATA ----
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
df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

for col in ['aantal', 'netto omzet incl. btw']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        if col == "aantal":
            df[col] = df[col].fillna(0).astype(int)
ALLE_LOCATIES = df['locatie'].unique() if "locatie" in df.columns else []
ALLE_OMZETGROEPEN = df['omzetgroep naam'].unique() if "omzetgroep naam" in df.columns else []
ALLE_PRODUCTEN = df['product name'].unique() if "product name" in df.columns else []

# ---- BEZOEKERSDATA ----
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

# ---- WEERDATA HISTORISCH ----
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

# ---- APP INTERFACE ----
st.set_page_config(layout="wide", page_title="Park horeca omzet- & verkoopvoorspelling")
st.title("Park horeca omzet- & verkoopvoorspelling")

# Datumselectie (keuze uit historie + komende 5 dagen)
alle_historische = bezoekers_df['datum'].dt.date.unique()
vandaag = pd.Timestamp("today").normalize().date()
toekomst = [vandaag + pd.Timedelta(days=i) for i in range(0, 6)]  # vandaag + 5 dagen vooruit
alle_data = sorted(set(list(alle_historische) + [d for d in toekomst]))
datum_sel = st.selectbox("Kies datum", [str(d) for d in alle_data])
datum_sel = pd.to_datetime(datum_sel).date()

# ---- KENGETALLEN ----
bezoek = bezoekers_df.loc[bezoekers_df['datum'].dt.date == datum_sel]
begroot = int(bezoek['begroot aantal bezoekers'].iloc[0]) if not bezoek.empty else 0
werkelijk = int(bezoek['totaal aantal bezoekers'].iloc[0]) if not bezoek.empty else 0

# ---- WEER ----
if datum_sel < vandaag:  # Historische dag
    weer = weerdata[weerdata['datum'].dt.date == datum_sel]
    temp = float(weer['Temp'].iloc[0]) if not weer.empty else None
    neerslag = float(weer['Neerslag'].iloc[0]) if not weer.empty else None
    weer_info = f"Historische KNMI: temperatuur {temp}°C, neerslag {neerslag} mm" if temp is not None else "Geen weerdata gevonden."
else:  # Vandaag of toekomst
    temp, neerslag = get_weather_forecast_openweather(datum_sel)
    if temp is not None:
        weer_info = f"Weersvoorspelling OpenWeather: max temperatuur {temp}°C, totaal neerslag {neerslag} mm"
    else:
        weer_info = "Kon geen OpenWeather-voorspelling ophalen."

# ---- BEOEKERSRUBRIEK ----
col1, col2, col3 = st.columns(3)
col1.metric("Begroot aantal bezoekers", begroot)
col2.metric("Voorspeld aantal bezoekers", begroot)  # Simpel model, later uitbreiden
col3.metric("Werkelijk aantal bezoekers", werkelijk)
st.info(weer_info)

# ---- PRODUCTVOORSPELLING PER PRODUCTGROEP ----
def voorspelling_per_groep(begroot, temp, neerslag, datum_sel, min_dagen=3):
    groepen = ['Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak']
    resultaten = {}
    for groep in groepen:
        df_p = df[(df['omzetgroep naam'] == groep)]
        for col in ['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal']:
            if col not in df_p.columns:
                df_p[col] = np.nan
        df_p = pd.merge(
            df_p, bezoekers_df[['datum', 'begroot aantal bezoekers']], on='datum', how='left'
        )
        df_p = pd.merge(
            df_p, weerdata[['datum', 'Temp', 'Neerslag']], on='datum', how='left'
        )
        df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
        if len(df_p) < min_dagen:
            resultaten[groep] = None
            continue
        X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
        y = df_p['aantal']
        model = LinearRegression().fit(X, y)
        x_pred = pd.DataFrame([{
            'begroot aantal bezoekers': begroot,
            'Temp': temp if temp is not None else 20,
            'Neerslag': neerslag if neerslag is not None else 0,
        }])
        voorspeld = int(round(model.predict(x_pred)[0]))
        resultaten[groep] = max(0, voorspeld)
    return resultaten

voorspeld_per_groep = voorspelling_per_groep(begroot, temp, neerslag, datum_sel)

st.subheader("Voorspeld aantal verkochte producten per groep (parktotaal)")
for groep in ['Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak']:
    aantal = voorspeld_per_groep.get(groep)
    if aantal is None:
        st.warning(f"{groep}: Niet genoeg data voor voorspelling.")
    else:
        st.markdown(f"**{groep}:** {aantal}")

# ---- DEBUG EXTRA: Toon voorspeld_per_groep als table ----
# st.write("DEBUG", voorspeld_per_groep)
