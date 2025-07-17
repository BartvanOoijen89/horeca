import streamlit as st
import pandas as pd
import datetime

# Laden van bezoekersdata
bezoekers = pd.read_excel('Bezoekersdata.xlsx')
bezoekers['Datum'] = pd.to_datetime(bezoekers['Datum'])

# Kalenderkeuze (alle dagen mogelijk)
min_date = bezoekers['Datum'].min()
max_date = bezoekers['Datum'].max()
vandaag = datetime.date.today()
datum = st.date_input("Selecteer een dag", value=vandaag, min_value=min_date, max_value=max_date)

# Filter op geselecteerde datum
dagdata = bezoekers[bezoekers['Datum'] == pd.Timestamp(datum)]
if dagdata.empty:
    begroot = "-"
    werkelijk = "-"
else:
    begroot = int(dagdata['Begroot aantal bezoekers'].iloc[0])
    werkelijk = int(dagdata['Totaal aantal bezoekers'].iloc[0])

# ==== Hier komt je bezoekersvoorspelling-model ====
# >>>> Simpele placeholder (geef hier je ML-model of formule voor voorspelling):
def voorspel_bezoekers(datum, weersdata=None):
    # Hier je echte model! Nu gewoon als voorbeeld:
    if begroot != "-":
        return round(begroot * 1.05)  # Simpele truc: voorspelling is 5% meer dan begroot
    else:
        return "-"

voorspeld = voorspel_bezoekers(datum)

# ==== Omzetvoorspelling ====
def voorspel_omzet(aantal_bezoekers):
    if aantal_bezoekers == "-" or aantal_bezoekers == 0:
        return "-"
    else:
        # Simpele vuistregel (voorbeeld): €4,50 per bezoeker omzet
        return round(aantal_bezoekers * 4.5, 2)

omzet_voorspelling = voorspel_omzet(voorspeld)

# ==== Werkelijke omzet ====
# Hier moet je even je werkelijke omzetdata koppelen per dag als je die hebt (eventueel uit een andere sheet)

# ===== Streamlit output =====
st.title(f"Park-voorspelling voor {datum.strftime('%d-%m-%Y')}")

st.subheader("Bezoekers:")
st.markdown(f"""
- **Begroot:** {begroot}
- **Voorspeld:** {voorspeld}
- **Werkelijk:** {werkelijk}
""")

st.subheader("Omzet:")
st.markdown(f"""
- **Voorspelling:** € {omzet_voorspelling}
- **Werkelijk:** _[hier werkelijke omzet tonen indien data beschikbaar]_
""")

# Checkboxen om locaties te tonen
locaties = ['Entree', 'Oranjerie', 'Bloemenkas']
tonen = []
for locatie in locaties:
    if st.checkbox(f"Toon {locatie}"):
        tonen.append(locatie)

# ---- Hierna kun je per locatie dezelfde opzet doen ----
# Laat productvoorspellingen etc. tonen per locatie indien gewenst

# Productvoorspelling voorbeeld
st.subheader("Productvoorspelling (park-totaal):")
st.write("_Hier je productvoorspellingen tonen (net zoals je eerder deed)_")

# ---- Einde ----
