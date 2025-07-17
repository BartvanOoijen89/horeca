import streamlit as st
import pandas as pd
import numpy as np
import glob
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression

# ===== 1. INLEZEN DATA =====

# Verkoopbestanden inlezen
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

# Aggregatie
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)
ALLE_OMZETGROEPEN = [
    'Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak'
]

# Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

# Weerdata
weerdata_knmi = pd.read_csv(
    'Volkel_weerdata.txt', skiprows=47, usecols=[1, 11, 21], names=['YYYYMMDD', 'TG', 'RH']
)
weerdata_knmi['YYYYMMDD'] = weerdata_knmi['YYYYMMDD'].astype(str)
weerdata_knmi['datum'] = pd.to_datetime(weerdata_knmi['YYYYMMDD'], format='%Y%m%d', errors='coerce')
weerdata_knmi['Temp'] = pd.to_numeric(weerdata_knmi['TG'], errors='coerce') / 10
weerdata_knmi['Neerslag'] = pd.to_numeric(weerdata_knmi['RH'], errors='coerce').clip(lower=0) / 10
weerdata = weerdata_knmi[['datum', 'Temp', 'Neerslag']].copy()

# Locatienamen
ALLE_LOCATIES = {
    'Onze Entree': 'Entree',
    'Oranjerie': 'Oranjerie',
    'Bloemenkas': 'Bloemenkas'
}

# ===== 2. UI: DATUM EN LOCATIE =====

st.title("🍽️ Horeca Voorspelling")

vandaag = datetime.now().date()
min_datum = min(bezoekers_df['datum'].dt.date.unique())
max_datum = vandaag + timedelta(days=5)

datum_sel = st.date_input(
    "Kies datum", value=vandaag if vandaag <= max_datum else max_datum,
    min_value=min_datum, max_value=max_datum
)

locaties_ui = st.multiselect(
    "Kies locatie(s)",
    options=list(ALLE_LOCATIES.keys()),
    default=['Onze Entree']
)
gekozen_locaties = [ALLE_LOCATIES[l] for l in locaties_ui]

# ===== 3. WEERSVOORSPELLING =====

def get_weather_openweather(dt):
    # Voor vandaag & toekomst: OpenWeather
    import requests
    api_key = st.secrets["openweather_key"]
    url = (
        f"https://api.openweathermap.org/data/2.5/forecast?q=Appeltern,NL&units=metric&appid={api_key}&lang=nl"
    )
    r = requests.get(url)
    data = r.json()
    # Pak max temperatuur per dag voor 5 dagen (3-uurs blokken)
    voorsp = {}
    for blok in data["list"]:
        tijd = datetime.fromtimestamp(blok["dt"])
        dag = tijd.date()
        tmax = blok["main"]["temp_max"]
        neerslag = blok.get("rain", {}).get("3h", 0.0)
        if dag not in voorsp:
            voorsp[dag] = {'tmax': tmax, 'neerslag': neerslag}
        else:
            voorsp[dag]['tmax'] = max(voorsp[dag]['tmax'], tmax)
            voorsp[dag]['neerslag'] += neerslag
    # Zoek voor dt
    if dt in voorsp:
        return voorsp[dt]['tmax'], voorsp[dt]['neerslag']
    return np.nan, np.nan

def get_weather(datum):
    if datum >= vandaag:
        try:
            return get_weather_openweather(datum)
        except:
            return np.nan, np.nan
    else:
        blok = weerdata[weerdata['datum'].dt.date == datum]
        if blok.empty:
            return np.nan, np.nan
        return blok['Temp'].iloc[0], blok['Neerslag'].iloc[0]

temp, neerslag = get_weather(datum_sel)
st.info(f"Weerverwachting: Max temp: {temp:.1f}°C, Neerslag: {neerslag:.1f} mm")

# ===== 4. BEZOEKERS =====

