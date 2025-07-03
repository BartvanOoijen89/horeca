import streamlit as st
import pandas as pd
import joblib
import requests
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="📊 Horeca Verkoopvoorspelling Appeltern", layout="wide")
st.title("📊 Verkoopvoorspelling per Product – Appeltern")

# 📁 Constants
DATA_FOLDER = "verkoopdata"
EXCEL_BEGROTING = "Horeca-data 2025 (Tot 19 mei 2025).xlsx"

# 📥 Laad begroting
@st.cache_data
def load_budget_data():
    return pd.read_excel(EXCEL_BEGROTING, parse_dates=["Data 2025"])

budget_df = load_budget_data()

# 📅 Datumselectie
date_input = st.date_input("📅 Kies een datum", datetime.today())

# 🔑 API-key ophalen
api_key = st.secrets["weather"]["api_key"]

# 🌦️ Huidig of voorspeld weer ophalen
def get_weather(api_key, lat=51.8421, lon=5.5820, date=None):
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={api_key}"
    r = requests.get(url)
    if r.status_code == 200:
        data = r.json()
        if date.date
