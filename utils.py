import requests
from datetime import datetime
import streamlit as st

# 🧠 Haal weerdata op via OpenWeather API
def get_weather(api_key, date=None, locatie="Appeltern"):
    if not api_key:
        api_key = st.secrets["weather"]["api_key"]

    # OpenWeatherMap werkt met lat/lon
    LAT, LON = 51.865, 5.618  # Appeltern

    # 📅 Vandaag = gebruik 'current weather' endpoint
    if date is None or date.date() == datetime.now().date():
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&units=metric&appid={api_key}"
        response = requests.get(url).json()
        temperature = response["main"]["temp"]
        rain_mm = response.get("rain", {}).get("1h", 0.0)
        return temperature, rain_mm

    # 🕒 Historisch of toekomstig: gebruik One Call API (alleen voor max 7 dagen vooruit of verleden)
    unix_time = int(date.timestamp())
    url = f"https://api.openweathermap.org/data/3.0/onecall/timemachine?lat={LAT}&lon={LON}&dt={unix_time}&units=metric&appid={api_key}"
    response = requests.get(url).json()

    if "data" in response and len(response["data"]) > 0:
        temperature = response["data"][0].get("temp", 0.0)
        rain_mm = response["data"][0].get("rain", {}).get("1h", 0.0)
        return temperature, rain_mm
    elif "hourly" in response and len(response["hourly"]) > 0:
        temps = [h.get("temp", 0.0) for h in response["hourly"]]
        rains = [h.get("rain", {}).get("1h", 0.0) for h in response["hourly"]]
        avg_temp = sum(temps) / len(temps)
        total_rain = sum(rains)
        return avg_temp, total_rain

    return None, None
