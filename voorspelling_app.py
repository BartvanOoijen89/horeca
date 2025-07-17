import streamlit as st
import pandas as pd
import glob
import re
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
import requests

st.set_page_config(layout="wide", page_title="Park horeca omzet- & verkoopvoorspelling")

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

# === NIET MEER TONEN/VOORSPELLEN PRODUCTEN (filter na inlezen én bij ophalen unieke producten) ===
PRODUCTEN_VERBORGEN = set([
    'Kaasbroodje',
    'Koffie met Appeltaart',
    'Slagroom',
    'Fritessaus zakje',
    'Ketchup zakje',
    'Mosterd zakje',
    'Croissant jam/hagelslag',
    'Kids boterham kaas/jam/hagel',
    'Tafelbroodje',
    'Croissant los'
])
df = df[~df['product name'].isin(PRODUCTEN_VERBORGEN)]

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
LOCATIE_KLEUREN = {
    "Onze Entree": "#295687",  # blauw
    "Oranjerie": "#237b57",    # groen
    "Bloemenkas": "#df8426",   # oranje
}

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
    # Ook hier filteren!
    producten = df_aggr[
        (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == groep)
    ]['product name'].sort_values().unique()
    # Verwijder ongewenste producten voor 100% zekerheid
    return [p for p in producten if p not in PRODUCTEN_VERBORGEN]

def voorspelling_en_werkelijk_per_product(locatie, groep, datum_sel, begroot, temp, neerslag):
    producten = alle_producten_per_locatie_groep(locatie, groep)
    werkelijk_df = df_aggr[
        (df_aggr['datum'] == datum_sel) & (df_aggr['locatie'] == locatie) & (df_aggr['omzetgroep naam'] == groep)
    ]
    daadwerkelijk_dict = dict(zip(werkelijk_df['product name'], werkelijk_df['aantal']))

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
        daadwerkelijk_aantal = daadwerkelijk_dict.get(product)
        if voorspeld_aantal > 0 or daadwerkelijk_aantal is not None:
            if daadwerkelijk_aantal is not None:
                resultaat.append((product, voorspeld_aantal, daadwerkelijk_aantal))
            else:
                resultaat.append((product, voorspeld_aantal, None))
    return resultaat

# ---- START UI ----

st.markdown("""
    <style>
    body, .main, .block-container { background: #fff !important; }
    </style>
    """, unsafe_allow_html=True)

st.markdown(f"""
# Park horeca omzet- & verkoopvoorspelling

### {datum_sel.strftime('%d-%m-%Y')}
""")

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

# --- Weersvoorspelling als metric/info block ---
colw1, colw2 = st.columns(2)
with colw1:
    st.markdown("""
        <div style='background:#fff; border-radius:8px; box-shadow:0 1px 8px #0001; padding:1em; margin-bottom:1.5em;'>
        <div style='font-weight:700;font-size:1.13em; color:#223155; margin-bottom:.7em;'>WEERSVOORSPELLING</div>
        <div style='font-size:1.03em; color:#223155;'><b>Maximale temperatuur</b> 🌡️ {0:.1f} °C</div>
        <div style='font-size:1.03em; color:#223155;'><b>Totale Neerslag</b> 🌧️ {1:.1f} mm</div>
        </div>
    """.format(temp, neerslag), unsafe_allow_html=True)

# ---- PRODUCTVOORSPELLING & WERKELIJKE VERKOOP PER LOCATIE & GROEP ----

for loc_key, loc_val in zip(gekozen_locs_keys, gekozen_locaties_data):
    hoofdkleur = LOCATIE_KLEUREN.get(loc_key, "#295687")
    st.markdown(
        f"<div style='font-size:1.38em;font-weight:800;color:{hoofdkleur};margin-top:1.5em;margin-bottom:0.5em;letter-spacing:0.01em;'>{loc_key}</div>",
        unsafe_allow_html=True
    )
    for groep in PRODUCTGROEPEN:
        alle_prod = alle_producten_per_locatie_groep(loc_val, groep)
        lijst = voorspelling_en_werkelijk_per_product(loc_val, groep, datum_sel, begroot, temp, neerslag)
        if len(lijst) == 0:
            continue
        st.markdown(
            f"<div class='grp-title' style='color:{hoofdkleur};'>{loc_key} - {groep}</div>",
            unsafe_allow_html=True
        )
        tblcss = f"""
        <style>
        .vp-table3-{loc_val.replace(' ', '').lower()} th {{
            background: {hoofdkleur};
            color: #fff;
        }}
        .vp-table3-{loc_val.replace(' ', '').lower()} {{
            border-collapse: collapse;
            width: 500px;
            min-width: 350px;
            margin-bottom: 1.2em;
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 8px #0001;
        }}
        .vp-table3-{loc_val.replace(' ', '').lower()} th, 
        .vp-table3-{loc_val.replace(' ', '').lower()} td {{
            border: 1px solid #e1e4ea;
            padding: 7px 13px 7px 13px;
            font-size: 1em;
        }}
        .vp-table3-{loc_val.replace(' ', '').lower()} th {{
            border: none;
        }}
        .vp-table3-{loc_val.replace(' ', '').lower()} td:first-child {{
            font-weight: 500;
            color: {hoofdkleur};
            background: #eef2f6;
        }}
        .vp-table3-{loc_val.replace(' ', '').lower()} td {{
            color: #222;
            background: #fff;
        }}
        </style>
        """
        st.markdown(tblcss, unsafe_allow_html=True)
        toon_werkelijk = any(w is not None for _, _, w in lijst)
        table_html = f"<table class='vp-table3-{loc_val.replace(' ', '').lower()}'>"
        table_html += "<tr><th>Productnaam</th><th>Voorspeld aantal verkopen</th>"
        if toon_werkelijk:
            table_html += "<th>Daadwerkelijk aantal verkopen</th>"
        table_html += "</tr>"
        for product, voorspeld, werkelijk in lijst:
            table_html += f"<tr><td>{product}</td><td>{voorspeld}</td>"
            if toon_werkelijk:
                table_html += f"<td>{werkelijk if werkelijk is not None else ''}</td>"
            table_html += "</tr>"
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)
