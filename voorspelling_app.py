import streamlit as st
import pandas as pd
import numpy as np
import glob
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import requests

# ---- THEMA & CONTRAST ----
st.set_page_config(layout="wide", page_title="Park horeca omzet- & verkoopvoorspelling")
st.markdown("""
<style>
body, .stApp {background: #fff !important;}
h1, h2, h3, h4, h5, h6,
.stApp header, .stApp [data-testid="stSidebar"] label,
.stApp [data-testid="stMarkdownContainer"],
.st-emotion-cache-10trblm, .st-emotion-cache-1v0mbdj,
label, .stSelectbox label, .stDateInput label {
    color: #182242 !important;
    font-weight: 700 !important;
}
.st-bw { color: #182242 !important; }
.grp-title { color: #fff !important; }
</style>
""", unsafe_allow_html=True)

# ---- DATA INLEZEN ----

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

df_aggr = (
    df.groupby(['datum', 'locatie', 'omzetgroep naam', 'product name'])
    .agg({'aantal': 'sum', 'netto omzet incl. btw': 'sum'})
    .reset_index()
)

bezoekers_df = pd.read_excel('Bezoekersdata.xlsx')
bezoekers_df.columns = bezoekers_df.columns.str.strip().str.lower()
bezoekers_df['datum'] = pd.to_datetime(bezoekers_df['datum'])
if 'locatie' not in bezoekers_df.columns:
    bezoekers_df['locatie'] = 'Totaal'

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

PRODUCTGROEPEN = [
    'Broodjes', 'Wraps', 'Soepen', 'Salades', 'Kleine trek', 'Snacks', 'Gebak'
]
LOCATIE_MAPPING = {
    'Onze Entree': 'Entree',
    'Oranjerie': 'Oranjerie',
    'Bloemenkas': 'Bloemenkas'
}
ALLE_OMZETGROEPEN = PRODUCTGROEPEN
ALLE_LOCATIES = df['locatie'].unique()

# PRODUCTEN die niet meer getoond mogen worden:
EXCLUDE_PRODUCTS = set([
    'Kaasbroodje', 'Koffie met Appeltaart', 'Slagroom', 'Fritessaus zakje', 'Ketchup zakje',
    'Mosterd zakje', 'Croissant jam/hagelslag', 'Kids boterham kaas/jam/hagel',
    'Tafelbroodje', 'Croissant los'
])

# ---- DATUM SELECTIE ----

vandaag = datetime.now().date()
min_datum = min(bezoekers_df['datum'].dt.date.unique())
max_datum = vandaag + timedelta(days=5)

datum_sel = st.date_input(
    "Kies datum",
    value=vandaag if vandaag <= max_datum else max_datum,
    min_value=min_datum,
    max_value=max_datum,
    key="kies_datum"
)
datum_sel = pd.Timestamp(datum_sel)

# ---- LOCATIE SELECTIE ----

st.markdown("#### Selecteer extra locatie (optioneel, maximaal 1):")
overige_locaties = [loc for loc in LOCATIE_MAPPING.keys() if loc != "Onze Entree"]
extra_locatie = st.selectbox(
    "Tweede locatie (optioneel):", 
    options=["Geen"] + overige_locaties,
    index=0,
    key="loc_select"
)
gekozen_locs_keys = ["Onze Entree"]
if extra_locatie != "Geen":
    gekozen_locs_keys.append(extra_locatie)
gekozen_locaties_data = [LOCATIE_MAPPING[loc] for loc in gekozen_locs_keys]

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
        else:
            temp, neerslag = 0.0, 0.0
    else:
        temp, neerslag = get_weather_forecast_openweather(datum)
    return temp, neerslag, None

# ---- BEZOEKERSVOORSPELLING (met begroting) ----

