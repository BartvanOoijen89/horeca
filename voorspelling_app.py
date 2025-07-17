import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import os
import glob
import re

# --- Functies en parameters ---
@st.cache_data
def load_data():
    # Alle verkoopbestanden inlezen
    bestanden = glob.glob('verkopen/Verkochte-Producten-*.csv')
    dfs = []
    for bestand in bestanden:
        match = re.search(r'Verkochte-Producten-(.*)_(\d{2}-\d{2}-\d{4})\.csv', bestand)
        if match:
            locatie = match.group(1)
            datum = pd.to_datetime(match.group(2), format='%d-%m-%Y')
        else:
            locatie = 'Onbekend'
            datum = pd.NaT
        df_temp = pd.read_csv(bestand, sep=';', decimal=',')
        df_temp['locatie'] = locatie
        df_temp['datum'] = datum
        df_temp.columns = df_temp.columns.str.strip().str.lower()
        dfs.append(df_temp)
    df = pd.concat(dfs, ignore_index=True)
    for col in ['aantal', 'netto omzet incl. btw']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df_aggr = (
        df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
        .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
        .reset_index()
    )
    return df_aggr

@st.cache_data
def load_bezoekers():
    bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
    bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
    bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
    bezoekers_df['locatie'] = 'Totaal'
    return bezoekers_df

@st.cache_data
def load_weer():
    weerdata_knmi = pd.read_csv(
        'Volkel_weerdata.txt',
        skiprows=47,
        usecols=[1, 11, 21],
        names=['YYYYMMDD', 'TG', 'RH']
    )
    weerdata_knmi['YYYYMMDD'] = weerdata_knmi['YYYYMMDD'].astype(str)
    weerdata_knmi['datum'] = pd.to_datetime(weerdata_knmi['YYYYMMDD'], format='%Y%m%d', errors='coerce')
    weerdata_knmi['TG'] = pd.to_numeric(weerdata_knmi['TG'], errors='coerce')
    weerdata_knmi['RH'] = pd.to_numeric(weerdata_knmi['RH'], errors='coerce')
    weerdata_knmi['Temp'] = weerdata_knmi['TG'] / 10
    weerdata_knmi['Neerslag'] = weerdata_knmi['RH'].clip(lower=0) / 10
    return weerdata_knmi[['datum', 'Temp', 'Neerslag']].copy()

def merge_data(df_aggr, bezoekers_df, weerdata):
    bezoekers_park = bezoekers_df[['datum', 'begroot aantal bezoekers', 'totaal aantal bezoekers']]
    df_merged = pd.merge(df_aggr, bezoekers_park, on='datum', how='left')
    df_merged = pd.merge(df_merged, weerdata, on='datum', how='left')
    return df_merged

def voorspellingen_per_locatie(df_merged, locatie, datum_voorspelling, min_dagen=3):
    out = {}
    df = df_merged.copy()
    producten = df[df['locatie'] == locatie]['product name'].unique()
    omzetgroepen = df[df['locatie'] == locatie]['omzetgroep naam'].unique()
    results_per_omzetgroep = {}
    totaal_omzet = 0

    # Input voor voorspelling
    bezoekers = df[df['datum'] == datum_voorspelling]['begroot aantal bezoekers'].max()
    temp = df[df['datum'] == datum_voorspelling]['Temp'].max()
    neerslag = df[df['datum'] == datum_voorspelling]['Neerslag'].max()
    if np.isnan(bezoekers): bezoekers = st.number_input("Bezoekers", min_value=0, step=1, value=200)
    if np.isnan(temp): temp = st.number_input("Temperatuur", value=19.0)
    if np.isnan(neerslag): neerslag = st.number_input("Neerslag (mm)", value=0.0)

    for omzetgroep in omzetgroepen:
        group_results = []
        groepdata = df[(df['locatie'] == locatie) & (df['omzetgroep naam'] == omzetgroep)]
        for product in groepdata['product name'].unique():
            df_p = groepdata[groepdata['product name'] == product]
            # Vereist voldoende trainingsdagen
            df_train = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
            if len(df_train) < min_dagen:
                continue
            X = df_train[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
            y = df_train['aantal']
            model = LinearRegression().fit(X, y)
            voorspeld = int(round(model.predict([[bezoekers, temp, neerslag]])[0]))
            if voorspeld > 0:
                group_results.append({'product name': product, 'verwacht aantal': voorspeld})
        if group_results:
            results_per_omzetgroep[omzetgroep] = group_results

    # Omzet-voorspelling (totaal per locatie)
    omzet_df = df[(df['locatie'] == locatie) & (df['netto omzet incl. btw'] > 0)]
    omzet_train = omzet_df.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'netto omzet incl. btw'])
    totaal_omzet_pred = ""
    if len(omzet_train) >= min_dagen:
        X = omzet_train[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
        y = omzet_train['netto omzet incl. btw']
        omzet_model = LinearRegression().fit(X, y)
        omzet_voorspeld = float(omzet_model.predict([[bezoekers, temp, neerslag]])[0])
        if omzet_voorspeld > 0:
            totaal_omzet_pred = f"€ {omzet_voorspeld:.2f}"

    return results_per_omzetgroep, totaal_omzet_pred

# === STREAMLIT APP START ===

st.title("Verkoop- en Omzetvoorspelling per locatie")

# --- Data laden ---
with st.spinner("Data inladen..."):
    df_aggr = load_data()
    bezoekers_df = load_bezoekers()
    weerdata = load_weer()
    df_merged = merge_data(df_aggr, bezoekers_df, weerdata)

# --- Keuzes voor gebruiker ---
alle_locaties = sorted(df_merged['locatie'].unique())
alle_datums = sorted(df_merged['datum'].dt.date.unique())

locatie = st.selectbox("Kies een locatie", alle_locaties)
datum_strs = [str(d) for d in alle_datums]
datum_voorspelling = pd.to_datetime(st.selectbox("Kies een datum", datum_strs))

# --- Resultaat tonen ---
with st.spinner(f"Voorspellingen berekenen voor {locatie}..."):
    resultaten, omzet = voorspellingen_per_locatie(df_merged, locatie, datum_voorspelling)
    for omzetgroep, products in resultaten.items():
        st.markdown(f"**-- {omzetgroep} --**")
        result_df = pd.DataFrame(products)
        result_df = result_df[result_df['verwacht aantal'] > 0]
        if not result_df.empty:
            st.table(result_df.set_index("product name"))
            st.markdown(f"Totaal aantal: {result_df['verwacht aantal'].sum()}")
    if omzet:
        st.success(f"**>>> Verwachte omzet totaal voor {locatie}: {omzet}**")
    else:
        st.warning("Onvoldoende data om omzet te voorspellen voor deze locatie en datum.")

st.caption("Alleen producten/omzetgroepen met voldoende data worden getoond.")