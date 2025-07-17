import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import glob
import re
import os

st.set_page_config(page_title="Horeca Omzet & Bezoekers Voorspelling", layout="wide")
st.title("🌳 Horeca Voorspellingen — Park Totaal & Locaties")

### === DATA INLEZEN EN VOORBEREIDEN ===

# 1. Verkoopbestanden inlezen
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

# 2. Agregeren op dag/locatie/omzetgroep/product
df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)

ALLE_LOCATIES = df['locatie'].unique()
ALLE_OMZETGROEPEN = df['omzetgroep naam'].unique()

# 3. Bezoekersdata
bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

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

# 5. Koppelen bezoekers/weerdata aan verkoopdata (park-totaal bezoekers)
bezoekers_park = bezoekers_df.groupby('datum').agg({
    'begroot aantal bezoekers': 'sum',
    'totaal aantal bezoekers': 'sum'
}).reset_index()
df_aggr = pd.merge(df_aggr, bezoekers_park, on='datum', how='left')
df_aggr = pd.merge(df_aggr, weerdata, on='datum', how='left')

### === STREAMLIT INTERFACE: DATUM & LOCATIE SELECTIE ===

col1, col2, col3 = st.columns([2, 2, 4])

with col1:
    datums_beschikbaar = sorted(list(set(df_aggr['datum'].dropna().unique()) | set(bezoekers_park['datum'].unique())))
    datum = st.date_input("Kies dag voor voorspelling", value=max(datums_beschikbaar), min_value=min(datums_beschikbaar), max_value=max(datums_beschikbaar))

with col2:
    locaties_te_kiezen = list(ALLE_LOCATIES)
    locaties_selected = st.multiselect("Toon locaties (standaard Park totaal)", opties:=["Park Totaal"] + locaties_te_kiezen, default=["Park Totaal"])

with col3:
    tonen_omzet = st.checkbox("Toon omzetvoorspelling", value=True)

### === BASISVARIABELEN VOOR DE DAG ===

dag = pd.Timestamp(datum)
dag_bezoek = bezoekers_park.loc[bezoekers_park['datum'] == dag]
if not dag_bezoek.empty:
    begroot = int(dag_bezoek['begroot aantal bezoekers'].values[0])
    werkelijk = int(dag_bezoek['totaal aantal bezoekers'].values[0])
else:
    begroot = 0
    werkelijk = 0

dag_weer = weerdata.loc[weerdata['datum'] == dag]
if not dag_weer.empty:
    temp = float(dag_weer['Temp'].values[0])
    neerslag = float(dag_weer['Neerslag'].values[0])
else:
    temp = 20.0
    neerslag = 0.0

### === VOORSPELLINGSFUNCTIES ===

def voorspel_product(df_p, begroot, temp, neerslag, min_dagen=3):
    df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal', 'netto omzet incl. btw'])
    if len(df_p) < min_dagen:
        return None, None
    X = df_p[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
    y = df_p['aantal']
    y_omzet = df_p['netto omzet incl. btw']
    model = LinearRegression().fit(X, y)
    model_omzet = LinearRegression().fit(X, y_omzet)
    x_voorspel = pd.DataFrame({'begroot aantal bezoekers': [begroot], 'Temp': [temp], 'Neerslag': [neerslag]})
    aantal = int(round(model.predict(x_voorspel)[0]))
    aantal = max(0, aantal)
    omzet = model_omzet.predict(x_voorspel)[0]
    omzet = max(0, omzet)
    return aantal, omzet

def park_omzet_en_bezoek(dag, tonen_omzet):
    # Park-totaal werkelijke omzet uit alle locaties samen (alle verkoopbestanden)
    df_dag = df_aggr[df_aggr['datum'] == dag]
    werkelijke_omzet = df_dag['netto omzet incl. btw'].sum()
    return werkelijke_omzet

### === PARK TOTAAL VOORSPELLING ===

with st.expander("🚩 Park totaal — bezoekers en omzet", expanded=True):
    st.write(f"### Park totaal voor: {dag.date()}")
    st.write(f"Begroot aantal bezoekers: **{begroot}**")
    st.write(f"Werkelijk aantal bezoekers: **{werkelijk}**")
    st.write(f"Weersverwachting: temperatuur **{temp}°C**, neerslag **{neerslag} mm**")
    if tonen_omzet:
        werkelijke_omzet = park_omzet_en_bezoek(dag, tonen_omzet)
        st.write(f"Werkelijke omzet (alle locaties): **€ {werkelijke_omzet:,.2f}**")
    st.info("Product- en omzetvoorspelling volgt per locatie hieronder. Selecteer locaties in het menu.")

### === PER LOCATIE: PRODUCT- EN OMZETVOORSPELLING ===

for locatie in locaties_selected:
    if locatie == "Park Totaal":
        continue
    st.write(f"## 📍 Voorspellingen voor {locatie} op {dag.date()}")
    totaal_omzet = 0
    totaal_aantal = 0
    productresultaten = []

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
            aantal, omzet = voorspel_product(df_p, begroot, temp, neerslag, min_dagen=3)
            if (aantal is not None) and (aantal > 0):
                resultaten.append({'Product': prod, 'Omzetgroep': omzetgroep, 'Aantal voorspeld': aantal})
                totaal_aantal += aantal
                if tonen_omzet:
                    totaal_omzet += omzet
        if resultaten:
            productresultaten.extend(resultaten)

    if productresultaten:
        df_toon = pd.DataFrame(productresultaten)
        st.dataframe(df_toon[['Omzetgroep', 'Product', 'Aantal voorspeld']].sort_values(['Omzetgroep', 'Product']), use_container_width=True)
    else:
        st.info("Geen productvoorspellingen voor deze locatie (onvoldoende data).")

    st.write(f"**Totaal voorspeld aantal producten:** {totaal_aantal}")
    if tonen_omzet and totaal_omzet > 0:
        st.write(f"**Voorspelde omzet {locatie}:** € {totaal_omzet:,.2f}")

### === EINDE ===

st.caption("© 2024-2025 | Voorspellingen d.m.v. Lineaire Regressie per product, per locatie. Contact: Bart")