def voorspel_bezoekers_met_begroting(begroot, temp, neerslag, datum_sel):
    df_hist = bezoekers_df[
        (bezoekers_df['datum'] < datum_sel) &
        pd.notnull(bezoekers_df['totaal aantal bezoekers'])
    ].copy()
    df_hist = pd.merge(df_hist, weerdata, on='datum', how='left')
    df_hist = df_hist.dropna(subset=['begroot aantal bezoekers', 'totaal aantal bezoekers', 'Temp', 'Neerslag'])
    if len(df_hist) < 8:
        return begroot
    X = df_hist[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
    y = df_hist['totaal aantal bezoekers']
    model = LinearRegression().fit(X, y)
    x_voorspel = pd.DataFrame({'begroot aantal bezoekers': [begroot], 'Temp': [temp], 'Neerslag': [neerslag]})
    voorspeld = int(round(model.predict(x_voorspel)[0]))
    return max(0, voorspeld)

# ---- VOORSPELLINGSMODEL: per groep & product ----

def alle_producten_per_locatie_groep(locatie, groep):
    producten = df_aggr[
        (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == groep)
    ]['product name'].sort_values().unique()
    # Filter producten die uitgesloten zijn
    return [p for p in producten if p not in EXCLUDE_PRODUCTS]

def voorspelling_en_werkelijk_per_product(locatie, groep, datum_sel, begroot, temp, neerslag):
    producten = alle_producten_per_locatie_groep(locatie, groep)
    # Werkelijke verkoop op deze dag
    werkelijk_df = df_aggr[
        (df_aggr['datum'] == datum_sel) & (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == groep)
    ]
    daadwerkelijk_dict = dict(zip(werkelijk_df['product name'], werkelijk_df['aantal']))

    # Voorspelling per product
    voorspeld_dict = {}
    df_p = df_aggr[
        (df_aggr['datum'] < datum_sel) &
        (df_aggr['omzetgroep naam'] == groep) &
        (df_aggr['locatie'] == locatie)
    ]
    if len(df_p) >= 3:
        df_p = pd.merge(df_p, bezoekers_df[['datum', 'begroot aantal bezoekers']], on='datum', how='left')
        df_p = pd.merge(df_p, weerdata, on='datum', how='left')
        df_p = df_p.dropna(subset=['begroot aantal bezoekers', 'Temp', 'Neerslag', 'aantal'])
        for product in producten:
            df_prod = df_p[df_p['product name'] == product]
            if len(df_prod) < 3:
                voorspeld_dict[product] = 0
            else:
                X = df_prod[['begroot aantal bezoekers', 'Temp', 'Neerslag']]
                y = df_prod['aantal']
                model = LinearRegression().fit(X, y)
                x_voorspel = pd.DataFrame({'begroot aantal bezoekers': [begroot], 'Temp': [temp], 'Neerslag': [neerslag]})
                aantal = int(round(model.predict(x_voorspel)[0]))
                voorspeld_dict[product] = max(0, aantal)
    else:
        for product in producten:
            voorspeld_dict[product] = 0

    resultaat = []
    for product in producten:
        voorspeld_aantal = voorspeld_dict.get(product, 0)
        daadwerkelijk_aantal = daadwerkelijk_dict.get(product, None)
        resultaat.append((product, voorspeld_aantal, daadwerkelijk_aantal))
    return resultaat

# ---- UNIEKE KLEUR PER LOCATIE ----
LOCATIE_KLEUREN = {
    "Onze Entree": "#294788",
    "Oranjerie": "#61964b",
    "Bloemenkas": "#c08545"
}

# ---- START UI ----

st.markdown(f"""
# <span style='color:#182242;'>Park horeca omzet- & verkoopvoorspelling</span>
""", unsafe_allow_html=True)
st.markdown(f"""
### <span style='color:#182242;'>{datum_sel.strftime('%d-%m-%Y')}</span>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

bezoek = bezoekers_df[bezoekers_df['datum'] == datum_sel]
begroot = int(bezoek['begroot aantal bezoekers'].iloc[0]) if not bezoek.empty else 0
if not bezoek.empty and 'totaal aantal bezoekers' in bezoek.columns and pd.notna(bezoek['totaal aantal bezoekers'].iloc[0]):
    werkelijk = int(bezoek['totaal aantal bezoekers'].iloc[0])
else:
    werkelijk = 0

temp, neerslag, _ = get_weer_voor_dag(datum_sel)
voorspeld_met_begroting = voorspel_bezoekers_met_begroting(begroot, temp, neerslag, datum_sel)

col1.metric("Begroot aantal bezoekers", begroot)
col2.metric("Werkelijk aantal bezoekers", werkelijk)
col3.metric("Voorspeld aantal bezoekers", voorspeld_met_begroting)

# Nieuwe stijl voor weersvoorspelling blok
with st.container():
    st.markdown(f"""
    <div style='background:#fff; border:2px solid #e3e8f0; border-radius: 12px; padding:1em; margin-bottom:1em; width:330px;'>
        <span style='font-weight:800; color:#223155; font-size:1.08em;'>WEERSVOORSPELLING</span><br>
        <span style='font-size:1.03em; margin-top:0.5em; display:inline-block;'>Maximale temperatuur 🌡️ <b>{temp:.1f} °C</b></span><br>
        <span style='font-size:1.03em;'>Totale neerslag 🌧️ <b>{neerslag:.1f} mm</b></span>
    </div>
    """, unsafe_allow_html=True)

# ---- PRODUCTVOORSPELLING & WERKELIJKE VERKOOP PER LOCATIE & GROEP ----

TBL_STYLE = """
<style>
.grp-title {
    font-size: 1.14em;
    font-weight: 800;
    margin-bottom: 0.4em;
    margin-top: 1.4em;
    letter-spacing: 0.02em;
    padding: 0.4em 0.8em;
    border-radius: 8px 8px 0 0;
    display: inline-block;
}
.vp-table3 {
    border-collapse: collapse;
    width: 500px;
    min-width: 350px;
    margin-bottom: 1.2em;
    background: #f7fafd;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 8px #0001;
}
.vp-table3 th, .vp-table3 td {
    border: 1px solid #e1e4ea;
    padding: 7px 13px 7px 13px;
    font-size: 1em;
}
.vp-table3 th {
    background: #223155;
    color: #fff;
    font-weight: bold;
    border: none;
}
.vp-table3 td:first-child {
    font-weight: 500;
    color: #223155;
    background: #dde3eb;
}
.vp-table3 td {
    color: #222;
    background: #f7fafd;
}
</style>
"""
st.markdown(TBL_STYLE, unsafe_allow_html=True)

for loc_key, loc_val in zip(gekozen_locs_keys, gekozen_locaties_data):
    basiskleur = LOCATIE_KLEUREN.get(loc_key, "#223155")
    for groep in PRODUCTGROEPEN:
        alle_prod = alle_producten_per_locatie_groep(loc_val, groep)
        if len(alle_prod) == 0:
            continue
        st.markdown(
            f"<div class='grp-title' style='background:{basiskleur};color:#fff'>{loc_key} - {groep}</div>",
            unsafe_allow_html=True
        )
        lijst = voorspelling_en_werkelijk_per_product(loc_val, groep, datum_sel, begroot, temp, neerslag)
        # Check of er in deze groep daadwerkelijk verkopen zijn (voor de kolom "Daadwerkelijk")
        is_data = any((w is not None) for _, _, w in lijst)
        # Tabel tonen
        table_html = """
        <table class='vp-table3'>
            <tr>
                <th>Productnaam</th>
                <th>Voorspeld aantal verkopen</th>""" + ("""<th>Daadwerkelijk aantal verkopen</th>""" if is_data else "") + """
            </tr>
        """
        for product, voorspeld, werkelijk in lijst:
            # Toon alleen producten als ze een voorspeld of werkelijke waarde hebben, of altijd als ze op kaart staan
            if (voorspeld > 0) or (werkelijk and werkelijk > 0) or (werkelijk == 0):
                table_html += f"<tr><td>{product}</td><td>{voorspeld}</td>"
                if is_data:
                    table_html += f"<td>{werkelijk if werkelijk is not None else ''}</td>"
                table_html += "</tr>"
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)