bezoek = bezoekers_df[bezoekers_df['datum'].dt.date == datum_sel]
begroot = int(bezoek['begroot aantal bezoekers'].sum()) if not bezoek.empty else 0
werkelijk = int(bezoek['totaal aantal bezoekers'].sum()) if not bezoek.empty else 0

# Dummy bezoekersvoorspelling (hier kun je je ML-model plaatsen)
def bezoekers_model(begroot, temp, neerslag):
    # Lineair model, vervang door echt model indien gewenst
    if begroot == 0 or np.isnan(temp) or np.isnan(neerslag):
        return 0
    return int(round(begroot * (0.8 + 0.02 * temp - 0.01 * neerslag)))

voorspeld_bezoekers = bezoekers_model(begroot, temp, neerslag)

st.subheader("Bezoekersprognose")
col1, col2, col3 = st.columns(3)
col1.metric("Begroot", begroot)
col2.metric("Voorspeld", voorspeld_bezoekers)
col3.metric("Werkelijk", werkelijk)

# ===== 5. OMZET =====

def omzet_werkelijk(locaties, datum):
    totaal = df_aggr[
        (df_aggr['locatie'].isin(locaties)) &
        (df_aggr['datum'].dt.date == datum)
    ]['netto omzet incl. btw'].sum()
    return totaal

def omzet_voorspeld(locaties, datum, begroot, temp, neerslag):
    totaal = 0
    for locatie in locaties:
        # Gebruik bestaand model/data: lineaire regressie over alle producten/omzetgroepen
        df_p = df_aggr[
            (df_aggr['locatie'] == locatie)
        ].dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'netto omzet incl. btw'])
        if len(df_p) < 3:
            continue
        X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
        y = df_p['netto omzet incl. btw']
        model = LinearRegression().fit(X, y)
        x_pred = pd.DataFrame({
            'begroot aantal bezoekers': [begroot],
            'Temp': [temp],
            'Neerslag': [neerslag]
        })
        pred_omzet = model.predict(x_pred)[0]
        totaal += max(0, pred_omzet)
    return int(round(totaal))

st.subheader("Omzet")
col1, col2 = st.columns(2)
col1.metric("Voorspeld", f"€ {omzet_voorspeld(gekozen_locaties, datum_sel, begroot, temp, neerslag):,}")
col2.metric("Werkelijk", f"€ {omzet_werkelijk(gekozen_locaties, datum_sel):,}")

# ===== 6. PRODUCTVOORSPELLING =====

def voorspelling_per_groep(begroot, temp, neerslag, datum, locaties):
    resultaat = {groep: [] for groep in ALLE_OMZETGROEPEN}
    for groep in ALLE_OMZETGROEPEN:
        producten = df_aggr[
            (df_aggr['omzetgroep naam'] == groep) &
            (df_aggr['locatie'].isin(locaties))
        ]['product name'].unique()
        for prod in producten:
            df_p = df_aggr[
                (df_aggr['omzetgroep naam'] == groep) &
                (df_aggr['product name'] == prod) &
                (df_aggr['locatie'].isin(locaties))
            ].dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
            if len(df_p) < 3:
                continue
            X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_p['aantal']
            model = LinearRegression().fit(X, y)
            x_pred = pd.DataFrame({
                'begroot aantal bezoekers': [begroot],
                'Temp': [temp],
                'Neerslag': [neerslag]
            })
            aantal = int(round(model.predict(x_pred)[0]))
            aantal = max(0, aantal)
            if aantal > 0:
                resultaat[groep].append({'product name': prod, 'verwacht aantal': aantal})
    return resultaat

voorspeld_per_groep = voorspelling_per_groep(begroot, temp, neerslag, datum_sel, gekozen_locaties)

st.subheader("Productvoorspelling per groep")
for groep in ALLE_OMZETGROEPEN:
    if voorspeld_per_groep[groep]:
        st.markdown(f"**{groep}**")
        st.dataframe(pd.DataFrame(voorspeld_per_groep[groep]))

# ===== EINDE =====
